"""
notifications/services.py

Delivery strategy:
    Male / Female / Wali → DB record only. Mobile app polls REST endpoints.
    Admin (Matchmaker / Superadmin) → DB record + real-time WebSocket push.

Usage:
    Never call NotificationService directly from views or other apps.
    Always go through NotificationTemplates — one method per domain event.

Example:
    from notifications.services import NotificationTemplates
    NotificationTemplates.connection_request_received(receiver=user, sender=other_user)
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import *

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Admin role check helper
# ─────────────────────────────────────────────────────────────────────────────

def _is_admin(user) -> bool:
    """Returns True for both Matchmaker and Superadmin roles."""
    return getattr(user, "role", None) in ("matchmaker", "superadmin")


# ─────────────────────────────────────────────────────────────────────────────
# Low-level engine — internal use only
# ─────────────────────────────────────────────────────────────────────────────

class NotificationService:
    """
    Core dispatcher — not called directly from outside this module.
    Route all notification triggers through NotificationTemplates instead.

    Routing logic (automatic, resolved via user.role):
        Male / Female / Wali → DB write only
        Matchmaker / Superadmin → DB write + WebSocket push
    """

    @staticmethod
    def send(
        user,
        notification_type: str,
        title: str,
        body: str,
        data: dict = None,
        priority: str = NotificationPriority.NORMAL,
    ) -> "Notification | None":
        """
        Persist a Notification and dispatch it appropriately.

        Returns:
            The created Notification instance, or None if notifications are
            disabled for this user.
        """
        # Respect per-user notification preference (if the setting exists)
        if hasattr(user, "settings") and not user.settings.notification_enabled:
            logger.info("Notifications disabled for %s — skipped.", user.email)
            return None

        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            priority=priority,
        )

        if _is_admin(user):
            # Admin gets an additional real-time WebSocket push
            ws_ok = NotificationService._push_websocket(
                user_id=str(user.id),
                notification_id=str(notification.id),
                notification_type=notification_type,
                title=title,
                body=body,
                data=data or {},
                priority=priority,
            )
            notification.websocket_pushed  = True
            notification.websocket_success = ws_ok
            notification.save(update_fields=["websocket_pushed", "websocket_success"])
            logger.info(
                "Admin notification → %s | type=%s | ws_ok=%s",
                user.email, notification_type, ws_ok,
            )
        else:
            logger.info(
                "Notification saved → %s | type=%s | role=%s (REST polling)",
                user.email, notification_type, getattr(user, "role", "unknown"),
            )

        return notification

    # ── WebSocket push — admin dashboard only ─────────────────────────────────

    @staticmethod
    def _push_websocket(
        user_id: str,
        notification_id: str,
        notification_type: str,
        title: str,
        body: str,
        data: dict,
        priority: str,
    ) -> bool:
        """Push to the admin's open WebSocket channel. Returns True on success."""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}",
                {
                    "type":              "notification_message",  # maps to consumer method
                    "notification_id":   notification_id,
                    "notification_type": notification_type,
                    "title":             title,
                    "body":              body,
                    "data":              data,
                    "priority":          priority,
                    "timestamp":         timezone.now().isoformat(),
                },
            )
            return True
        except Exception as exc:
            logger.error("WebSocket push failed for user %s: %s", user_id, exc)
            return False

    # ── Broadcast helpers ─────────────────────────────────────────────────────

    @staticmethod
    def send_to_all_admins(
        notification_type: str,
        title: str,
        body: str,
        data: dict = None,
    ) -> None:
        """Send a notification to every active admin (Matchmaker + Superadmin)."""
        admins = User.objects.filter(
            role__in=["matchmaker", "superadmin"],
            is_active=True,
        )
        for admin in admins:
            NotificationService.send(
                user=admin,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
            )


# ─────────────────────────────────────────────────────────────────────────────
# High-level domain templates — the ONLY public interface for other apps
# ─────────────────────────────────────────────────────────────────────────────

