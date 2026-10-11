import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .managers import UserManager

phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Enter a phone number in international format, like +14155552671.",
)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        WORKER = "worker", "Worker"
        HIRING_MANAGER = "hiring_manager", "Hiring manager"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=16, unique=True, validators=[phone_validator])
    role = models.CharField(max_length=32, choices=Role.choices)
    sms_opt_in = models.BooleanField(
        default=False,
        help_text="The person checked the box agreeing to receive security codes and job-offer texts.",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone", "role"]
    EMAIL_FIELD = "email"

    def __str__(self):
        return self.email


class LoginCode(models.Model):
    """One-time SMS code for completing login. The code itself is stored hashed."""

    MAX_ATTEMPTS = 5
    TTL_MINUTES = 5

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_codes")
    code_hash = models.CharField(max_length=256)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Login code {self.id} for {self.user_id}"


class SmsConsent(models.Model):
    """Recorded when a person agrees to receive texts. A row with revoked_at set is no longer active."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sms_consents")
    phone_number = models.CharField(max_length=16)
    opted_in_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    terms_version = models.CharField(max_length=32)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opted_in_at"]

    def __str__(self):
        return f"{self.phone_number} opted in at {self.opted_in_at}"
