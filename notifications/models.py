"""
notifications/models.py

Delivery strategy:
    Male / Female / Wali → DB record only — mobile app polls via REST endpoints.
    Admin (Matchmaker / Superadmin) → DB record + real-time WebSocket push.

Notification types cover all AMM domain events:
    auth, connection requests, matches, photo requests, wali requests,
    unlock flow, chat messages, private matchmaking, and admin-specific alerts.
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Choices
# ─────────────────────────────────────────────────────────────────────────────

class NotificationType(models.TextChoices):
    # ── Auth / Account ────────────────────────────────────────────────────────
    WELCOME                         = "welcome",                        "Welcome"
    PASSWORD_CHANGED                = "pass_changed",                   "Password Changed"
    ACCOUNT_SUSPENDED               = "account_suspended",              "Account Suspended"
    ACCOUNT_BLOCKED                 = "account_blocked",                "Account Blocked"
    PROFILE_APPROVED                = "profile_approved",               "Profile Approved"

    # ── Connection Requests ───────────────────────────────────────────────────
    CONNECTION_REQUEST_RECEIVED     = "connection_request_received",    "Connection Request Received"
    CONNECTION_REQUEST_ACCEPTED     = "connection_request_accepted",    "Connection Request Accepted"
    CONNECTION_REQUEST_DECLINED     = "connection_request_declined",    "Connection Request Declined"
    CONNECTION_REQUEST_CANCELLED    = "connection_request_cancelled",   "Connection Request Cancelled"

    # ── Matches ───────────────────────────────────────────────────────────────
    MATCH_CREATED                   = "match_created",                  "Match Created"

    # ── Photo Requests ────────────────────────────────────────────────────────
    PHOTO_REQUEST_RECEIVED          = "photo_request_received",         "Photo Request Received"
    PHOTO_REQUEST_APPROVED          = "photo_request_approved",         "Photo Request Approved"
    PHOTO_REQUEST_DECLINED          = "photo_request_declined",         "Photo Request Declined"

    # ── Wali Requests ─────────────────────────────────────────────────────────
    WALI_REQUEST_RECEIVED           = "wali_request_received",          "Wali Request Received"
    WALI_REQUEST_APPROVED           = "wali_request_approved",          "Wali Request Approved"
    WALI_REQUEST_DECLINED           = "wali_request_declined",          "Wali Request Declined"

    # ── Unlock Flow (post-wali stage) ─────────────────────────────────────────
    UNLOCK_REQUEST_RECEIVED         = "unlock_request_received",        "Unlock Request Received"

    # ── Chat ──────────────────────────────────────────────────────────────────
    NEW_MESSAGE                     = "new_message",                    "New Chat Message"

    # ── Private Matchmaking ───────────────────────────────────────────────────
    PRIVATE_MATCHMAKING_REQUESTED   = "private_matchmaking_requested",  "Private Matchmaking Requested"
    PRIVATE_MATCHMAKING_CONFIRMED   = "private_matchmaking_confirmed",  "Private Matchmaking Confirmed"

    # ── Admin-only alerts ─────────────────────────────────────────────────────
    NEW_USER_JOINED                 = "new_user_joined",                "New User Joined"


class NotificationPriority(models.TextChoices):
    LOW     = "low",    "Low"
    NORMAL  = "normal", "Normal"
    HIGH    = "high",   "High"
    URGENT  = "urgent", "Urgent"


# ─────────────────────────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────────────────────────

class Notification(models.Model):
    """
    Single notification table shared across all user roles.

    Delivery notes:
        • Male / Female / Wali: DB record only — clients poll via REST.
        • Admin: DB record + WebSocket push attempted immediately.
          `websocket_pushed` / `websocket_success` track delivery status.
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=60,
        choices=NotificationType.choices,
        db_index=True,
    )
    title    = models.CharField(max_length=255)
    body     = models.TextField()
    data     = models.JSONField(default=dict, blank=True)  # arbitrary context payload
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL,
    )

    # Delivery tracking — meaningful only for admin WebSocket channel.
    # Stays False for Male / Female / Wali (REST polling only).
    websocket_pushed = models.BooleanField(
        default=False,
        help_text="True when a real-time WebSocket push was attempted (admin only).",
    )
    websocket_success = models.BooleanField(
        default=False,
        help_text="True when the WebSocket push was confirmed sent (admin only).",
    )

    # Read tracking — used by all roles
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        return f"[{self.notification_type}] {self.title} → {self.user.email}"