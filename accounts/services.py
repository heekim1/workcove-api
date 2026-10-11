import importlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from .consent import has_active_sms_consent
from .models import LoginCode, User

RESEND_COOLDOWN = timedelta(seconds=60)
_DUMMY_PASSWORD_HASH = make_password("unused-login-timing-pad")


class AuthError(Exception):
    status_code = 400
    code = "invalid"
    detail = "Invalid request."

    def __init__(self, detail=None, extra=None):
        self.detail = self.detail if detail is None else detail
        self.extra = extra or {}
        super().__init__(self.detail)


class InvalidCredentials(AuthError):
    status_code = 401
    code = "invalid_credentials"
    detail = "Invalid email or password."


class InvalidLoginCode(AuthError):
    code = "invalid_code"
    detail = "Invalid code."


class ExpiredLoginCode(AuthError):
    code = "expired"
    detail = "This code has expired. Request a new one."


class LoginCodeAlreadyUsed(AuthError):
    code = "already_used"
    detail = "This code has already been used."


class TooManyAttempts(AuthError):
    code = "too_many_attempts"
    detail = "Too many attempts. Request a new code."


class ResendCooldown(AuthError):
    status_code = 429
    code = "resend_cooldown"
    detail = "A code was just sent. Wait before requesting another."


class SmsConsentRequired(AuthError):
    status_code = 403
    code = "sms_consent_required"
    detail = "This phone number has not agreed to receive text messages."


def get_sms_backend():
    module_name, class_name = settings.SMS_BACKEND.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()


def mask_phone(phone):
    return f"***{phone[-4:]}"


def _generate_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def _message(code):
    return f"Workcove login code: {code}. It expires in 5 minutes."


def issue_login_code(email, password):
    email = email.strip().lower()
    user = User.objects.filter(email=email).first()
    if user is None:
        check_password(password, _DUMMY_PASSWORD_HASH)
        raise InvalidCredentials
    if not user.check_password(password) or not user.is_active:
        raise InvalidCredentials

    now = timezone.now()
    latest = (
        user.login_codes.filter(used_at__isnull=True, expires_at__gt=now)
        .order_by("-created_at")
        .first()
    )
    if (
        latest
        and latest.attempts < LoginCode.MAX_ATTEMPTS
        and latest.created_at > now - RESEND_COOLDOWN
    ):
        retry_after = int((latest.created_at + RESEND_COOLDOWN - now).total_seconds())
        raise ResendCooldown(extra={"retry_after": max(retry_after, 1)})

    if not has_active_sms_consent(user):
        raise SmsConsentRequired

    code = _generate_code()
    delivered_code = get_sms_backend().send_login_code(user.phone, _message(code))
    if delivered_code:
        code = delivered_code
    code_hash = make_password(code)
    with transaction.atomic():
        user.login_codes.filter(used_at__isnull=True).update(used_at=timezone.now())
        challenge = LoginCode.objects.create(
            user=user,
            code_hash=code_hash,
            expires_at=timezone.now(),
        )
        challenge.expires_at = challenge.created_at + timedelta(minutes=LoginCode.TTL_MINUTES)
        challenge.save(update_fields=["expires_at"])

    return challenge


def verify_login_code(challenge_id, code):
    with transaction.atomic():
        try:
            challenge = LoginCode.objects.select_for_update().get(pk=challenge_id)
        except LoginCode.DoesNotExist:
            raise InvalidLoginCode

        if challenge.used_at is not None:
            raise LoginCodeAlreadyUsed
        if challenge.expires_at <= timezone.now():
            raise ExpiredLoginCode
        if challenge.attempts >= LoginCode.MAX_ATTEMPTS:
            raise TooManyAttempts

        if check_password(code, challenge.code_hash):
            challenge.used_at = timezone.now()
            challenge.save(update_fields=["used_at"])
            return challenge.user

        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        attempts = challenge.attempts

    if attempts >= LoginCode.MAX_ATTEMPTS:
        raise TooManyAttempts
    raise InvalidLoginCode(extra={"attempts_remaining": LoginCode.MAX_ATTEMPTS - attempts})
