"""
notifications/tasks.py

Celery tasks for deferred or periodic notification delivery.

To add a new periodic task:
    1. Define a @shared_task here.
    2. Register it in core/celery.py under app.conf.beat_schedule.

Current tasks:
    (none active — placeholders ready for future use)
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


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