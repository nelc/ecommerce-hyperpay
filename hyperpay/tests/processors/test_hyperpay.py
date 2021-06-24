from unittest.mock import patch
from urllib.parse import parse_qsl, unquote, urlencode

import ddt
import responses
from django.urls import reverse

from ecommerce.extensions.payment.models import PaymentProcessorResponse
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.testcases import TestCase
from hyperpay.processors import HyperPay, HyperPayException
from hyperpay.tests.mixins import HyperPayMixin


@ddt.ddt
class HyperPayTests(HyperPayMixin, PaymentProcessorTestCaseMixin, TestCase):
    maxDiff = None
    processor_name = 'hyperpay'
    processor_class = HyperPay
    DEFAULT_BASKET_DATA = {
        'cart.items[0].name': 'Seat in Demo Course with test-certificate-type certificate',
        'cart.items[0].type': 'DIGITAL',
        'amount': '20.00',
        'cart.items[0].quantity': 1,
        'cart.items[0].currency': 'SAR',
        'currency': 'SAR',
        'merchantTransactionId': 'EDX-100001',
        'cart.items[0].sku': '133C822',
        'cart.items[0].price': '20.00',
        'cart.items[0].totalAmount': '20.00'
    }
    DEFAULT_CUSTOMER_PROFILE_DATA = {
        'customer.email': 'ecommerce_test_0@example.com',
        'customer.givenName': 'Test User',
        'customer.surname': 'Last Name',
    }
    DEFAULT_USER_ACCOUNT_DETAILS = {
        'extended_profile': [
            {'field_name': 'first_name', 'field_value': 'Test User'},
            {'field_name': 'last_name', 'field_value': 'Last Name'}
        ]
    }

    def assert_processor_response_recorded(self, processor_name, transaction_id, response, basket=None):
        """
        Ensures a PaymentProcessorResponse exists for the corresponding processor and response.
        """
        ppr = PaymentProcessorResponse.objects.filter(
            processor_name=processor_name,
            transaction_id=transaction_id
        ).latest('created')

        # The response we have for CyberSource is XML. Rather than parse it, we simply check for a single key/value.
        # If that key/value is present it is reasonably safe to assume the others are present.
        expected = {
            'merchantTransactionId': transaction_id,
        }
        self.assertDictContainsSubset(expected, ppr.response)
        self.assertEqual(ppr.basket, basket)

        return ppr.id

    @responses.activate
    @patch('ecommerce.core.models.User.account_details')
    def test__get_checkout_id(self, mock_account_details):
        """
        Test the _get_checkout_id() method.
        """
        mock_account_details.return_value = self.DEFAULT_USER_ACCOUNT_DETAILS
        self.mock_checkout_api_response()
        expected_request_json = {
            'entityId': self.processor.entity_id,
            'paymentType': 'DB',
        }
        expected_request_json.update(self.DEFAULT_BASKET_DATA)
        expected_request_json.update(self.DEFAULT_CUSTOMER_PROFILE_DATA)

        # The following values change for every test and hence have to be updated.
        expected_request_json.update({
            'cart.items[0].sku': self.basket.all_lines()[0].stockrecord.partner_sku,
            'merchantTransactionId': self.basket.order_number
        })

        expected_request_json['customer.email'] = self.basket.owner.email

        checkout_id = self.processor._get_checkout_id(self.basket, self.request)  # pylint:disable=protected-access

        actual_response_json = dict(parse_qsl(unquote(responses.calls[0].request.body)))
        actual_response_json['cart.items[0].quantity'] = int(actual_response_json['cart.items[0].quantity'])

        self.assertTrue(responses.calls[0].request.url.endswith('/v1/checkouts'))
        self.assertEqual(expected_request_json, actual_response_json)
        self.assertEqual(checkout_id, '123456789')

    @responses.activate
    @patch('ecommerce.core.models.User.account_details')
    def test__get_checkout_id_non_success_status_code(self, mock_account_details):
        """
        Test the _get_checkout_id() method when the API call returns a non-success status code.
        """
        mock_account_details.return_value = self.DEFAULT_USER_ACCOUNT_DETAILS
        self.mock_checkout_api_response(code='123456789')
        with self.assertRaises(HyperPayException) as exc:
            self.processor._get_checkout_id(self.basket, self.request)  # pylint:disable=protected-access
        self.assertEqual(exc.exception.args[0], 'Error creating checkout. HyperPay status code: 123456789')

    @responses.activate
    @patch('ecommerce.core.models.User.account_details')
    def test__get_checkout_id_invalid_response(self, mock_account_details):
        """
        Test the _get_checkout_id() method when the API call returns an invalid response.
        """
        mock_account_details.return_value = self.DEFAULT_USER_ACCOUNT_DETAILS
        self.mock_api_response('/v1/checkouts', {'a': 1}, resp=responses)
        with self.assertRaises(HyperPayException) as exc:
            self.processor._get_checkout_id(self.basket, self.request)  # pylint: disable=protected-access
        self.assertEqual(exc.exception.args[0], 'Error creating checkout. Invalid response from HyperPay.')

    @responses.activate
    @patch('hyperpay.processors.get_token')
    @patch('ecommerce.core.models.User.account_details')
    def test_get_transaction_parameters(self, mock_account_details, mock_get_token):  # pylint:disable=arguments-differ
        """
        Test the get_transaction_parameters() method.
        """
        mock_account_details.return_value = self.DEFAULT_USER_ACCOUNT_DETAILS
        mock_get_token.return_value = 'abcd1234'
        self.mock_checkout_api_response()

        payment_widget_js = '{}?{}'.format(
            self.processor.hyper_pay_api_base_url + self.processor.PAYMENT_WIDGET_JS_PATH,
            urlencode({'checkoutId': '123456789'})
        )
        # This is required because the LocaleMiddleware is not invoked for requests created using the RequestFactory.
        self.request.LANGUAGE_CODE = 'en'
        self.assertEqual(
            self.processor.get_transaction_parameters(self.basket, request=self.request),
            {
                'payment_widget_js': payment_widget_js,
                'payment_page_url': reverse('hyperpay:payment-form'),
                'payment_result_url': self.processor.return_url,
                'brands': self.processor.BRANDS,
                'payment_mode': self.processor.PAYMENT_MODE,
                'locale': 'en',
                'csrfmiddlewaretoken': 'abcd1234'
            }
        )

    def test_handle_processor_response(self):
        pass

    def test_issue_credit(self):
        pass

    def test_issue_credit_error(self):
        pass
