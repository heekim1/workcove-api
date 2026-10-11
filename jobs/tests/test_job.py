from datetime import date, time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from accounts.models import User
from jobs.models import Job
from managers.models import ManagerProfile
from workers.models import Skill

pytestmark = pytest.mark.django_db


def _manager():
    user = User.objects.create_user(
        email="manager@example.com",
        password="Workcove-test-1",
        phone="+14155552672",
        role=User.Role.HIRING_MANAGER,
    )
    return ManagerProfile.objects.create(user=user, business_name="Cove Staffing")


def test_manager_can_post_a_job():
    manager = _manager()
    skill = Skill.objects.create(name="Warehouse loading")
    job = Job.objects.create(
        manager=manager,
        work_date=date(2026, 10, 6),
        start_time=time(8, 0),
        end_time=time(16, 0),
        city="San Jose",
        state="CA",
        zip_code="95110",
        hourly_rate=Decimal("22.50"),
        skill=skill,
        headcount=5,
    )

    assert job.status == Job.Status.OPEN
    assert list(manager.jobs.values_list("headcount", flat=True)) == [5]


def test_end_time_must_be_after_start_time():
    manager = _manager()
    skill = Skill.objects.create(name="Warehouse loading")
    with pytest.raises(ValidationError):
        Job.objects.create(
            manager=manager,
            work_date=date(2026, 10, 6),
            start_time=time(16, 0),
            end_time=time(8, 0),
            city="San Jose",
            state="CA",
            zip_code="95110",
            hourly_rate=Decimal("22.50"),
            skill=skill,
            headcount=1,
        )
