"""Shared formatting and domain helpers across apps."""

from django.utils import timezone


def format_last_active_display(user) -> str | None:
    """
    Format a user's last_active timestamp cleanly:
    - Within 5 minutes -> "Active now"
    - Under 24 hours   -> "Active <N> hr(s) ago"
    - 24+ hours        -> "Active <N> day(s) ago"
    """
    if not user or not getattr(user, "last_active", None):
        return None
    delta = timezone.now() - user.last_active
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 300:
        return "Active now"
    if seconds < 86400:
        hours = max(1, seconds // 3600)
        return f"Active {hours} hr{'s' if hours != 1 else ''} ago"
    days = seconds // 86400
    return f"Active {days} day{'s' if days != 1 else ''} ago"

