from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from accounts.models import User
from workers.models import Skill, WorkerProfile, WorkerSkill

pytestmark = pytest.mark.django_db


def _user(role, email, phone):
    return User.objects.create_user(
        email=email,
        password="Workcove-test-1",
        phone=phone,
        role=role,
    )


def test_worker_profile_links_skills():
    worker = _user(User.Role.WORKER, "worker@example.com", "+14155552671")
    profile = WorkerProfile.objects.create(
        user=worker,
        city="San Jose",
        state="CA",
        zip_code="95110",
        hourly_rate=Decimal("25.00"),
    )
    skill = Skill.objects.create(name="Warehouse loading")
    WorkerSkill.objects.create(worker=profile, skill=skill)

    assert list(profile.skills.values_list("name", flat=True)) == ["Warehouse loading"]


def test_hiring_manager_cannot_have_a_worker_profile():
    manager = _user(User.Role.HIRING_MANAGER, "manager@example.com", "+14155552672")
    with pytest.raises(ValidationError):
        WorkerProfile.objects.create(user=manager, hourly_rate=Decimal("30.00"))


def test_location_needs_city_state_and_zip_code():
    worker = _user(User.Role.WORKER, "worker2@example.com", "+14155552673")
    with pytest.raises(ValidationError):
        WorkerProfile.objects.create(
            user=worker,
            city="San Jose",
            hourly_rate=Decimal("25.00"),
        )
