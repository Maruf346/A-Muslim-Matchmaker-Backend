"""
users/signals.py

Django signals for the users app.

Signals registered:
    post_save → User:
        - Creates UserSettings on new user creation (if not already exists)

Wire up in users/apps.py — see UsersConfig.ready().
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    """
    Automatically create a UserSettings record for every new User.
    Skips if settings already exist (e.g. created explicitly in services.py
    for OAuth users to avoid duplicate creation).
    """
    if created:
        from users.models import UserSettings
        UserSettings.objects.get_or_create(user=instance)
        logger.debug("UserSettings created for user %s", instance.email)
