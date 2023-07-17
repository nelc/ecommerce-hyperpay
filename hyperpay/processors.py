"""
HyperPay payment processor.
"""

import logging
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from oscar.apps.payment.exceptions import GatewayError

from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse
from ecommerce.extensions.payment.utils import clean_field_value

logger = logging.getLogger(__name__)


def format_price(price):
    """
    Return the price in the expected format.
    """
    return '{:0.2f}'.format(price)


class HyperPayException(GatewayError):
    """
    An umbrella exception to catch all errors from HyperPay.
    """
    pass  # pylint: disable=unnecessary-pass


class HyperPay(BasePaymentProcessor):
    """
    HyperPay payment processor.

    For reference, see https://hyperpay.docs.oppwa.com/integration-guide and
    https://hyperpay.docs.oppwa.com/reference/parameters.
    """

    NAME = 'hyperpay'
    PAYMENT_MODE = _('Credit card')
    PAYMENT_TYPE = 'CD'
    CHECKOUTS_ENDPOINT = '/v1/checkouts'
    PAYMENT_WIDGET_JS_PATH = '/v1/paymentWidgets.js'
    RESULT_CODE_SUCCESSFULLY_CREATED_CHECKOUT = '000.200.100'
    CART_ITEM_TYPE_DIGITAL = 'DIGITAL'
    BILLING_ADDRESS_STREET1_MAX_LEN = 95
    BILLING_ADDRESS_STREET2_MAX_LEN = 100
    BRANDS = "VISA MASTER"
    CHECKOUT_TEXT = _("Checkout with credit card")

    def __init__(self, site):
        super(HyperPay, self).__init__(site)
        configuration = self.configuration
        self.access_token = configuration['access_token']
        self.entity_id = configuration['entity_id']
        self.return_url = configuration['return_url']
        self.currency = configuration['currency']
        self.hyper_pay_api_base_url = configuration.get('hyper_pay_api_base_url', 'https://test.oppwa.com')
        self.test_mode = configuration.get('test_mode')
        self.encryption_key = configuration.get('encryption_key', settings.SECRET_KEY)
        self.salt = configuration['salt']
        self.site = site
        self.pending_status_polling_interval = int(configuration.get('pending_status_polling_interval', 30))

    @property
    def authentication_headers(self):
        """
        Return the authentication headers.
        """
        return {
            'Authorization': 'Bearer {}'.format(self.access_token)
        }

    def _get_customer_profile_data(self, user, request):
        """
        Return the user profile data.
        """

        def get_extended_profile_field(account_details, field_name, default_value=None):
            """
            Helper function to get the values of extended profile fields.
            """
            return next(
                (
                    field.get('field_value', default_value) for field in account_details['extended_profile']
                    if field['field_name'] == field_name
                ),
                default_value
            )
        user_account_details = user.account_details(request)
        data = {
            'customer.email': user.email,
        }

        first_name = get_extended_profile_field(user_account_details, 'first_name', '')
        if first_name:
            data['customer.givenName'] = first_name
            data['customer.surname'] = get_extended_profile_field(user_account_details, 'last_name', '')
        else:
            logger.warning('Unable to get the first name and last name for the user %s', user.username)

        return data

    def _get_basket_data(self, basket):
        """
        Return the basket data
        """

        def get_cart_field(index, name):
            """
            Return the cart field name.
            """
            return 'cart.items[{}].{}'.format(index, name)

        basket_data = {
            'amount': format_price(basket.total_incl_tax),
            'currency': self.currency,
            'merchantTransactionId': basket.order_number.replace("-", ""),
            'merchantMemo': basket.order_number,
        }
        for index, line in enumerate(basket.all_lines()):
            cart_item = {
                get_cart_field(index, 'name'): clean_field_value(line.product.title),
                get_cart_field(index, 'quantity'): line.quantity,
                get_cart_field(index, 'type'): self.CART_ITEM_TYPE_DIGITAL,
                get_cart_field(index, 'sku'): line.stockrecord.partner_sku,
                get_cart_field(index, 'price'): format_price(line.unit_price_incl_tax),
                get_cart_field(index, 'currency'): self.currency,
                get_cart_field(index, 'totalAmount'): format_price(line.line_price_incl_tax_incl_discounts)
            }
            basket_data.update(cart_item)
        return basket_data

    def _get_checkout_id(self, basket, request):
        """
        Prepare the checkout and return the checkout ID.
        """
        checkouts_api_url = self.hyper_pay_api_base_url + self.CHECKOUTS_ENDPOINT
        request_data = {
            'entityId': self.entity_id,
            'paymentType': self.PAYMENT_TYPE
        }
        if self.test_mode:
            request_data['testMode'] = self.test_mode

        request_data.update(self._get_basket_data(basket))
        request_data.update(self._get_customer_profile_data(basket.owner, request))

        try:
            response = requests.post(
                checkouts_api_url,
                request_data,
                headers=self.authentication_headers
            )
        except Exception as exc:
            raise HyperPayException('Error creating a checkout. {}'.format(exc))

        data = response.json()
        if 'result' not in data or 'code' not in data['result']:
            raise HyperPayException(
                'Error creating checkout. Invalid response from HyperPay.'
            )
        result_code = data['result']['code']
        if result_code != self.RESULT_CODE_SUCCESSFULLY_CREATED_CHECKOUT:
            raise HyperPayException(
                'Error creating checkout. HyperPay status code: {}'.format(result_code)
            )
        return data['id']

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """
        Return the transaction parameters needed for this processor.
        """
        payment_widget_js_url = '{}?{}'.format(
            self.hyper_pay_api_base_url + self.PAYMENT_WIDGET_JS_PATH,
            urlencode({'checkoutId': self._get_checkout_id(basket, request)})
        )
        transaction_parameters = {
            'payment_widget_js': payment_widget_js_url,
            'payment_page_url': reverse('hyperpay:payment-form'),
            'payment_result_url': self.return_url,
            'brands': self.BRANDS,
            'payment_mode': self.PAYMENT_MODE,
            'locale': request.LANGUAGE_CODE.split('-')[0],
            'csrfmiddlewaretoken': get_token(request),
        }
        return transaction_parameters

    def handle_processor_response(self, response, basket=None):
        """
        Handle the payment processor response and record the relevant details.
        """
        currency = response.get('currency')
        total = response.get('amount')
        transaction_id = response.get('id')
        card_data = response.get('card', {})
        card_number = '{}XXXXXX{}'.format(
            card_data.get('bin', 'XXXXXX'),
            card_data.get('last4Digits', 'XXXX')
        )
        payment_type = response.get('paymentBrand', 'Unknown')

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=card_number,
            card_type=payment_type
        )

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        """
        This is currently not implemented.
        """
        logger.exception(
            'HyperPay processor cannot issue credits or refunds from Open edX ecommerce.'
        )


class HyperPayMada(HyperPay):
    """
    HyperPay payment processor for mada.
    """
    NAME = 'hyperpay_mada'
    PAYMENT_MODE = _('mada')
    BRANDS = "MADA"
    CHECKOUT_TEXT = _("Checkout with mada")
    PAYMENT_TYPE = 'DB'
