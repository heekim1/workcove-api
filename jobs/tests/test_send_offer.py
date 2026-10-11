import pytest
from django.utils import timezone

from accounts.consent import record_sms_consent
from accounts.sms import LocMemSMSBackend, SMSDeliveryError
from jobs.models import Job, JobOffer
from jobs.services import OfferDeliveryError, OfferNotSendable, offer_message, send_offer, send_pending_offers
from jobs.tests.test_offer import _job, _manager, _worker

pytestmark = pytest.mark.django_db


@pytest.fixture
def sms(settings):
    settings.SMS_BACKEND = "accounts.sms.LocMemSMSBackend"
    LocMemSMSBackend.messages.clear()


def _opted_in_worker(email, phone):
    worker = _worker(email, phone)
    record_sms_consent(worker.user, "127.0.0.1")
    return worker


def test_send_offer_texts_the_worker_and_marks_it_sent(sms):
    job = _job(_manager())
    offer = JobOffer.objects.create(job=job, worker=_opted_in_worker("worker@example.com", "+14155552671"))
    before = timezone.now()

    sent = send_offer(offer)

    phone, body = LocMemSMSBackend.messages[-1]
    assert phone == "+14155552671"
    assert body == offer_message(offer)
    assert offer.reply_code in body
    assert "YES" in body
    assert "NO" in body
    assert sent.status == JobOffer.Status.SENT
    assert sent.sent_at >= before


def test_a_sent_offer_is_not_texted_again(sms):
    offer = JobOffer.objects.create(
        job=_job(_manager()),
        worker=_opted_in_worker("worker@example.com", "+14155552671"),
    )
    send_offer(offer)

    with pytest.raises(OfferNotSendable):
        send_offer(offer)
    assert len(LocMemSMSBackend.messages) == 1


def test_failed_sms_leaves_the_offer_pending(sms, monkeypatch):
    offer = JobOffer.objects.create(
        job=_job(_manager()),
        worker=_opted_in_worker("worker@example.com", "+14155552671"),
    )

    class Failing:
        def send_job_offer(self, phone, body):
            raise SMSDeliveryError("provider down")

    monkeypatch.setattr("jobs.services.get_sms_backend", lambda: Failing())
    with pytest.raises(OfferDeliveryError):
        send_offer(offer)

    offer.refresh_from_db()
    assert offer.status == JobOffer.Status.PENDING
    assert offer.sent_at is None


def test_send_pending_offers_skips_answered_offers(sms):
    job = _job(_manager(), headcount=2)
    waiting = JobOffer.objects.create(job=job, worker=_opted_in_worker("a@example.com", "+14155552671"))
    declined = JobOffer.objects.create(job=job, worker=_worker("b@example.com", "+14155552673"))
    declined.status = JobOffer.Status.DECLINED
    declined.save()

    sent, failed = send_pending_offers(job)

    assert failed == []
    assert [offer.pk for offer in sent] == [waiting.pk]
    assert LocMemSMSBackend.messages[0][0] == "+14155552671"
    waiting.refresh_from_db()
    declined.refresh_from_db()
    assert waiting.status == JobOffer.Status.SENT
    assert declined.status == JobOffer.Status.DECLINED
    assert job.status == Job.Status.OPEN


def test_offer_is_not_sent_without_text_consent(sms):
    offer = JobOffer.objects.create(
        job=_job(_manager()),
        worker=_worker("worker@example.com", "+14155552671"),
    )

    with pytest.raises(OfferNotSendable):
        send_offer(offer)

    offer.refresh_from_db()
    assert offer.status == JobOffer.Status.PENDING
    assert LocMemSMSBackend.messages == []
