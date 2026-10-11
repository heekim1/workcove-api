from django.conf import settings
from django.utils import timezone

from .models import SmsConsent


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def record_sms_consent(user, ip_address):
    """Store the agreement and mark the account as opted in."""
    consent = SmsConsent.objects.create(
        user=user,
        phone_number=user.phone,
        ip_address=ip_address or None,
        terms_version=settings.SMS_TERMS_VERSION,
    )
    if not user.sms_opt_in:
        user.sms_opt_in = True
        user.save(update_fields=["sms_opt_in"])
    return consent


def revoke_sms_consent(user):
    """Mark every current agreement for this phone as revoked."""
    user.sms_consents.filter(phone_number=user.phone, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    if user.sms_opt_in:
        user.sms_opt_in = False
        user.save(update_fields=["sms_opt_in"])


def has_active_sms_consent(user):
    """True when this phone agreed to the current terms and has not revoked that agreement."""
    return user.sms_consents.filter(
        phone_number=user.phone,
        terms_version=settings.SMS_TERMS_VERSION,
        revoked_at__isnull=True,
    ).exists()
