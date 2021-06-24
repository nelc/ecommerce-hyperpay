from ecommerce.settings.test import *

INSTALLED_APPS += ['hyperpay']

PAYMENT_PROCESSOR_CONFIG = {
    'edx': {
        'hyperpay': {
            'access_token': '1234',
            'entity_id': 'abcd',
            'currency': 'SAR',
            'hyperpay_base_api_url': 'https://test.oppwa.com',
            'return_url': '/payment/hyperpay/submit/',
            'encryption_key': 'test-key',
            'salt': 'test-salt',
        },
        'hyperpay_mada': {
            'access_token': '1234',
            'entity_id': 'efgh',
            'currency': 'SAR',
            'hyperpay_base_api_url': 'https://test.oppwa.com',
            'return_url': '/payment/hyperpay/mada/submit/',
            'encryption_key': 'test-key',
            'salt': 'test-salt',
        },
    },
    'other': {
        'hyperpay': {
            'access_token': '1234',
            'entity_id': 'abcd',
            'currency': 'SAR',
            'hyperpay_base_api_url': 'https://test.oppwa.com',
            'return_url': '/payment/hyperpay/submit/',
            'encryption_key': 'test-key',
            'salt': 'test-salt',
        },
        'hyperpay_mada': {
            'access_token': '1234',
            'entity_id': 'efgh',
            'currency': 'SAR',
            'hyperpay_base_api_url': 'https://test.oppwa.com',
            'return_url': '/payment/hyperpay/mada/submit/',
            'encryption_key': 'test-key',
            'salt': 'test-salt',
        },
    }
}
