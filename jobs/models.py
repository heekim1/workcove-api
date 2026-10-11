import secrets

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models, transaction
from django.utils import timezone

from managers.models import ManagerProfile
from workers.models import US_STATES, Skill

REPLY_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class Job(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        FILLED = "filled", "Filled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    manager = models.ForeignKey(ManagerProfile, on_delete=models.CASCADE, related_name="jobs")
    work_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=2, choices=US_STATES)
    zip_code = models.CharField(
        max_length=10,
        validators=[RegexValidator(r"^\d{5}(-\d{4})?$", "Enter a 5-digit ZIP code.")],
        verbose_name="ZIP code",
    )
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name="jobs")
    headcount = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["work_date", "start_time"]

    def clean(self):
        self.city = (self.city or "").strip()
        self.zip_code = (self.zip_code or "").strip()
        errors = {}
        if not self.city:
            errors["city"] = "Enter a city."
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            errors["end_time"] = "End time must be after start time."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.skill} on {self.work_date} for {self.manager}"


def _new_reply_code():
    while True:
        code = "".join(secrets.choice(REPLY_CODE_ALPHABET) for _ in range(4))
        if not JobOffer.objects.filter(reply_code=code).exists():
            return code


class JobOffer(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CLOSED = "closed", "Closed"

    OPEN_STATUSES = (Status.PENDING, Status.SENT)

    class Channel(models.TextChoices):
        TEXT = "text", "Text"
        APP = "app", "App"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="offers")
    worker = models.ForeignKey(
        "workers.WorkerProfile",
        on_delete=models.CASCADE,
        related_name="job_offers",
    )
    reply_code = models.CharField(max_length=4, unique=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.TEXT)
    sent_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "worker"], name="unique_job_offer_worker"),
        ]
        ordering = ["-sent_at"]

    def clean(self):
        errors = {}
        if self.job_id and not self.pk and self.job.status != Job.Status.OPEN:
            errors["job"] = "Offers can only be sent for an open job."
        if self.pk:
            previous = JobOffer.objects.get(pk=self.pk).status
            if previous != self.status and previous not in self.OPEN_STATUSES:
                errors["status"] = "This offer has already been answered."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.reply_code:
            self.reply_code = _new_reply_code()
        with transaction.atomic():
            if self.job_id:
                Job.objects.select_for_update().get(pk=self.job_id)
            previous = None
            if self.pk:
                previous = JobOffer.objects.get(pk=self.pk).status
            becoming_sent = self.status == self.Status.SENT and previous != self.Status.SENT
            becoming_accepted = self.status == self.Status.ACCEPTED and previous != self.Status.ACCEPTED
            becoming_declined = self.status == self.Status.DECLINED and previous != self.Status.DECLINED
            if becoming_sent and self.sent_at is None:
                self.sent_at = timezone.now()
            if becoming_accepted:
                accepted = JobOffer.objects.filter(job_id=self.job_id, status=self.Status.ACCEPTED).count()
                if accepted >= self.job.headcount:
                    raise ValidationError({"status": "This job is already filled."})
            if (becoming_accepted or becoming_declined) and self.answered_at is None:
                self.answered_at = timezone.now()
            self.full_clean()
            super().save(*args, **kwargs)
            if becoming_accepted:
                self._close_remaining_offers_when_filled()

    def _close_remaining_offers_when_filled(self):
        accepted = JobOffer.objects.filter(job_id=self.job_id, status=self.Status.ACCEPTED).count()
        if accepted < self.job.headcount:
            return
        JobOffer.objects.filter(job_id=self.job_id, status__in=self.OPEN_STATUSES).update(
            status=self.Status.CLOSED,
            answered_at=timezone.now(),
        )
        if self.job.status == Job.Status.OPEN:
            self.job.status = Job.Status.FILLED
            Job.objects.filter(pk=self.job_id).update(status=Job.Status.FILLED)

    def __str__(self):
        return f"{self.reply_code} to {self.worker} for {self.job_id}"
