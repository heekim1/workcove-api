from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .consent import client_ip, has_active_sms_consent, record_sms_consent, revoke_sms_consent
from .models import SmsConsent, User


class AccountUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "phone", "role")


class AccountUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = (
            "email",
            "phone",
            "role",
            "sms_opt_in",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )


class SmsConsentInline(admin.TabularInline):
    model = SmsConsent
    extra = 0
    can_delete = False
    readonly_fields = ("phone_number", "opted_in_at", "ip_address", "terms_version", "revoked_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AccountUserChangeForm
    add_form = AccountUserCreationForm
    ordering = ("email",)
    list_display = ("email", "phone", "role", "sms_opt_in", "is_staff", "is_active")
    search_fields = ("email", "phone")
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("last_login", "date_joined")
    inlines = (SmsConsentInline,)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("phone", "role", "sms_opt_in")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "phone", "role", "password1", "password2"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.sms_opt_in and not has_active_sms_consent(obj):
            record_sms_consent(obj, client_ip(request))
        elif not obj.sms_opt_in and has_active_sms_consent(obj):
            revoke_sms_consent(obj)
