from datetime import date, time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from accounts.models import User
from jobs.models import Job, JobOffer
from managers.models import ManagerProfile
from workers.models import Skill, WorkerProfile

pytestmark = pytest.mark.django_db


def _manager():
    user = User.objects.create_user(
        email="manager@example.com",
        password="Workcove-test-1",
        phone="+14155552672",
        role=User.Role.HIRING_MANAGER,
    )
    return ManagerProfile.objects.create(user=user, business_name="Cove Staffing")


def _worker(email, phone):
    user = User.objects.create_user(
        email=email,
        password="Workcove-test-1",
        phone=phone,
        role=User.Role.WORKER,
    )
    return WorkerProfile.objects.create(user=user, hourly_rate=Decimal("25.00"))


def _job(manager, headcount=1):
    skill = Skill.objects.create(name=f"Warehouse loading {headcount} {manager.pk}")
    return Job.objects.create(
        manager=manager,
        work_date=date(2026, 10, 6),
        start_time=time(8, 0),
        end_time=time(16, 0),
        city="San Jose",
        state="CA",
        zip_code="95110",
        hourly_rate=Decimal("22.50"),
        skill=skill,
        headcount=headcount,
    )


def test_offer_gets_a_reply_code():
    job = _job(_manager())
    worker = _worker("worker@example.com", "+14155552671")
    offer = JobOffer.objects.create(job=job, worker=worker)

    assert offer.status == JobOffer.Status.PENDING
    assert offer.sent_at is None
    assert len(offer.reply_code) == 4


def test_accepting_the_last_spot_closes_other_offers_and_fills_the_job():
    job = _job(_manager(), headcount=1)
    first = JobOffer.objects.create(job=job, worker=_worker("a@example.com", "+14155552671"))
    second = JobOffer.objects.create(job=job, worker=_worker("b@example.com", "+14155552673"))

    first.status = JobOffer.Status.ACCEPTED
    first.save()

    second.refresh_from_db()
    job.refresh_from_db()
    assert second.status == JobOffer.Status.CLOSED
    assert job.status == Job.Status.FILLED


def test_decline_leaves_other_offers_open():
    job = _job(_manager(), headcount=2)
    first = JobOffer.objects.create(job=job, worker=_worker("a@example.com", "+14155552671"))
    second = JobOffer.objects.create(job=job, worker=_worker("b@example.com", "+14155552673"))

    first.status = JobOffer.Status.DECLINED
    first.save()

    second.refresh_from_db()
    job.refresh_from_db()
    assert second.status == JobOffer.Status.PENDING
    assert job.status == Job.Status.OPEN


def test_same_worker_cannot_be_offered_the_same_job_twice():
    job = _job(_manager())
    worker = _worker("worker@example.com", "+14155552671")
    JobOffer.objects.create(job=job, worker=worker)

    with pytest.raises(ValidationError):
        JobOffer.objects.create(job=job, worker=worker)
