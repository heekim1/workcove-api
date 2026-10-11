import pytest
from rest_framework.test import APIClient

from accounts.models import User
from jobs.models import Job, JobOffer
from jobs.tests.test_offer import _job, _manager, _worker

pytestmark = pytest.mark.django_db


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_worker_sees_only_open_jobs():
    manager = _manager()
    open_job = _job(manager)
    filled = _job(manager, headcount=2)
    filled.status = Job.Status.FILLED
    filled.save()
    worker = _worker("worker@example.com", "+14155552671")

    response = _client(worker.user).get("/jobs/")

    assert response.status_code == 200
    ids = [job["id"] for job in response.data["results"]]
    assert ids == [open_job.id]
    assert response.data["results"][0]["skill"]
    assert response.data["results"][0]["business_name"] == "Cove Staffing"


def test_anonymous_visitor_can_open_a_job_until_login_is_required():
    job = _job(_manager())

    response = APIClient().get(f"/jobs/{job.id}/")

    assert response.status_code == 200
    assert response.data["my_offer"] is None


def test_worker_can_open_a_job_and_submit_an_offer_without_a_text():
    job = _job(_manager())
    worker = _worker("worker@example.com", "+14155552671")
    client = _client(worker.user)

    detail = client.get(f"/jobs/{job.id}/")
    submit = client.post(f"/jobs/{job.id}/offers/")
    again = client.post(f"/jobs/{job.id}/offers/")

    assert detail.status_code == 200
    assert detail.data["my_offer"] is None
    assert detail.data["city"] == "San Jose"
    assert submit.status_code == 201
    assert submit.data["channel"] == JobOffer.Channel.APP
    assert submit.data["status"] == JobOffer.Status.PENDING
    offer = JobOffer.objects.get(pk=submit.data["id"])
    assert offer.worker == worker
    assert offer.sent_at is None
    assert again.status_code == 400


def test_worker_without_a_profile_cannot_submit():
    job = _job(_manager())
    user = User.objects.create_user(
        email="worker@example.com",
        password="Workcove-test-1",
        phone="+14155552671",
        role=User.Role.WORKER,
    )

    response = _client(user).post(f"/jobs/{job.id}/offers/")

    assert response.status_code == 400
    assert JobOffer.objects.count() == 0


def test_closed_job_is_not_available_to_submit():
    job = _job(_manager())
    job.status = Job.Status.CANCELLED
    job.save()
    worker = _worker("worker@example.com", "+14155552671")

    response = _client(worker.user).post(f"/jobs/{job.id}/offers/")

    assert response.status_code == 404
