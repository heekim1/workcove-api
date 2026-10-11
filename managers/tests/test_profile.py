import pytest
from django.core.exceptions import ValidationError

from accounts.models import User
from managers.models import ManagerProfile

pytestmark = pytest.mark.django_db


def _user(role, email, phone):
    return User.objects.create_user(
        email=email,
        password="Workcove-test-1",
        phone=phone,
        role=role,
    )


def test_hiring_manager_profile_stores_business_and_location():
    manager = _user(User.Role.HIRING_MANAGER, "manager@example.com", "+14155552672")
    profile = ManagerProfile.objects.create(
        user=manager,
        business_name="Cove Staffing",
        city="San Jose",
        state="CA",
        zip_code="95110",
    )

    assert profile.business_name == "Cove Staffing"
    assert manager.manager_profile == profile


def test_worker_cannot_have_a_manager_profile():
    worker = _user(User.Role.WORKER, "worker@example.com", "+14155552671")
    with pytest.raises(ValidationError):
        ManagerProfile.objects.create(user=worker, business_name="Cove Staffing")


def test_location_needs_city_state_and_zip_code():
    manager = _user(User.Role.HIRING_MANAGER, "manager2@example.com", "+14155552673")
    with pytest.raises(ValidationError):
        ManagerProfile.objects.create(
            user=manager,
            business_name="Cove Staffing",
            city="San Jose",
        )
