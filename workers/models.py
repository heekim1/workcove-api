from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from accounts.models import User

US_STATES = [
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("DC", "District of Columbia"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
]


class Skill(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WorkerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="worker_profile",
        limit_choices_to={"role": User.Role.WORKER},
    )
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=2, choices=US_STATES, blank=True)
    zip_code = models.CharField(
        max_length=10,
        blank=True,
        validators=[RegexValidator(r"^\d{5}(-\d{4})?$", "Enter a 5-digit ZIP code.")],
        verbose_name="ZIP code",
    )
    service_radius_km = models.PositiveIntegerField(
        default=25,
        validators=[MinValueValidator(1)],
    )
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    bio = models.TextField(blank=True)
    skills = models.ManyToManyField(Skill, through="WorkerSkill", related_name="workers", blank=True)

    def clean(self):
        self.city = (self.city or "").strip()
        self.zip_code = (self.zip_code or "").strip()
        errors = {}
        if self.user_id and self.user.role != User.Role.WORKER:
            errors["user"] = "A worker profile can only belong to a worker account."
        filled = (bool(self.city), bool(self.state), bool(self.zip_code))
        if any(filled) and not all(filled):
            errors["city"] = "Set city, state, and ZIP code, or leave all three empty."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.user.email


class WorkerSkill(models.Model):
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name="worker_skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="worker_skills")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["worker", "skill"], name="unique_worker_skill"),
        ]

    def __str__(self):
        return f"{self.worker} — {self.skill}"


class Availability(models.Model):
    """One row per worker per date. A row with is_available marks that the worker can be hired that day."""

    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name="availability")
    date = models.DateField()
    is_available = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["worker", "date"], name="unique_worker_availability_date"),
        ]
        ordering = ["date"]
        verbose_name_plural = "availability"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.worker} on {self.date}"
