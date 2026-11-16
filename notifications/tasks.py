"""
notifications/tasks.py

Celery tasks for deferred or periodic notification delivery.

To add a new periodic task:
    1. Define a @shared_task here.
    2. Register it in core/celery.py under app.conf.beat_schedule.

Current tasks:
    notifications.send_push — deliver a saved Notification to the user's
    phones through Firebase Cloud Messaging (see notifications/push.py).
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    name="notifications.send_push",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    ignore_result=True,
)
def send_push(notification_id: str):
    """Push one Notification to every registered device of its user."""
    from .models import Notification
    from .push import send_to_user

    notification = (
        Notification.objects.select_related("user")
        .filter(id=notification_id)
        .first()
    )
    if notification is None:
        return
    data = dict(notification.data or {})
    data["notification_id"] = str(notification.id)
    data["notification_type"] = notification.notification_type
    sent = send_to_user(notification.user, notification.title, notification.body, data)
    logger.info(
        "Push %s → %s (%d device(s))",
        notification.notification_type, notification.user.email, sent,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Example: send a deferred notification asynchronously via Celery
# ─────────────────────────────────────────────────────────────────────────────

# @shared_task(name="notifications.send_deferred_notification")
# def send_deferred_notification(user_id: str, notification_type: str, title: str, body: str, data: dict = None):
#     """
#     Send a single notification asynchronously.
#     Useful when you want to defer delivery without blocking the request cycle.
#
#     Usage:
#         send_deferred_notification.delay(
#             user_id=str(user.id),
#             notification_type=NotificationType.WELCOME,
#             title="Welcome!",
#             body="Your account is ready.",
#         )
#     """
#     from notifications.services import NotificationService
#     try:
#         user = User.objects.get(id=user_id)
#         NotificationService.send(
#             user=user,
#             notification_type=notification_type,
#             title=title,
#             body=body,
#             data=data or {},
#         )
#         logger.info("Deferred notification sent to user %s", user_id)
#     except User.DoesNotExist:
#         logger.error("send_deferred_notification: user %s not found", user_id)