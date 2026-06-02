"""
users/models.py

Models:
    User              — custom AbstractUser (email-based, role via is_staff/is_superuser)
    ArtisanProfile    — extended profile for artisans
    ClientProfile     — extended profile for clients
    Address           — saved addresses (client: multiple, artisan: one home addr)
    Referral          — referral tracking for both roles
    UserSettings      — per-user preferences (notifications toggle etc.)
"""

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


# ─────────────────────────────────────────────────────────────────────────────
# Choices
# ─────────────────────────────────────────────────────────────────────────────

class AuthProvider(models.TextChoices):
    SELF   = "self",   "Self"
    GOOGLE = "google", "Google"
    APPLE  = "apple",  "Apple"



class VerificationStatus(models.TextChoices):
    UNVERIFIED  = "unverified",  "Unverified"
    PENDING     = "pending",     "Pending Review"
    VERIFIED    = "verified",    "Verified"
    REJECTED    = "rejected",    "Rejected"


# ─────────────────────────────────────────────────────────────────────────────
# Custom User Manager
# ─────────────────────────────────────────────────────────────────────────────

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"]:
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields["is_superuser"]:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)

    # Convenience querysets
    def clients(self):
        return self.filter(is_staff=False, is_superuser=False)

    def artisans(self):
        return self.filter(is_staff=True, is_superuser=False)

    def admins(self):
        return self.filter(is_staff=True, is_superuser=True)


# ─────────────────────────────────────────────────────────────────────────────
# Core User Model
# ─────────────────────────────────────────────────────────────────────────────

class User(AbstractUser):
    """
    Role matrix (is_staff / is_superuser):
        Admin   →  True  / True
        Artisan →  True  / False
        Client  →  False / False
    """

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Remove Django defaults we don't use
    username    = None
    first_name  = None
    last_name   = None

    full_name       = models.CharField(max_length=150, blank=True)
    email           = models.EmailField(unique=True)
    phone           = PhoneNumberField(verbose_name=_("Phone Number"), blank=True, null=True)
    profile_picture = models.ImageField(upload_to="users/profile_pictures/", blank=True, null=True)
    birth_date      = models.DateField(null=True, blank=True)
    is_active       = models.BooleanField(default=True)

    # OAuth
    provider    = models.CharField(
        max_length=20, choices=AuthProvider.choices, default=AuthProvider.SELF
    )
    provider_id = models.CharField(max_length=255, blank=True, null=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    objects         = UserManager()
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []

    # ── Role helpers ──────────────────────────────────────────────────────────

    @property
    def role(self) -> str:
        if self.is_superuser:
            return "admin"
        if self.is_staff:
            return "artisan"
        return "client"

    @property
    def is_client(self) -> bool:
        return not self.is_staff and not self.is_superuser

    @property
    def is_artisan(self) -> bool:
        return self.is_staff and not self.is_superuser

    @property
    def is_admin(self) -> bool:
        return self.is_superuser

    def __str__(self):
        return f"{self.full_name or self.email} ({self.role})"

    class Meta:
        verbose_name        = "User"
        verbose_name_plural = "Users"
        ordering            = ["-created_at"]




# ─────────────────────────────────────────────────────────────────────────────
# User Settings
# ─────────────────────────────────────────────────────────────────────────────

class UserSettings(models.Model):
    """Per-user preferences — created automatically via post_save signal on User."""

    user                    = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="settings"
    )
    notification_enabled    = models.BooleanField(default=True)
    email_notifications     = models.BooleanField(default=True)
    sms_notifications       = models.BooleanField(default=False)
    language                = models.CharField(max_length=10, default="en")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "User Settings"
        verbose_name_plural = "User Settings"

    def __str__(self):
        return f"Settings for {self.user.email}"