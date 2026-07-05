"""
matchmaking/models.py

Model:
    PrivateMatchmakingRequest — user requests to become a private matchmaking
    client. Admin/Matchmaker approves or declines. On approval, the user's
    is_private_matchmaking_client flag is set to True automatically.

One active request per user at a time (enforced in the service layer).
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class RequestStatus(models.TextChoices):
    PENDING  = "pending",  "Pending"
    APPROVED = "approved", "Approved"
    DECLINED = "declined", "Declined"


def generate_request_id() -> str:
    import re
    existing = PrivateMatchmakingRequest.objects.filter(
        request_id__startswith="RQ-"
    ).values_list("request_id", flat=True)
    max_num = 0
    for rid in existing:
        m = re.match(r"^RQ-(\d+)$", rid)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"RQ-{max_num + 1}"


class PrivateMatchmakingRequest(models.Model):
    """
    A user's request to be onboarded as a private matchmaking client.
    Admin reviews, then approves or declines.
    On approval: user.is_private_matchmaking_client = True is set by the service.
    """

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_id = models.CharField(max_length=20, unique=True, blank=True, null=True)

    user   = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="private_matchmaking_requests",
    )
    status = models.CharField(
        max_length=20, choices=RequestStatus.choices, default=RequestStatus.PENDING,
        db_index=True,
    )

    # Admin fields
    admin_notes  = models.TextField(blank=True, null=True,
        help_text="Optional note from admin — visible to the user.")
    reviewed_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pm_requests_reviewed",
    )
    reviewed_at  = models.DateTimeField(null=True, blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Private Matchmaking Request"
        verbose_name_plural = "Private Matchmaking Requests"
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.request_id or self.id} | {self.user.codename} | {self.status}"