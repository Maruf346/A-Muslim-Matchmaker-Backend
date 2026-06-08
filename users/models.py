"""
users/models.py

Models:
    User          — custom AbstractUser (email-based auth, role-based access)
    UserSettings  — per-user preferences (notifications toggle etc.)

Role matrix:
    MALE        → normal user, gender=MALE
    FEMALE      → normal user, gender=FEMALE
    WALI        → guardian role (gender set later during onboarding)
    MATCHMAKER  → admin role, limited permissions (no financial data)
    SUPERADMIN  → admin role, full permissions

Account state:
    is_active=True  + deactivated_by_user=False → normal active account
    is_active=False + deactivated_by_user=True  → self-deactivated by user
    is_active=False + deactivated_by_user=False → blocked by admin

Last active / online presence:
    last_active (DateTimeField) — updated on every authenticated request via
    LastActiveMiddleware. Used to compute "active now / 5 mins ago / 1hr ago".
    Fully independent of is_active.

Codename:
    Auto-generated at registration-complete time (after OTP verify).
    Format: MMK + zero-padded sequential number (e.g. MMK0001, MMK0042).
    Stored permanently — used as the public identity before mutual interest.
"""

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from users import serializers


# ─────────────────────────────────────────────────────────────────────────────
# Choices
# ─────────────────────────────────────────────────────────────────────────────

class UserRole(models.TextChoices):
    MALE        = "male",       "Male"
    FEMALE      = "female",     "Female"
    WALI        = "wali",       "Wali (Guardian)"
    MATCHMAKER  = "matchmaker", "Matchmaker"
    SUPERADMIN  = "superadmin", "Super Admin"


class Gender(models.TextChoices):
    MALE   = "male",   "Male"
    FEMALE = "female", "Female"


class AuthProvider(models.TextChoices):
    SELF   = "self",   "Self"
    GOOGLE = "google", "Google"
    APPLE  = "apple",  "Apple"


class SubscriptionPlan(models.TextChoices):
    FREE    = "free",    "Free"
    MONTHLY = "monthly", "Monthly"
    ANNUAL  = "annual",  "Annual"


# ─────────────────────────────────────────────────────────────────────────────
# Custom User Manager
# ─────────────────────────────────────────────────────────────────────────────

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Creates a Django superuser — mapped to SUPERADMIN role.
        Used only for the initial platform setup via manage.py createsuperuser.
        In production, superadmins are created programmatically or via admin panel.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", UserRole.SUPERADMIN)
        return self.create_user(email, password, **extra_fields)

    # ── Convenience querysets ─────────────────────────────────────────────────

    def normal_users(self):
        return self.filter(role__in=[UserRole.MALE, UserRole.FEMALE, UserRole.WALI])

    def male_users(self):
        return self.filter(role=UserRole.MALE)

    def female_users(self):
        return self.filter(role=UserRole.FEMALE)

    def wali_users(self):
        return self.filter(role=UserRole.WALI)

    def admins(self):
        return self.filter(role__in=[UserRole.MATCHMAKER, UserRole.SUPERADMIN])

    def matchmakers(self):
        return self.filter(role=UserRole.MATCHMAKER)

    def superadmins(self):
        return self.filter(role=UserRole.SUPERADMIN)


# ─────────────────────────────────────────────────────────────────────────────
# Codename Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_codename(role: str) -> str:
    """
    Generate a unique sequential codename based on role.

    Format:
        Male  → B-1, B-2, ... B-238 (no zero-padding, no fixed digit length)
        Female → S-1, S-2, ... S-460
        Wali  → W-1, W-2, ... W-99

    No fixed digit width — numbers grow naturally (B-9999, B-10000 etc.).
    Existing legacy users may have non-standard formats (e.g. B-29, S-3)
    which is fine since codename is a free CharField.

    Only generated for MALE, FEMALE, WALI roles.
    Admins (MATCHMAKER, SUPERADMIN) do not get codenames.
    """
    prefix_map = {
        UserRole.MALE:   "B",
        UserRole.FEMALE: "S",
        UserRole.WALI:   "W",
    }

    prefix = prefix_map.get(role)
    if not prefix:
        return None  # Admins get no codename

    # Find the highest existing number for this prefix
    import re
    existing = (
        User.objects
        .filter(codename__startswith=f"{prefix}-")
        .values_list("codename", flat=True)
    )

    max_num = 0
    for codename in existing:
        match = re.match(rf"^{prefix}-(\d+)$", codename)
        if match:
            max_num = max(max_num, int(match.group(1)))

    return f"{prefix}-{max_num + 1}"


# ─────────────────────────────────────────────────────────────────────────────
# Core User Model
# ─────────────────────────────────────────────────────────────────────────────

