from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.utils import timezone

from .models import (
    Gender,
    SubscriptionPlan,
    User,
    UserRole,
    UserSettings,
    WhyLeaving,
    generate_codename,
)


class UserAdminCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "role",
            "gender",
            "subscription_plan",
            "subscription_start",
            "subscription_end",
            "provider",
            "provider_id",
            "is_active",
            "is_staff",
            "is_superuser",
        )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields did not match.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserAdminChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        help_text="Raw passwords are not stored, so there is no way to see this user's password."
    )

    class Meta:
        model = User
        fields = "__all__"

    def clean_password(self):
        return self.initial["password"]


class UserSettingsInline(admin.StackedInline):
    model = UserSettings
    extra = 0
    can_delete = False
    verbose_name_plural = "User settings"
    readonly_fields = ("created_at", "updated_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    inlines = [UserSettingsInline]

    list_display = (
        "email",
        "full_name",
        "codename",
        "role",
        "subscription_plan",
        "is_verified",
        "is_active",
        "is_staff",
        "created_at",
    )
    list_filter = (
        "role",
        "gender",
        "subscription_plan",
        "is_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_private_matchmaking_client",
        "deactivated_by_user",
        "provider",
        "created_at",
    )
    search_fields = ("email", "first_name", "last_name", "codename", "provider_id")
    ordering = ("-created_at",)
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = (
        "id",
        "password",
        "last_login",
        "date_joined",
        "last_active",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("id", "first_name", "last_name", "codename", "profile_picture")}),
        (
            "User details",
            {
                "fields": (
                    "role",
                    "gender",
                    "is_verified",
                    "is_private_matchmaking_client",
                    "is_active",
                    "deactivated_by_user",
                )
            },
        ),
        (
            "Subscription",
            {"fields": ("subscription_plan", "subscription_start", "subscription_end")},
        ),
        ("Authentication", {"fields": ("provider", "provider_id", "last_login", "date_joined")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Activity", {"fields": ("last_active", "device_token", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "role",
                    "gender",
                    "subscription_plan",
                    "subscription_start",
                    "subscription_end",
                    "provider",
                    "provider_id",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    actions = ("mark_free_plan", "mark_monthly_plan", "mark_annual_plan", "mark_verified", "mark_unverified")

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.full_name or "-"

    @admin.action(description="Change subscription to Free")
    def mark_free_plan(self, request, queryset):
        updated = queryset.update(
            subscription_plan=SubscriptionPlan.FREE,
            subscription_start=None,
            subscription_end=None,
        )
        self.message_user(request, f"{updated} user(s) moved to the Free plan.")

    @admin.action(description="Change subscription to Monthly")
    def mark_monthly_plan(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(subscription_plan=SubscriptionPlan.MONTHLY, subscription_start=now)
        self.message_user(request, f"{updated} user(s) moved to the Monthly plan.")

    @admin.action(description="Change subscription to Annual")
    def mark_annual_plan(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(subscription_plan=SubscriptionPlan.ANNUAL, subscription_start=now)
        self.message_user(request, f"{updated} user(s) moved to the Annual plan.")

    @admin.action(description="Mark selected users as verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} user(s) marked as verified.")

    @admin.action(description="Mark selected users as unverified")
    def mark_unverified(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"{updated} user(s) marked as unverified.")

    def save_model(self, request, obj, form, change):
        if obj.role == UserRole.MALE and not obj.gender:
            obj.gender = Gender.MALE
        elif obj.role == UserRole.FEMALE and not obj.gender:
            obj.gender = Gender.FEMALE

        if obj.role in (UserRole.MATCHMAKER, UserRole.SUPERADMIN):
            obj.is_staff = True

        if obj.role in (UserRole.MALE, UserRole.FEMALE, UserRole.WALI) and not obj.codename:
            obj.codename = generate_codename(role=obj.role)

        super().save_model(request, obj, form, change)


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "notification_enabled", "created_at", "updated_at")
    list_filter = ("notification_enabled", "created_at", "updated_at")
    search_fields = ("user__email", "user__first_name", "user__last_name", "user__codename")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(WhyLeaving)
class WhyLeavingAdmin(admin.ModelAdmin):
    list_display = ("id", "short_reasons", "tell_us_more",)
    search_fields = ("reasons", "tell_us_more")
    readonly_fields = ("id",)

    @admin.display(description="Reasons")
    def short_reasons(self, obj):
        if not obj.reasons:
            return "-"
        return obj.reasons[:75] + ("..." if len(obj.reasons) > 75 else "")
