"""
subscriptions/tasks.py
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="subscriptions.expire_lapsed_subscriptions", ignore_result=True)
def expire_lapsed_subscriptions():
    from .services import EntitlementService

    changed = EntitlementService.expire_lapsed_users()
    logger.info("expire_lapsed_subscriptions: %s users changed plan", changed)
