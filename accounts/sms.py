import logging
import re

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

SMS_BACKENDS = {
    "console": "accounts.sms.ConsoleSMSBackend",
    "twilio": "accounts.sms.TwilioSMSBackend",
    "sms": "accounts.sms.AwsSMSBackend",
    "aws": "accounts.sms.AwsSMSBackend",
}


def resolve_sms_backend(name):
    if not name:
        name = "console"
    return SMS_BACKENDS.get(name.strip().lower(), name)


class SMSDeliveryError(Exception):
    """The SMS provider did not accept the message."""

    def __init__(self, detail="Could not send the text."):
        self.detail = detail
        super().__init__(detail)


def code_from_message(body):
    match = re.search(r"\b(\d{6})\b", body or "")
    return match.group(1) if match else None


class ConsoleSMSBackend:
    """Logs the message. Used for local development only."""

    def send_login_code(self, phone, body):
        self._log(phone, body)

    def send_job_offer(self, phone, body):
        self._log(phone, body)

    def _log(self, phone, body):
        if not settings.DEBUG:
            raise ImproperlyConfigured(
                "The console SMS backend only runs when DEBUG is on. "
                "Set SMS_BACKEND=twilio or SMS_BACKEND=sms."
            )
        logger.warning("Dev SMS to %s: %s", phone, body)


class LocMemSMSBackend:
    """Stores messages in memory so tests can read the text that was sent."""

    messages = []

    def send_login_code(self, phone, body):
        self.messages.append((phone, body))

    def send_job_offer(self, phone, body):
        self.messages.append((phone, body))


class TwilioSMSBackend:
    """Sends through Twilio. A trial account can send the login template only."""

    def send_login_code(self, phone, body):
        response = self._post(phone, body)
        if _twilio_error_code(response) == 572006:
            response = self._post(phone, "sms_2fa")
        self._raise_for_status(response)
        return code_from_message(response.json().get("body", ""))

    def send_job_offer(self, phone, body):
        response = self._post(phone, body)
        self._raise_for_status(response)

    def _post(self, phone, body):
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        from_number = settings.TWILIO_FROM_NUMBER
        if not account_sid or not auth_token or not from_number:
            raise ImproperlyConfigured(
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER are required."
            )
        return requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            data={"To": phone, "From": from_number, "Body": body},
            auth=(account_sid, auth_token),
            timeout=10,
        )

    def _raise_for_status(self, response):
        if response.status_code >= 300:
            detail = _twilio_error_message(response)
            logger.error("Twilio SMS failed: %s", detail)
            raise SMSDeliveryError(detail)


class AwsSMSBackend:
    """Sends through Amazon SNS. Select with SMS_BACKEND=sms."""

    def send_login_code(self, phone, body):
        self._publish(phone, body)

    def send_job_offer(self, phone, body):
        self._publish(phone, body)

    def _publish(self, phone, body):
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError as exc:
            raise ImproperlyConfigured("boto3 is required for SMS_BACKEND=sms.") from exc

        region = settings.AWS_REGION
        if not region:
            raise ImproperlyConfigured("AWS_REGION is required for SMS_BACKEND=sms.")

        client = boto3.client("sns", region_name=region)
        try:
            client.publish(
                PhoneNumber=phone,
                Message=body,
                MessageAttributes={
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": "Transactional",
                    }
                },
            )
        except (BotoCoreError, ClientError) as exc:
            logger.error("AWS SMS failed: %s", exc)
            raise SMSDeliveryError from exc


def _twilio_error_code(response):
    try:
        return response.json().get("code")
    except ValueError:
        return None


def _twilio_error_message(response):
    try:
        payload = response.json()
    except ValueError:
        return f"Twilio returned status {response.status_code}."
    message = payload.get("message") or f"Twilio returned status {response.status_code}."
    code = payload.get("code")
    if code:
        return f"{message} ({code})"
    return message
