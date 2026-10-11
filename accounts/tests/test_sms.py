import pytest

from accounts.sms import SMSDeliveryError, TwilioSMSBackend, resolve_sms_backend


def test_sms_backend_names():
    assert resolve_sms_backend("console") == "accounts.sms.ConsoleSMSBackend"
    assert resolve_sms_backend("Twilio") == "accounts.sms.TwilioSMSBackend"
    assert resolve_sms_backend("sms") == "accounts.sms.AwsSMSBackend"
    assert resolve_sms_backend("aws") == "accounts.sms.AwsSMSBackend"


def test_twilio_trial_stores_the_template_code(settings, monkeypatch):
    settings.TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    settings.TWILIO_AUTH_TOKEN = "token"
    settings.TWILIO_FROM_NUMBER = "+17372583478"
    bodies = []

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, data, auth, timeout):
        bodies.append(data["Body"])
        if data["Body"] != "sms_2fa":
            return Response(400, {"code": 572006, "message": "Invalid template name"})
        return Response(
            201,
            {"body": "Your verification code is 482913. It expires in 5 minutes."},
        )

    monkeypatch.setattr("accounts.sms.requests.post", fake_post)
    assert TwilioSMSBackend().send_login_code("+14086556161", "Workcove login code: 111111.") == "482913"
    assert bodies == ["Workcove login code: 111111.", "sms_2fa"]


def test_twilio_offer_does_not_fall_back_to_the_login_template(settings, monkeypatch):
    settings.TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    settings.TWILIO_AUTH_TOKEN = "token"
    settings.TWILIO_FROM_NUMBER = "+17372583478"
    bodies = []

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, data, auth, timeout):
        bodies.append(data["Body"])
        return Response(400, {"code": 572006, "message": "Invalid template name"})

    monkeypatch.setattr("accounts.sms.requests.post", fake_post)
    with pytest.raises(SMSDeliveryError):
        TwilioSMSBackend().send_job_offer(
            "+14086556161",
            "Workcove: Warehouse on Oct 6. Reply K7NP YES to accept.",
        )
    assert bodies == ["Workcove: Warehouse on Oct 6. Reply K7NP YES to accept."]
