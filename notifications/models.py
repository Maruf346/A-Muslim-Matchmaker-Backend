"""
notifications/models.py

Delivery strategy (by role):
    Male  → DB record only  — mobile app polls via REST
    Female → DB record only  — mobile app polls via REST
    Wali → DB record only  — mobile app polls via REST
    Admin   → DB record + WebSocket push — real-time dashboard
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class NotificationType(models.TextChoices):
    # ── Auth / Account ────────────────────────────────────────────────────────
    WELCOME                 = "welcome",                "Welcome"
    PASSWORD_UPDATED        = "pass_updated",           "Password Updated"
    PASSWORD_CHANGED        = "pass_changed",           "Password Changed"
    ACCOUNT_VERIFIED        = "account_verified",       "Account Verified"
    ACCOUNT_SUSPENDED       = "account_suspended",      "Account Suspended"

    # ── Chat ──────────────────────────────────────────────────────────────────
    NEW_MESSAGE             = "new_message",            "New Chat Message"

    # ── Verification ──────────────────────────────────────────────────────────
    VERIFICATION_APPROVED   = "verification_approved",  "Verification Approved"
    VERIFICATION_REJECTED   = "verification_rejected",  "Verification Rejected"

    # ── Referral ──────────────────────────────────────────────────────────────
    REFERRAL_BONUS          = "referral_bonus",         "Referral Bonus Earned"

    # ── Admin-only ────────────────────────────────────────────────────────────
    NEW_USER                = "new_user",               "New User Joined"


class NotificationPriority(models.TextChoices):
    LOW     = "low",    "Low"
    NORMAL  = "normal", "Normal"
    HIGH    = "high",   "High"
    URGENT  = "urgent", "Urgent"


class Notification(models.Model):
    """
    Single table for all roles.

    Delivery column (websocket_pushed):
        False for client/artisan — they poll via REST.
        True/False for admin    — reflects whether the WS push succeeded.
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")

    notification_type = models.CharField(max_length=60, choices=NotificationType.choices, db_index=True)
    title             = models.CharField(max_length=255)
    body              = models.TextField()
    data              = models.JSONField(default=dict, blank=True)  # arbitrary context payload
    priority          = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL,
    )

    # Delivery tracking — only meaningful for admin WebSocket channel.
    # For client/artisan this stays False (they use REST).
    websocket_pushed = models.BooleanField(
        default=False,
        help_text="True when a real-time WebSocket push was attempted (admin only).",
    )
    websocket_success = models.BooleanField(
        default=False,
        help_text="True when the WebSocket push was confirmed sent (admin only).",
    )

    # Read tracking — used by all roles
    is_read  = models.BooleanField(default=False, db_index=True)
    read_at  = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        return f"{self.title} → {self.user.email}"
