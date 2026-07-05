"""
private_matches/models.py

Model:
    PrivateMatchSuggestion — matchmaker pushes a prospect's profile to a
    private matchmaking client. Sequential flow: client reviews first,
    then prospect is notified only if client says YES.

Status flow:
    PENDING_CLIENT_REVIEW
        → CLIENT_DECLINED  (final — prospect never notified)
        → SENT_TO_PROSPECT
            → PROSPECT_ACCEPTED  (matchmaker takes over via chat)
            → PROSPECT_DECLINED  (final — no connection created)

Critical rule: prospect is NEVER notified automatically. The service
layer only moves to SENT_TO_PROSPECT when client explicitly says YES.
"""

import uuid
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class SuggestionStatus(models.TextChoices):
    PENDING_CLIENT_REVIEW = "pending_client_review", "Pending Client Review"
    CLIENT_ACCEPTED       = "client_accepted",       "Client Accepted"
    CLIENT_DECLINED       = "client_declined",       "Client Declined"
    SENT_TO_PROSPECT      = "sent_to_prospect",      "Sent to Prospect"
    PROSPECT_ACCEPTED     = "prospect_accepted",     "Prospect Accepted"
    PROSPECT_DECLINED     = "prospect_declined",     "Prospect Declined"


class PrivateMatchSuggestion(models.Model):
    """
    One matchmaker-curated suggestion for a private matchmaking client.
    The matchmaker can create multiple suggestions per client.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    private_client = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_suggestions_received",
        help_text="The private matchmaking client reviewing this suggestion.",
    )
    prospect = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_suggestions_as_prospect",
        help_text="The suggested match (standard or private client).",
    )
    suggested_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pm_suggestions_created",
        help_text="The matchmaker who created this suggestion.",
    )

    status = models.CharField(
        max_length=30,
        choices=SuggestionStatus.choices,
        default=SuggestionStatus.PENDING_CLIENT_REVIEW,
        db_index=True,
    )

    # Client response
    client_feedback      = models.TextField(
        blank=True, null=True,
        help_text="Feedback stored when client declines. Visible to admin only.",
    )
    client_responded_at  = models.DateTimeField(null=True, blank=True)

    # Prospect response
    prospect_responded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Private Match Suggestion"
        verbose_name_plural = "Private Match Suggestions"
        ordering            = ["-created_at"]
        # A prospect can only be suggested to the same client once
        unique_together     = [("private_client", "prospect")]
        indexes = [
            models.Index(fields=["private_client", "status"]),
            models.Index(fields=["prospect", "status"]),
        ]

    def __str__(self):
        return (
            f"PM Suggestion | {self.private_client.codename} ← "
            f"{self.prospect.codename} | {self.status}"
        )