from django.contrib import admin

from .models import ManagerProfile


@admin.register(ManagerProfile)
class ManagerProfileAdmin(admin.ModelAdmin):
    list_display = ("business_name", "user", "city", "state", "zip_code")
    search_fields = ("business_name", "user__email", "user__phone")
    autocomplete_fields = ("user",)
