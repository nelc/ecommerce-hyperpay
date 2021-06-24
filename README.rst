HyperPay Payment Processor backend for Open edX ecommerce
=========================================================

This application provides a custom `Open edX ecommerce <https://github.com/edx/ecommerce/>`
payment processor backend for the
`HyperPay payment processor <https://wordpresshyperpay.docs.oppwa.com/tutorials/integration-guide>`_.

Installation and usage
######################

* Install this repository inside the ecommerce virtualenv environment using `pip`.
* In `ecommerce.yml`, add the following settings:
  ::

     ADDL_INSTALLED_APPS:
       - hyperpay
     ADDL_PAYMENT_PROCESSORS:
       - 'hyperpay.processors.HyperPay'
       - 'hyperpay.processors.HyperPayMada'
     # many other settings
     PAYMENT_PROCESSOR_CONFIG:
       <partner name>:
         <hyperpay or hyperpay_mada>:
           access_token: <hyperpay access token>
           entity_id: <entity id for hyperpay or hyperpay_mada>
           currency: <3-letter ISO 4217 currency code supported by HyperPay>
           hyperpay_base_api_url: <hyperpay base API URL to use - https://test.oppwa.com is used for testing>
           return_url: <URL to which HyperPay must redirect after a transaction.Either /payment/hyperpay/submit/ or /payment/hyperpay/mada/submit/ depending on the backend>
           encryption_key: <encryption key to use for encrypting the sensitive values in the URL>
           salt: <salt to use with the above encryption key>

* Restart the `ecommerce` service in production and the devserver in the devstack.
* In the `ecommerce` Django admin site, create waffle switches `payment_processor_active_hyperpay`, `payment_processor_active_hyperpay_mada` to enable the backends.
* Verify and ensure that the `enable_client_side_checkout` waffle flag is disabled for everyone.
* Once these steps are done, the `HyperPay` and `HyperPayMada` processor backends provided by this application will be available as payment options
  during the payment flow for purchasing paid seats in courses.
