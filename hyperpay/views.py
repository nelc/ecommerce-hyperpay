"""
Views related to the HyperPay payment processor.
"""

import base64
import logging
import re
from enum import Enum
from urllib.parse import urlencode
import uuid

import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model

from .processors import HyperPay, HyperPayMada

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


def generate_key(encryption_key, salt):
    """
    Generate the encryption key.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        iterations=100000,
        salt=salt.encode(),
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))


def encrypt_string(message, encryption_key, salt):
    """
    Encrypt the string.
    """
    fernet = Fernet(generate_key(encryption_key, salt))
    return fernet.encrypt(message.encode()).decode('utf-8')


def decrypt_string(encrypted_message, encryption_key, salt):
    """
    Decrypt the encrypted string.
    """
    fernet = Fernet(generate_key(encryption_key, salt))
    return fernet.decrypt(encrypted_message.encode()).decode('utf-8')


class PaymentStatus(Enum):
    SUCCESS = 0
    PENDING = 1
    FAILURE = 2


class HyperPayPaymentPageView(View):
    """
    Render the template which loads the HyperPay payment form via JavaScript
    """
    template_name = 'payment/hyperpay.html'

    def post(self, request):
        """
        Handles the POST request.
        """
        context = request.POST.dict()
        context["nonce_id"] = str(uuid.uuid4())
        return render(request, self.template_name, context)


class HyperPayResponseView(EdxOrderPlacementMixin, View):
    """
    Handle the response from HyperPay after processing the payment.

    The result codes returned by HyperPay are documented at https://hyperpay.docs.oppwa.com/reference/resultCodes
    """
    SUCCESS_CODES_REGEX = re.compile(r'^(000\.000\.|000\.100\.1|000\.[36])')
    SUCCESS_MANUAL_REVIEW_CODES_REGEX = re.compile(r'^(000\.400\.0[^3]|000\.400\.[0-1]{2}0)')
    PENDING_CHANGEABLE_SOON_CODES_REGEX = re.compile(r'^(000\.200)')
    PENDING_NOT_CHANGEABLE_SOON_CODES_REGEX = re.compile(r'^(800\.400\.5|100\.400\.500)')
    PENDING_STATUS_URL_NAME = 'hyperpay:status-check'
    PENDING_STATUS_PAGE_TITLE = _('HyperPay - Credit card - pending')

    @property
    def payment_processor(self):
        return HyperPay(self.request.site)

    @method_decorator(transaction.non_atomic_requests)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(HyperPayResponseView, self).dispatch(request, *args, **kwargs)

    def _get_basket(self, basket_id):
        """
        Return the basket for the given id or None.
        """
        if not basket_id:
            return None

        try:
            basket_id = int(basket_id)
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
            Applicator().apply(basket, basket.owner, self.request)
            return basket
        except (ValueError, ObjectDoesNotExist):
            return None

    def _verify_status(self, resource_path):
        """
        Verify the status of the payment.
        """
        status = PaymentStatus.SUCCESS
        payment_status_endpoint = "{}?{}".format(
            self.payment_processor.hyper_pay_api_base_url + resource_path,
            urlencode({'entityId': self.payment_processor.configuration['entity_id']})
        )
        response = requests.get(payment_status_endpoint, headers=self.payment_processor.authentication_headers)
        response_data = response.json()

        result_code = response_data['result']['code']
        if not response.ok:
            logger.error('Received a non-success response status code from HyperPay %s', response.status_code)
            status = PaymentStatus.FAILURE
        elif self.PENDING_CHANGEABLE_SOON_CODES_REGEX.search(result_code):
            logger.warning(
                'Received a pending status code %s from HyperPay for payment id %s.',
                result_code,
                response_data.get('id', 'id-not-found')
            )
            status = PaymentStatus.PENDING
        elif self.PENDING_NOT_CHANGEABLE_SOON_CODES_REGEX.search(result_code):
            logger.warning(
                'Received a pending status code %s from HyperPay for payment id %s. As this can change '
                'after several days, treating it as a failure.',
                result_code,
                response_data.get('id', 'id-not-found')
            )
            status = PaymentStatus.FAILURE
        elif self.SUCCESS_CODES_REGEX.search(result_code):
            logger.info(
                'Received a success status code %s from HyperPay for payment id %s.',
                result_code,
                response_data.get('id', 'id-not-found')
            )
        elif self.SUCCESS_MANUAL_REVIEW_CODES_REGEX.search(result_code):
            logger.error(
                'Received a success status code %s from HyperPay which requires manual verification for payment id %s.'
                'Treating it as a failed transaction.',
                result_code,
                response_data.get('id', 'id-not-found')
            )

            # This is a temporary change till we get clarity on whether this should be treated as a failure.
            status = PaymentStatus.FAILURE
        else:
            logger.error(
                'Received a rejection status code %s from HyperPay for payment id %s',
                result_code,
                response_data.get('id', 'id-not-found')
            )
            status = PaymentStatus.FAILURE

        return response_data, status

    def _handle_pending_status(self, request, encrypted_resource_path, resource_path):
        """
        Handles the pending status.
        """
        encrypted_resource_path_value = encrypt_string(
            resource_path,
            self.payment_processor.encryption_key,
            self.payment_processor.salt
        )
        context = {
            'title': self.PENDING_STATUS_PAGE_TITLE,
            'interval': self.payment_processor.pending_status_polling_interval
        }
        if encrypted_resource_path is not None:
            return render(request, 'payment/hyperpay_pending.html', context)

        request.session['hyperpay_dont_check_status'] = True
        return redirect(
            reverse(
                self.PENDING_STATUS_URL_NAME,
                kwargs={'encrypted_resource_path': encrypted_resource_path_value}
            )
        )

    def _get_resource_path(self, request, encrypted_resource_path):
        """
        Get the resource_path for checking the payment status.
        """
        if encrypted_resource_path is not None:
            resource_path = decrypt_string(
                encrypted_resource_path,
                self.payment_processor.encryption_key,
                self.payment_processor.salt
            )
        else:
            resource_path = request.GET.get('resourcePath')
        return resource_path

    def _get_check_status(self, request):
        """
        Get the value of the check_status variable.
        """
        check_status = True
        if 'hyperpay_dont_check_status' in request.session:
            check_status = False
            del request.session['hyperpay_dont_check_status']
        return check_status

    def _generate_user_data(self, user):
        """
        This extracts the basic user information.

        Args:
            user <User model>: User instance.

        Returns
            dictionary: Basic user data.
        """

        if not user:
            return {}

        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
        }

    def get(self, request, encrypted_resource_path=None):
        """
        Handle the response from HyperPay and redirect to the appropriate page based on the status.
        """
        if encrypted_resource_path is None:
            self.payment_processor.record_processor_response(request.GET, transaction_id=request.GET.get('id'))

        verification_response = {}
        basket = None
        error = None
        transaction_id = 'Unknown'
        status = PaymentStatus.PENDING

        resource_path = self._get_resource_path(request, encrypted_resource_path)
        if resource_path is None:
            logger.error('Received an invalid response from HyperPay')
            return redirect(reverse('payment_error'))

        check_status = self._get_check_status(request)

        try:
            if check_status:
                verification_response, status = self._verify_status(resource_path)

            if verification_response and 'merchantMemo' in verification_response:
                transaction_id = verification_response['merchantMemo']
                basket_id = OrderNumberGenerator().basket_id(transaction_id)
                basket = self._get_basket(basket_id)

            if status == PaymentStatus.FAILURE:
                return redirect(reverse('payment_error'))
            elif status == PaymentStatus.PENDING:
                return self._handle_pending_status(request, encrypted_resource_path, resource_path)

            transaction_id = verification_response['id']

            if not basket:
                logger.error('Received payment for non-existent basket [%s]', basket_id)
                return redirect(reverse('payment_error'))

            if basket.owner != request.user:
                logger.error(
                    'The basket owner for the order %s is not the same as the requesting user %s',
                    basket.owner.username,
                    request.user.username,
                )
                raise Http404
        except Exception as exc:
            error = exc.__class__.__name__
        finally:
            verification_response.update({
                "request_user": self._generate_user_data(request.user),
                "basket_user": self._generate_user_data(getattr(basket, 'owner', None)),
                "status": status.name,
                "error": error,
            })

            payment_processor_response = self.payment_processor.record_processor_response(
                verification_response,
                transaction_id=transaction_id,
                basket=basket
            )

        try:
            with transaction.atomic():
                try:
                    self.handle_payment(verification_response, basket)
                except Exception as exc:
                    logger.exception(
                        'HyperPay payment did not complete for basket [%d] because of [%s]. '
                        'The payment response was recorded in entry [%d].',
                        basket.id,
                        exc.__class__.__name__,
                        payment_processor_response.id
                    )
                    raise
        except Exception as exc:  # pylint:disable=broad-except
            logger.exception(
                'Attempts to handle payment for basket [%d] failed due to [%s].',
                basket.id,
                exc.__class__.__name__
            )
            return redirect(reverse('payment_error'))
        self.create_order(request, basket)
        receipt_url = get_receipt_page_url(
            request=request,
            order_number=basket.order_number,
            site_configuration=basket.site.siteconfiguration
        )
        return redirect(receipt_url)


class HyperPayMadaResponseView(HyperPayResponseView):
    """
    Handle the response from HyperPay after processing the mada payment.
    """
    PENDING_STATUS_URL_NAME = 'hyperpay:mada-status-check'
    PENDING_STATUS_PAGE_TITLE = _('HyperPay - mada - pending')

    @property
    def payment_processor(self):
        return HyperPayMada(self.request.site)
