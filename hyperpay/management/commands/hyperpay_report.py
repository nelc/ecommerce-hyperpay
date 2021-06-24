import datetime
import logging
import re
import smtplib

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.template import loader
from django.utils.timezone import now
from oscar.core.loading import get_class, get_classes

from hyperpay.processors import HyperPay, HyperPayMada

logger = logging.getLogger(__name__)
PaymentProcessorResponse = get_class("payment.models", "PaymentProcessorResponse")

REPORT_DUARATION = 5
# Hyperpay result codes for manual review can be found at
# https://hyperpay.docs.oppwa.com/reference/resultCodes#successful under the section
# "Result codes for successfully processed transactions that should be manually reviewed"
SUCCESS_MANUAL_REVIEW_CODES_REGEX = re.compile(r'^(000\.400\.0[^3]|000\.400\.[0-1]{2}0)')


class Command(BaseCommand):

    help = """
        Generates a report of transaction/reponses from Hyperpay in past N hours
        which require manual verification/action and sends the report
        to the provided email address
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "-d",
            "--duration",
            default=REPORT_DUARATION,
            type=int,
            help="Duration in hours to check the past records from now. Defaults to %s" % REPORT_DUARATION
        )
        parser.add_argument(
            "-e",
            "--emails",
            required=True,
            nargs="+",
            help="The email addresses to which the report will be sent."
        )

    def handle(self, *args, **options):
        """
        Main command dispatch.
        """
        time_duration = options.get("duration")
        recipient_list = options.get("emails")
        actionable_payment_responses = []
        past_responses = PaymentProcessorResponse.objects.filter(
            processor_name__in=[HyperPay.NAME, HyperPayMada.NAME],
            created__gte=now() - datetime.timedelta(hours=time_duration)
        )
        for response in past_responses:
            result_code = response.response["result"]["code"]
            if SUCCESS_MANUAL_REVIEW_CODES_REGEX.search(result_code):
                actionable_payment_responses.append(response)

        logger.info("Found %s payment records requiring action", len(actionable_payment_responses))
        if actionable_payment_responses:
            self._render_email_and_send(actionable_payment_responses, recipient_list)

    def _render_email_and_send(self, payment_reponses, recipient_list):
        """
        Render email with all the transactions requiring manual verification
        and send the email
        """
        html_template = loader.get_template("payment/hyperpay_report.html")
        text_template = loader.get_template("payment/hyperpay_report.txt")
        context = {
            "responses": payment_reponses
        }
        html_message = html_template.render(context)
        message = text_template.render(context)

        try:
            send_mail(
                from_email=settings.OSCAR_FROM_EMAIL,
                subject="Action Required! Payment Report",
                html_message=html_message,
                message=message,
                recipient_list=recipient_list
            )
        except smtplib.SMTPException:
            logger.error("Failed to send email")
