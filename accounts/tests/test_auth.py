import re
from datetime import timedelta

import pytest
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from rest_framework.test import APIClient

from django.conf import settings

from accounts.models import LoginCode, SmsConsent, User
from accounts.sms import LocMemSMSBackend

pytestmark = pytest.mark.django_db

PASSWORD = "Workcove-test-1"
REGISTER = "/auth/register/"
LOGIN = "/auth/login/"
VERIFY = "/auth/verify/"


@pytest.fixture
def api(settings):
    settings.SMS_BACKEND = "accounts.sms.LocMemSMSBackend"
    LocMemSMSBackend.messages.clear()
    return APIClient()


def _register(api, **overrides):
    payload = {
        "email": "worker@example.com",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
        "phone": "+14155552671",
        "role": User.Role.WORKER,
        "sms_opt_in": True,
    }
    payload.update(overrides)
    return api.post(REGISTER, payload, format="json")


def _code_from_sms():
    _phone, body = LocMemSMSBackend.messages[-1]
    return re.search(r"(\d{6})", body).group(1)


def _login(api, email="worker@example.com", password=PASSWORD):
    return api.post(LOGIN, {"email": email, "password": password}, format="json")


def test_register_worker_and_hiring_manager(api):
    worker = _register(api)
    manager = _register(
        api,
        email="manager@example.com",
        phone="+14155552672",
        role=User.Role.HIRING_MANAGER,
    )

    assert worker.status_code == 201
    assert worker.data["role"] == "worker"
    assert "password" not in worker.data
    assert manager.status_code == 201
    assert manager.data["role"] == "hiring_manager"
    assert User.objects.count() == 2


def test_register_rejects_duplicate_email_and_mismatched_password(api):
    assert _register(api).status_code == 201
    duplicate = _register(api, phone="+14155552673")
    mismatch = _register(
        api,
        email="other@example.com",
        phone="+14155552674",
        password_confirm="different-password-1",
    )

    assert duplicate.status_code == 400
    assert mismatch.status_code == 400


def test_login_sends_a_hashed_single_use_code(api):
    _register(api)
    response = _login(api)

    assert response.status_code == 200
    assert response.data["expires_in"] == 300
    assert response.data["phone"] == "***2671"
    sent = _code_from_sms()
    challenge = LoginCode.objects.get(pk=response.data["challenge_id"])
    assert challenge.code_hash != sent
    assert sent not in challenge.code_hash
    assert check_password(sent, challenge.code_hash)
    assert challenge.expires_at - challenge.created_at == timedelta(minutes=5)

    verified = api.post(
        VERIFY,
        {"challenge_id": response.data["challenge_id"], "code": sent},
        format="json",
    )
    assert verified.status_code == 200
    assert verified.data["user"]["email"] == "worker@example.com"
    assert verified.data["user"]["role"] == "worker"
    assert verified.data["access"]
    assert verified.data["refresh"]

    reused = api.post(
        VERIFY,
        {"challenge_id": response.data["challenge_id"], "code": sent},
        format="json",
    )
    assert reused.status_code == 400
    assert reused.data["code"] == "already_used"


def test_wrong_password_does_not_send_a_code(api):
    _register(api)
    response = _login(api, password="not-the-password")

    assert response.status_code == 401
    assert response.data["code"] == "invalid_credentials"
    assert LoginCode.objects.count() == 0
    assert LocMemSMSBackend.messages == []


def test_code_expires_and_locks_after_five_attempts(api):
    _register(api)
    response = _login(api)
    sent = _code_from_sms()
    challenge_id = response.data["challenge_id"]
    wrong = "000000" if sent != "000000" else "111111"

    challenge = LoginCode.objects.get(pk=challenge_id)
    challenge.expires_at = timezone.now() - timedelta(seconds=1)
    challenge.save(update_fields=["expires_at"])
    expired = api.post(VERIFY, {"challenge_id": challenge_id, "code": sent}, format="json")
    assert expired.data["code"] == "expired"

    challenge.expires_at = timezone.now() + timedelta(minutes=5)
    challenge.save(update_fields=["expires_at"])
    for remaining in (4, 3, 2, 1):
        attempt = api.post(VERIFY, {"challenge_id": challenge_id, "code": wrong}, format="json")
        assert attempt.status_code == 400
        assert attempt.data["code"] == "invalid_code"
        assert attempt.data["attempts_remaining"] == remaining

    locked = api.post(VERIFY, {"challenge_id": challenge_id, "code": wrong}, format="json")
    assert locked.status_code == 400
    assert locked.data["code"] == "too_many_attempts"
    after_lock = api.post(VERIFY, {"challenge_id": challenge_id, "code": sent}, format="json")
    assert after_lock.status_code == 400
    assert after_lock.data["code"] == "too_many_attempts"
    challenge.refresh_from_db()
    assert challenge.used_at is None
    assert challenge.attempts == LoginCode.MAX_ATTEMPTS


def test_new_login_invalidates_the_previous_code(api):
    _register(api)
    first = _login(api)
    first_code = _code_from_sms()
    challenge = LoginCode.objects.get(pk=first.data["challenge_id"])
    challenge.created_at = timezone.now() - timedelta(seconds=61)
    challenge.save(update_fields=["created_at"])

    second = _login(api)
    assert second.status_code == 200
    old = api.post(
        VERIFY,
        {"challenge_id": first.data["challenge_id"], "code": first_code},
        format="json",
    )
    assert old.data["code"] == "already_used"

    current = api.post(
        VERIFY,
        {"challenge_id": second.data["challenge_id"], "code": _code_from_sms()},
        format="json",
    )
    assert current.status_code == 200


def test_registration_stores_text_consent(api):
    response = _register(api)

    assert response.status_code == 201
    consent = SmsConsent.objects.get(user__email="worker@example.com")
    assert consent.phone_number == "+14155552671"
    assert consent.ip_address == "127.0.0.1"
    assert consent.terms_version == settings.SMS_TERMS_VERSION
    assert consent.opted_in_at is not None
    assert consent.revoked_at is None
    assert consent.user.sms_opt_in is True


def test_admin_sms_checkbox_records_consent(api):
    from django.contrib.admin.sites import AdminSite
    from django.test import RequestFactory

    from accounts.admin import UserAdmin
    from accounts.consent import has_active_sms_consent

    _register(api, sms_opt_in=False)
    user = User.objects.get(email="worker@example.com")
    user.sms_opt_in = True
    request = RequestFactory().post("/admin/accounts/user/1/change/")
    UserAdmin(User, AdminSite()).save_model(request, user, form=None, change=True)

    user.refresh_from_db()
    consent = SmsConsent.objects.get(user=user)
    assert consent.phone_number == "+14155552671"
    assert consent.revoked_at is None
    assert has_active_sms_consent(user) is True


def test_login_does_not_text_without_consent(api):
    registered = _register(api, sms_opt_in=False)
    response = _login(api)

    assert registered.status_code == 201
    assert response.status_code == 403
    assert response.data["code"] == "sms_consent_required"
    assert SmsConsent.objects.count() == 0
    assert LocMemSMSBackend.messages == []
