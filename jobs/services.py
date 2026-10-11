from django.db import transaction

from accounts.consent import has_active_sms_consent
from accounts.services import get_sms_backend
from accounts.sms import SMSDeliveryError

from .models import Job, JobOffer


class OfferSendError(Exception):
    """The offer was not texted."""

    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


class OfferNotSendable(OfferSendError):
    pass


class OfferDeliveryError(OfferSendError):
    pass


def offer_message(offer):
    job = offer.job
    start = _clock(job.start_time)
    end = _clock(job.end_time)
    when = f"{job.work_date.strftime('%b')} {job.work_date.day}"
    return (
        f"Workcove: {job.skill.name} on {when}, {start}-{end}, "
        f"{job.city}, {job.state}. ${job.hourly_rate:.2f}/hr. "
        f"Reply {offer.reply_code} YES to accept or {offer.reply_code} NO to decline."
    )


def send_offer(offer):
    """Text one pending offer. The status becomes sent only after the provider accepts it."""
    with transaction.atomic():
        locked = (
            JobOffer.objects.select_for_update()
            .select_related("job__skill", "worker__user")
            .get(pk=offer.pk)
        )
        _ensure_sendable(locked)
        phone = locked.worker.user.phone
        body = offer_message(locked)
        try:
            get_sms_backend().send_job_offer(phone, body)
        except SMSDeliveryError as exc:
            raise OfferDeliveryError(exc.detail) from exc
        locked.status = JobOffer.Status.SENT
        locked.save()
    return locked


def send_pending_offers(job):
    """Text every pending offer for a job. One failure does not stop the others."""
    pending = job.offers.filter(
        status=JobOffer.Status.PENDING,
        channel=JobOffer.Channel.TEXT,
    ).order_by("pk")
    sent = []
    failed = []
    for offer in pending:
        try:
            sent.append(send_offer(offer))
        except OfferSendError as exc:
            failed.append((offer, exc))
    return sent, failed


def _ensure_sendable(offer):
    if offer.channel != JobOffer.Channel.TEXT:
        raise OfferNotSendable("This offer was submitted in the app.")
    if offer.status != JobOffer.Status.PENDING:
        raise OfferNotSendable("This offer is not waiting to be sent.")
    if offer.job.status != Job.Status.OPEN:
        raise OfferNotSendable("Offers can only be sent for an open job.")
    if not offer.worker.user.is_active:
        raise OfferNotSendable("This worker's account is inactive.")
    if not has_active_sms_consent(offer.worker.user):
        raise OfferNotSendable("This worker has not agreed to receive texts.")


def _clock(value):
    return value.strftime("%I:%M %p").lstrip("0")
