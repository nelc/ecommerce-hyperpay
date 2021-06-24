"""
HyperPay payment processor Django application initialization.
"""
from django.apps import AppConfig


class HyperPayConfig(AppConfig):
    """
    Configuration for the HyperPay payment processor Django application.
    """
    name = 'hyperpay'
    plugin_app = {
        'url_config': {
            'ecommerce': {
                'namespace': 'hyperpay',
            }
        },
    }
