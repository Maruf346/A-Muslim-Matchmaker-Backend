"""
users/middleware.py

LastActiveMiddleware:
    Updates User.last_active on every authenticated API request.
    Uses Redis to throttle DB writes — updates the DB at most once every
    2 minutes per user to avoid hammering the database on every request.

    Cache key: last_active_updated:<user_id>
    TTL:       120 seconds (configurable via LAST_ACTIVE_UPDATE_INTERVAL)

Usage:
    Add to MIDDLEWARE in settings.py, AFTER AuthenticationMiddleware:

        MIDDLEWARE = [
            ...
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'users.middleware.LastActiveMiddleware',
            ...
        ]
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# How often (in seconds) we write last_active to DB per user.
# Between writes, Redis holds the "already updated" flag to skip the DB write.
LAST_ACTIVE_UPDATE_INTERVAL = getattr(settings, "LAST_ACTIVE_UPDATE_INTERVAL", 120)


class LastActiveMiddleware:
    """
    Lightweight middleware that keeps User.last_active current.

    Only fires for authenticated requests (JWT-authenticated users).
    Skips: unauthenticated requests, Django admin, schema/docs endpoints.
    """

    # Paths to skip — avoids noise from schema/docs polling
    _SKIP_PATHS = ("/api/schema/", "/api/docs/", "/api/redoc/", "/admin/", "/health/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only run after the response is built (user is resolved by then)
        self._update_last_active(request)

        return response

    def _update_last_active(self, request) -> None:
        # Skip non-API and schema/docs paths
        path = request.path
        if any(path.startswith(skip) for skip in self._SKIP_PATHS):
            return

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return

        cache_key = f"last_active_updated:{user.id}"

        # If we've already written within the interval, skip the DB write
        if cache.get(cache_key):
            return

        try:
            # Update DB
            type(user).objects.filter(pk=user.pk).update(last_active=timezone.now())
            # Set flag in Redis to throttle next write
            cache.set(cache_key, True, LAST_ACTIVE_UPDATE_INTERVAL)
        except Exception as exc:
            logger.error("LastActiveMiddleware: failed to update last_active for user %s: %s", user.id, exc)
