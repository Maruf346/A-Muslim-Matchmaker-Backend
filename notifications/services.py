"""
notifications/services.py

Delivery strategy:
    Client  → Notification row written to DB. Mobile app polls REST endpoints.
    Artisan → Same as client.
    Admin   → Notification row written to DB + real-time WebSocket push.

No FCM. No third-party push. Simple and reliable.
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
# Low-level notification engine
# ─────────────────────────────────────────────────────────────────────────────

class NotificationService:
    """
    Core dispatcher. Call via NotificationTemplates — don't call this directly
    from views or other apps.

    Routing logic (automatic, based on user.role):
        client / artisan → DB write only
        admin            → DB write + WebSocket push
    """

    @staticmethod
    def send_notification(
        user,
        notification_type: str,
        title: str,
        body: str,
        data: dict = None,
        priority: str = NotificationPriority.NORMAL,
    ) -> "Notification | None":
        """
        Create a persisted Notification and dispatch it appropriately.
        Returns the Notification instance, or None if the user has disabled notifications.
        """
        # Respect per-user notification preference
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

        # Admins get a real-time WebSocket push on top of the DB record
        if user.is_superuser:
            ws_ok = NotificationService._push_websocket(
                user_id=str(user.id),
                notification_id=str(notification.id),
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
                priority=priority,
            )
            notification.websocket_pushed  = True
            notification.websocket_success = ws_ok
            notification.save(update_fields=["websocket_pushed", "websocket_success"])

            logger.info(
                "Admin notification → %s | type=%s | WS=%s",
                user.email, notification_type, ws_ok,
            )
        else:
            logger.info(
                "Notification saved → %s | type=%s | role=%s (REST polling)",
                user.email, notification_type, user.role,
            )

        return notification

    # ── WebSocket — admin only ────────────────────────────────────────────────

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
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}",
                {
                    "type":              "notification_message",   # maps to consumer method
                    "notification_id":   notification_id,
                    "notification_type": notification_type,
                    "title":             title,
                    "body":              body,
                    "data":              data or {},
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
    def send_to_admins(notification_type: str, title: str, body: str, data: dict = None):
        """Send to every active admin (DB + WebSocket for each)."""
        admins = User.objects.filter(is_superuser=True, is_active=True)
        for admin in admins:
            NotificationService.send_notification(
                user=admin,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
            )


# ─────────────────────────────────────────────────────────────────────────────
# High-level domain templates
# ─────────────────────────────────────────────────────────────────────────────

class NotificationTemplates:
    """
    One static method per domain event — the only public interface other apps
    should use to trigger notifications.
    """

    # ── Auth / Account ────────────────────────────────────────────────────────

    @staticmethod
    def welcome(user):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.WELCOME,
            title="Welcome to FixGo! 🎉",
            body=f"Hi {user.full_name or user.email}, your account is ready. Let's get started!",
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def password_changed(user):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.PASSWORD_CHANGED,
            title="Password Changed",
            body="Your FixGo password was changed. If this wasn't you, contact support immediately.",
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def account_suspended(user, reason: str = ""):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.ACCOUNT_SUSPENDED,
            title="Account Suspended",
            body=f"Your FixGo account has been suspended. {reason}".strip(),
            priority=NotificationPriority.URGENT,
        )


    # ── Payments ──────────────────────────────────────────────────────────────

    @staticmethod
    def payment_successful(client, booking, amount):
        return NotificationService.send_notification(
            user=client,
            notification_type=NotificationType.PAYMENT_SUCCESSFUL,
            title="Payment Successful 💳",
            body=f"Your payment of ${amount:.2f} for booking #{booking.booking_id} was processed successfully.",
            data={"booking_id": str(booking.id), "amount": str(amount)},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def payment_failed(client, booking):
        return NotificationService.send_notification(
            user=client,
            notification_type=NotificationType.PAYMENT_FAILED,
            title="Payment Failed ❌",
            body=f"We couldn't process your payment for booking #{booking.booking_id}. Please try again.",
            data={"booking_id": str(booking.id)},
            priority=NotificationPriority.URGENT,
        )

    @staticmethod
    def payout_processed(artisan, amount):
        return NotificationService.send_notification(
            user=artisan,
            notification_type=NotificationType.PAYOUT_PROCESSED,
            title="Payout Processed 💸",
            body=f"${amount:.2f} has been sent to your bank account and will arrive within 2 business days.",
            data={"amount": str(amount)},
            priority=NotificationPriority.HIGH,
        )

    # ── Reviews ───────────────────────────────────────────────────────────────

    @staticmethod
    def new_review(artisan, review):
        return NotificationService.send_notification(
            user=artisan,
            notification_type=NotificationType.NEW_REVIEW,
            title="New Review Received ⭐",
            body=f"You received a {review.rating}-star review. Keep up the great work!",
            data={"review_id": str(review.id)},
            priority=NotificationPriority.NORMAL,
        )

    # ── Verification ──────────────────────────────────────────────────────────

    @staticmethod
    def verification_approved(artisan):
        return NotificationService.send_notification(
            user=artisan,
            notification_type=NotificationType.VERIFICATION_APPROVED,
            title="Profile Verified ✅",
            body="Congratulations! Your identity has been verified. You now have a Verified badge.",
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def verification_rejected(artisan, reason: str = ""):
        return NotificationService.send_notification(
            user=artisan,
            notification_type=NotificationType.VERIFICATION_REJECTED,
            title="Verification Failed",
            body=f"We couldn't verify your identity. {reason} Please re-submit your documents.".strip(),
            priority=NotificationPriority.HIGH,
        )

    
    # ── Admin ─────────────────────────────────────────────────────────────────

    @staticmethod
    def new_user_joined(new_user):
        return NotificationService.send_to_admins(
            notification_type=NotificationType.NEW_USER,
            title="New Client Registered",
            body=f"{new_user.full_name or new_user.email} just joined FixGo as a client.",
            data={"user_id": str(new_user.id)},
        )

    
    @staticmethod
    def milestone_achieved(milestone_type: str, count: int):
        return NotificationService.send_to_admins(
            notification_type=NotificationType.MILESTONE_ACHIEVED,
            title="🏆 Milestone Achieved!",
            body=f"FixGo has reached {count} {milestone_type}!",
            data={"milestone_type": milestone_type, "count": str(count)},
        )