class NotificationTemplates:
    """
    One static method per AMM domain event.

    Import and call these from views, signals, or Celery tasks — never
    call NotificationService directly from outside this file.

    Example:
        from notifications.services import NotificationTemplates
        NotificationTemplates.welcome(user)
    """

    # ── Auth / Account ────────────────────────────────────────────────────────

    @staticmethod
    def welcome(user) -> "Notification | None":
        """Sent immediately after successful email verification."""
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.WELCOME,
            title="Welcome to A Muslim Matchmaker 🌙",
            body=f"As-salamu alaykum {user.full_name or user.email}! Your account is ready. Complete your profile to get started.",
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def password_changed(user) -> "Notification | None":
        """Sent after a successful password change or reset."""
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.PASSWORD_CHANGED,
            title="Password Changed",
            body="Your AMM password was changed successfully. If this wasn't you, contact support immediately.",
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def account_blocked(user, reason: str = "") -> "Notification | None":
        """Sent when an admin blocks the user's account."""
        body = "Your account has been blocked by our team."
        if reason:
            body += f" Reason: {reason}"
        body += " Please contact support for assistance."
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.ACCOUNT_BLOCKED,
            title="Account Blocked",
            body=body,
            priority=NotificationPriority.URGENT,
        )

    @staticmethod
    def profile_approved(user) -> "Notification | None":
        """Sent when admin approves a user's profile."""
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.PROFILE_APPROVED,
            title="Profile Approved ✅",
            body="Your profile has been reviewed and approved. You can now be seen by other members.",
            priority=NotificationPriority.HIGH,
        )

    # ── Connection Requests ───────────────────────────────────────────────────

    @staticmethod
    def connection_request_received(receiver, sender) -> "Notification | None":
        """Sent to the receiver when someone sends them a connection request."""
        return NotificationService.send(
            user=receiver,
            notification_type=NotificationType.CONNECTION_REQUEST_RECEIVED,
            title="New Connection Request",
            body=f"{sender.codename} has sent you a connection request.",
            data={"sender_codename": sender.codename, "sender_id": str(sender.id)},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def connection_request_accepted(sender, receiver) -> "Notification | None":
        """Sent to the original sender when their request is accepted."""
        return NotificationService.send(
            user=sender,
            notification_type=NotificationType.CONNECTION_REQUEST_ACCEPTED,
            title="Connection Request Accepted 🤝",
            body=f"{receiver.codename} has accepted your connection request. You are now matched!",
            data={"receiver_codename": receiver.codename, "receiver_id": str(receiver.id)},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def connection_request_declined(sender, receiver) -> "Notification | None":
        """Sent to the original sender when their request is declined."""
        return NotificationService.send(
            user=sender,
            notification_type=NotificationType.CONNECTION_REQUEST_DECLINED,
            title="Connection Request Declined",
            body=f"{receiver.codename} has declined your connection request.",
            data={"receiver_codename": receiver.codename},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def connection_request_cancelled(receiver, sender) -> "Notification | None":
        """Sent to the receiver when the sender cancels their pending request."""
        return NotificationService.send(
            user=receiver,
            notification_type=NotificationType.CONNECTION_REQUEST_CANCELLED,
            title="Connection Request Cancelled",
            body=f"{sender.codename} has cancelled their connection request.",
            data={"sender_codename": sender.codename},
            priority=NotificationPriority.NORMAL,
        )

    # ── Matches ───────────────────────────────────────────────────────────────

    @staticmethod
    def match_created(user, match_id: str) -> "Notification | None":
        """
        Sent to both users when a match is created.
        Call this twice — once per user in the match.
        """
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.MATCH_CREATED,
            title="You Have a New Match! 🌹",
            body="A mutual interest has been established. You can now view each other's full profiles.",
            data={"match_id": match_id},
            priority=NotificationPriority.HIGH,
        )

    # ── Photo Requests ────────────────────────────────────────────────────────

    @staticmethod
    def photo_request_received(receiver, requester, match_id: str) -> "Notification | None":
        """Sent to the receiver when their match requests to view photos again."""
        return NotificationService.send(
            user=receiver,
            notification_type=NotificationType.PHOTO_REQUEST_RECEIVED,
            title="Photo View Request",
            body=f"{requester.codename} is requesting to view your photos again.",
            data={"requester_codename": requester.codename, "match_id": match_id},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def photo_request_approved(requester, match_id: str) -> "Notification | None":
        """Sent to the requester when the photo request is approved."""
        return NotificationService.send(
            user=requester,
            notification_type=NotificationType.PHOTO_REQUEST_APPROVED,
            title="Photo Request Approved 📷",
            body="Your photo view request has been approved. You can now view the photos.",
            data={"match_id": match_id},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def photo_request_declined(requester, match_id: str) -> "Notification | None":
        """Sent to the requester when the photo request is declined."""
        return NotificationService.send(
            user=requester,
            notification_type=NotificationType.PHOTO_REQUEST_DECLINED,
            title="Photo Request Declined",
            body="Your photo view request has been declined.",
            data={"match_id": match_id},
            priority=NotificationPriority.NORMAL,
        )

    # ── Wali Requests ─────────────────────────────────────────────────────────

    @staticmethod
    def wali_request_received(receiver, requester, match_id: str) -> "Notification | None":
        """Sent to the receiver when their match sends a wali request."""
        return NotificationService.send(
            user=receiver,
            notification_type=NotificationType.WALI_REQUEST_RECEIVED,
            title="Wali Request Received",
            body=f"{requester.codename} has requested to proceed to the Wali stage.",
            data={"requester_codename": requester.codename, "match_id": match_id},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def wali_request_approved(requester, match_id: str) -> "Notification | None":
        """Sent to the requester when the wali request is approved."""
        return NotificationService.send(
            user=requester,
            notification_type=NotificationType.WALI_REQUEST_APPROVED,
            title="Wali Request Approved 🤲",
            body="Your Wali request has been approved. Wali details are now visible.",
            data={"match_id": match_id},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def wali_request_declined(requester, match_id: str) -> "Notification | None":
        """Sent to the requester when the wali request is declined."""
        return NotificationService.send(
            user=requester,
            notification_type=NotificationType.WALI_REQUEST_DECLINED,
            title="Wali Request Declined",
            body="Your Wali request has been declined.",
            data={"match_id": match_id},
            priority=NotificationPriority.NORMAL,
        )

    # ── Unlock Flow ───────────────────────────────────────────────────────────

    @staticmethod
    def unlock_request_received(receiver, requester, match_id: str) -> "Notification | None":
        """
        Sent to the other party when a user initiates an unlock from the Wali stage.
        Informs them that the other side wants to end the connection.
        """
        return NotificationService.send(
            user=receiver,
            notification_type=NotificationType.UNLOCK_REQUEST_RECEIVED,
            title="Connection Unlock Requested",
            body=f"{requester.codename} has requested to unlock and end the current connection.",
            data={"requester_codename": requester.codename, "match_id": match_id},
            priority=NotificationPriority.URGENT,
        )

    # ── Chat ──────────────────────────────────────────────────────────────────

    @staticmethod
    def new_message(receiver, sender_name: str, room_id: str) -> "Notification | None":
        """
        Sent when a new chat message arrives.
        Used for both user→admin and admin→user directions.
        """
        return NotificationService.send(
            user=receiver,
            notification_type=NotificationType.NEW_MESSAGE,
            title="New Message",
            body=f"You have a new message from {sender_name}.",
            data={"room_id": room_id, "sender_name": sender_name},
            priority=NotificationPriority.NORMAL,
        )

    # ── Private Matchmaking ───────────────────────────────────────────────────

    @staticmethod
    def private_matchmaking_requested(user, request_id: str) -> "Notification | None":
        """Sent to admins when a user submits a private matchmaking request."""
        return NotificationService.send_to_all_admins(
            notification_type=NotificationType.PRIVATE_MATCHMAKING_REQUESTED,
            title="New Private Matchmaking Request",
            body=f"{user.codename} has submitted a private matchmaking and consultation request.",
            data={"user_id": str(user.id), "user_codename": user.codename, "request_id": request_id},
        )

    @staticmethod
    def private_matchmaking_confirmed(user, request_id: str) -> "Notification | None":
        """Sent to the user when admin confirms their private matchmaking request."""
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.PRIVATE_MATCHMAKING_CONFIRMED,
            title="Consultation Confirmed ✅",
            body="Your private matchmaking consultation has been confirmed. Our team will be in touch.",
            data={"request_id": request_id},
            priority=NotificationPriority.HIGH,
        )

    # ── Admin-only alerts ─────────────────────────────────────────────────────

    @staticmethod
    def new_user_joined(new_user) -> None:
        """Broadcast to all admins when a new user completes registration."""
        role_display = getattr(new_user, "role", "user").capitalize()
        NotificationService.send_to_all_admins(
            notification_type=NotificationType.NEW_USER_JOINED,
            title=f"New {role_display} Registered",
            body=f"{new_user.full_name or new_user.email} ({new_user.codename}) just joined AMM.",
            data={"user_id": str(new_user.id), "codename": new_user.codename, "role": new_user.role},
        )