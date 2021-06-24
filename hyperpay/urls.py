"""
Defines the URL routes for the hyperpay app.
"""
from django.conf.urls import url

from .views import HyperPayMadaResponseView, HyperPayPaymentPageView, HyperPayResponseView

urlpatterns = [
    url(r'^payment/hyperpay/pay/$', HyperPayPaymentPageView.as_view(), name='payment-form'),
    url(r'^payment/hyperpay/submit/$', HyperPayResponseView.as_view(), name='submit'),
    url(
        r'^payment/hyperpay/status/(?P<encrypted_resource_path>.+)/$',
        HyperPayResponseView.as_view(),
        name='status-check'
    ),
    url(r'^payment/hyperpay/mada/submit/$', HyperPayMadaResponseView.as_view(), name='mada-submit'),
    url(
        r'^payment/hyperpay/mada/status/(?P<encrypted_resource_path>.+)/$',
        HyperPayMadaResponseView.as_view(),
        name='mada-status-check'
    ),
]
