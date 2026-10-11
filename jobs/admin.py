from django.contrib import admin, messages

from .models import Job, JobOffer
from .services import OfferSendError, send_offer, send_pending_offers


@admin.action(description="Send selected offers by SMS")
def send_selected_offers(modeladmin, request, queryset):
    sent = 0
    for offer in queryset:
        try:
            send_offer(offer)
        except OfferSendError as exc:
            modeladmin.message_user(request, f"{offer.reply_code}: {exc.detail}", level=messages.ERROR)
        else:
            sent += 1
    if sent:
        noun = "offer" if sent == 1 else "offers"
        modeladmin.message_user(request, f"Sent {sent} {noun}.")


@admin.action(description="Send pending offers for selected jobs")
def send_offers_for_jobs(modeladmin, request, queryset):
    sent = 0
    for job in queryset:
        delivered, failed = send_pending_offers(job)
        sent += len(delivered)
        for offer, exc in failed:
            modeladmin.message_user(request, f"{offer.reply_code}: {exc.detail}", level=messages.ERROR)
    if sent:
        noun = "offer" if sent == 1 else "offers"
        modeladmin.message_user(request, f"Sent {sent} {noun}.")


class JobOfferInline(admin.TabularInline):
    model = JobOffer
    extra = 0
    readonly_fields = ("reply_code", "sent_at", "answered_at")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "work_date",
        "skill",
        "manager",
        "city",
        "state",
        "zip_code",
        "headcount",
        "hourly_rate",
        "status",
    )
    list_filter = ("status", "state", "work_date")
    search_fields = ("city", "manager__business_name", "skill__name")
    autocomplete_fields = ("manager", "skill")
    date_hierarchy = "work_date"
    inlines = (JobOfferInline,)
    actions = (send_offers_for_jobs,)


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = ("reply_code", "job", "worker", "channel", "status", "sent_at", "answered_at")
    list_filter = ("status",)
    search_fields = ("reply_code", "worker__user__email", "job__manager__business_name")
    autocomplete_fields = ("job", "worker")
    readonly_fields = ("reply_code", "sent_at", "answered_at")
    actions = (send_selected_offers,)
