import datetime
import logging
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.six import StringIO
from django.utils.timezone import now
from oscar.core.loading import get_class

from ecommerce.extensions.payment.models import PaymentProcessorResponse
from ecommerce.tests.testcases import TestCase
from hyperpay.processors import HyperPay, HyperPayMada

PaymentProcessorResponse = get_class("payment.models", "PaymentProcessorResponse")


class HyperPayReportCommandTestCase(TestCase):

    def setUp(self):
        self.stdout = StringIO()
        self.success_response = {"result": {"code": "000.000.000"}}
        self.hyperpay_success_response = PaymentProcessorResponse.objects.create(
            processor_name=HyperPay.NAME,
            response=self.success_response
        )
        self.mada_success_response = PaymentProcessorResponse.objects.create(
            processor_name=HyperPayMada.NAME,
            response=self.success_response
        )

    def tearDown(self):
        self.hyperpay_success_response.delete()
        self.mada_success_response.delete()

    def test_email_is_required(self):
        """
        Test that CommandError is raised if required email parameter is not passed
        """
        with self.assertRaises(CommandError) as context:
            call_command('hyperpay_report')
        self.assertEqual("Error: the following arguments are required: -e/--emails", str(context.exception))

    def test_email_not_sent_if_no_actionable_response_found(self):
        """
        Test that no email is sent if there are no actionable responses
        found
        """
        call_command('hyperpay_report', emails=["report1@example.com"])
        self.assertTemplateNotUsed("payment/hyperpay_report.html")
        self.assertTemplateNotUsed("payment/hyperpay_report.txt")
        self.assertLogs(level=logging.INFO)
        self.assertEqual(len(mail.outbox), 0)


class HyperPayReportGenerationTestCase(TestCase):

    def setUp(self):
        self.stdout = StringIO()
        self.manual_review_response = {"result": {"code": "000.400.000"}}
        self.hyperpay_manual_review_response = PaymentProcessorResponse.objects.create(
            processor_name=HyperPay.NAME,
            response=self.manual_review_response
        )
        self.mada_manual_review_response = PaymentProcessorResponse.objects.create(
            processor_name=HyperPayMada.NAME,
            response=self.manual_review_response
        )
        self.old_manual_review_response = PaymentProcessorResponse.objects.create(
            processor_name=HyperPayMada.NAME,
            response=self.manual_review_response,
        )
        self.old_manual_review_response.created = now() - datetime.timedelta(hours=9)
        self.old_manual_review_response.save()

    def tearDown(self):
        self.hyperpay_manual_review_response.delete()
        self.mada_manual_review_response.delete()

    def test_email_sent_if_actionable_responses_found(self):
        """
        Tests that an email is rendered and sent when we find
        actionable responses.
        """
        call_command('hyperpay_report', emails=["report1@example.com"])
        self.assertTemplateUsed("payment/hyperpay_report.html")
        self.assertTemplateUsed("payment/hyperpay_report.txt")
        self.assertLogs(level=logging.INFO)
        self.assertEqual(len(mail.outbox), 1)

    def test_duration_is_configurable(self):
        """
        Test that passing duration allows filtering the records
        that timedelta.
        """
        arguments_1 = (
            [self.hyperpay_manual_review_response, self.mada_manual_review_response],
            ['report1@example.com']
        )
        arguments_2 = (
            [self.hyperpay_manual_review_response, self.mada_manual_review_response, self.old_manual_review_response],
            ['report1@example.com']
        )
        with patch(
            'hyperpay.management.commands.hyperpay_report.Command._render_email_and_send'
        ) as mock_method:
            # We should only get 2 records for 5 hour timedelta
            call_command('hyperpay_report', emails=["report1@example.com"])
            mock_method.assert_called_with(*arguments_1)
            # We should get 3 records now for 10 hours timedelta
            call_command('hyperpay_report', emails=["report1@example.com"], duration=10)
            mock_method.assert_called_with(*arguments_2)
