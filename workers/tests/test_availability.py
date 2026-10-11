from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from accounts.models import User
from workers.models import Availability, WorkerProfile

pytestmark = pytest.mark.django_db


def _profile(email, phone):
    user = User.objects.create_user(
        email=email,
        password="Workcove-test-1",
        phone=phone,
        role=User.Role.WORKER,
    )
    return WorkerProfile.objects.create(user=user, hourly_rate=Decimal("25.00"))


def test_worker_can_be_available_on_a_date():
    profile = _profile("worker@example.com", "+14155552671")
    day = date(2026, 10, 6)
    row = Availability.objects.create(worker=profile, date=day)

    assert row.is_available is True
    assert list(profile.availability.values_list("date", flat=True)) == [day]


def test_same_worker_cannot_have_two_rows_for_one_date():
    profile = _profile("worker@example.com", "+14155552671")
    day = date(2026, 10, 6)
    Availability.objects.create(worker=profile, date=day)

    with pytest.raises(ValidationError):
        Availability.objects.create(worker=profile, date=day, is_available=False)
