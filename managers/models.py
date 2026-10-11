from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from accounts.models import User
from workers.models import US_STATES


class ManagerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="manager_profile",
        limit_choices_to={"role": User.Role.HIRING_MANAGER},
    )
    business_name = models.CharField(max_length=120)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=2, choices=US_STATES, blank=True)
    zip_code = models.CharField(
        max_length=10,
        blank=True,
        validators=[RegexValidator(r"^\d{5}(-\d{4})?$", "Enter a 5-digit ZIP code.")],
        verbose_name="ZIP code",
    )

    def clean(self):
        self.business_name = (self.business_name or "").strip()
        self.city = (self.city or "").strip()
        self.zip_code = (self.zip_code or "").strip()
        errors = {}
        if not self.business_name:
            errors["business_name"] = "Enter a business name."
        if self.user_id and self.user.role != User.Role.HIRING_MANAGER:
            errors["user"] = "A manager profile can only belong to a hiring manager account."
        filled = (bool(self.city), bool(self.state), bool(self.zip_code))
        if any(filled) and not all(filled):
            errors["city"] = "Set city, state, and ZIP code, or leave all three empty."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.business_name
