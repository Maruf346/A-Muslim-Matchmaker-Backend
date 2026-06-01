"""
notifications/tasks.py

Celery tasks for periodic / deferred notification delivery.
Register new tasks here and wire them into core/celery.py beat_schedule.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


# @shared_task(name="notifications.check_user_milestones")
# def check_user_milestones():
#     """Run periodically; notify admins when the platform hits notable user counts."""
#     from notifications.services import NotificationTemplates

#     milestones = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000]
#     total = User.objects.filter(is_staff=False, is_superuser=False).count()
#     if total in milestones:
#         NotificationTemplates.milestone_achieved("clients", total)
#         logger.info("Milestone hit: %d clients", total)

