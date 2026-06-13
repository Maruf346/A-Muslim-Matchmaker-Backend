"""
wishlists/apps.py
"""

from django.apps import AppConfig


class WishlistsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name               = "wishlists"
    verbose_name       = "Wishlists & Safety"