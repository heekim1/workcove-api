from django.contrib import admin

from .models import Availability, Skill, WorkerProfile, WorkerSkill


class WorkerSkillInline(admin.TabularInline):
    model = WorkerSkill
    extra = 1


class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 1


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "state", "zip_code", "hourly_rate", "service_radius_km")
    search_fields = ("user__email", "user__phone")
    autocomplete_fields = ("user",)
    inlines = (WorkerSkillInline, AvailabilityInline)


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("worker", "date", "is_available")
    list_filter = ("is_available", "date")
    search_fields = ("worker__user__email",)
    autocomplete_fields = ("worker",)