class User(AbstractUser):
    """
    Central user model for all roles: Male, Female, Wali, Matchmaker, Superadmin.

    Identity before mutual interest:
        Public-facing identity is `codename` (e.g. MMK0042).
        `first_name`, `last_name`, `profile_picture`, and contact details are hidden until
        mutual interest — enforced at the serializer level in the matches app.

    Account state:
        is_active=True  → account is usable
        is_active=False → blocked by admin OR self-deactivated
        deactivated_by_user=True → distinguishes self-deactivation from admin block

    Online presence:
        last_active is updated by LastActiveMiddleware on every authenticated
        request. Compute display string ("active now", "5 mins ago") at read
        time from this field — no separate online/offline field needed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Remove unused Django AbstractUser fields
    username   = None

    # ── Core identity ─────────────────────────────────────────────────────────
    email     = models.EmailField(unique=True, verbose_name=_("Email Address"))
    # full_name = models.CharField(max_length=150, blank=True, verbose_name=_("Full Name"))
    first_name = serializers.CharField(max_length=75)
    last_name  = serializers.CharField(max_length=75)
    codename  = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_("Codename"),
        help_text="Auto-generated public identity (e.g. MMK0042). Set at registration-complete.",
    )

    # ── Role & gender ─────────────────────────────────────────────────────────
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        verbose_name=_("Role"),
        help_text=(
            "MALE/FEMALE → set by registration endpoint. "
            "WALI → set by wali registration endpoint. "
            "MATCHMAKER/SUPERADMIN → set by superadmin only."
        ),
    )
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        null=True,
        verbose_name=_("Gender"),
        help_text=(
            "Set automatically for MALE/FEMALE roles at registration. "
            "Wali sets gender during onboarding."
        ),
    )

    # ── Contact ───────────────────────────────────────────────────────────────
    profile_picture = models.ImageField(
        upload_to="users/profile_pictures/",
        blank=True,
        null=True,
        verbose_name=_("Profile Picture"),
    )

    # ── Subscription ──────────────────────────────────────────────────────────
    subscription_plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.choices,
        default=SubscriptionPlan.FREE,
        verbose_name=_("Subscription Plan"),
    )
    subscription_start = models.DateTimeField(null=True, blank=True)
    subscription_end   = models.DateTimeField(null=True, blank=True)

    # ── Auth provider ─────────────────────────────────────────────────────────
    provider    = models.CharField(
        max_length=20,
        choices=AuthProvider.choices,
        default=AuthProvider.SELF,
        verbose_name=_("Auth Provider"),
    )
    provider_id = models.CharField(max_length=255, blank=True, null=True)

    # ── Account state ─────────────────────────────────────────────────────────
    is_active           = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=(
            "False = account is blocked (by admin) or deactivated (by user). "
            "Check deactivated_by_user to distinguish the two."
        ),
    )
    deactivated_by_user = models.BooleanField(
        default=False,
        verbose_name=_("Deactivated by User"),
        help_text=(
            "True when the user self-deactivated their account. "
            "False when blocked by admin. Only meaningful when is_active=False."
        ),
    )

    # ── Online presence ───────────────────────────────────────────────────────
    last_active = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Active"),
        help_text="Updated by LastActiveMiddleware on every authenticated request.",
    )

    # ── Device token (push notifications — future use) ────────────────────────
    device_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Device Token"),
        help_text="FCM/APNs device token for push notifications.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects        = UserManager()
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []

    # ── Role helpers ──────────────────────────────────────────────────────────
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_male(self) -> bool:
        return self.role == UserRole.MALE

    @property
    def is_female(self) -> bool:
        return self.role == UserRole.FEMALE

    @property
    def is_wali(self) -> bool:
        return self.role == UserRole.WALI

    @property
    def is_matchmaker(self) -> bool:
        return self.role == UserRole.MATCHMAKER

    @property
    def is_superadmin(self) -> bool:
        return self.role == UserRole.SUPERADMIN

    @property
    def is_admin_user(self) -> bool:
        """True for both Matchmaker and Superadmin."""
        return self.role in (UserRole.MATCHMAKER, UserRole.SUPERADMIN)

    @property
    def is_normal_user(self) -> bool:
        """True for Male, Female, and Wali."""
        return self.role in (UserRole.MALE, UserRole.FEMALE, UserRole.WALI)

    # ── Subscription helpers ──────────────────────────────────────────────────

    @property
    def is_subscribed(self) -> bool:
        """True for Monthly or Annual subscribers."""
        return self.subscription_plan in (SubscriptionPlan.MONTHLY, SubscriptionPlan.ANNUAL)

    def is_subscribed_monthly(self) -> bool:
        """True for Monthly subscribers."""
        return self.subscription_plan == SubscriptionPlan.MONTHLY
    
    def is_subscribed_annual(self) -> bool:
        """True for Annual subscribers."""
        return self.subscription_plan == SubscriptionPlan.ANNUAL
    
    @property
    def can_send_requests(self) -> bool:
        return self.is_subscribed

    @property
    def can_see_suggestions(self) -> bool:
        return self.is_subscribed

    @property
    def can_see_viewers(self) -> bool:
        return self.is_subscribed

    @property
    def has_boosted_profile(self) -> bool:
        return self.subscription_plan == SubscriptionPlan.ANNUAL

    def __str__(self):
        return f"{self.codename or self.email} ({self.role})"

    class Meta:
        verbose_name        = "User"
        verbose_name_plural = "Users"
        ordering            = ["-created_at"]


# ─────────────────────────────────────────────────────────────────────────────
# User Settings
# ─────────────────────────────────────────────────────────────────────────────

class UserSettings(models.Model):
    """
    Per-user preferences.
    Created automatically via post_save signal when a User is created.
    """

    user                  = models.OneToOneField(User, on_delete=models.CASCADE, related_name="settings")
    notification_enabled  = models.BooleanField(default=True)
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings → {self.user.email}"

    class Meta:
        verbose_name        = "User Settings"
        verbose_name_plural = "User Settings"
