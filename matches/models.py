"""
matches/models.py

Models:
    Match  — central model covering the entire connection lifecycle:
             connection request → mutual interest → photo cycles →
             wali request → in_discussion → married/dropped

Lifecycle (status field):
    PENDING       → connection request sent, awaiting response
    DECLINED      → receiver declined the request
    ACCEPTED      → mutual interest established (a "match")
    CANCELLED     → either side cancelled after mutual interest, before wali stage
                     (cancelled_by tracks who)
    WALI_REQUESTED → male sent a wali request, awaiting response
    WALI_ACCEPTED  → wali request accepted, wali details now visible to male
    IN_DISCUSSION  → both sides progressing after wali stage
    MARRIED        → marked successful by either party or admin
    DROPPED        → connection ended after wali stage (dropped_by tracks who)

Photo visibility (separate from main status):
    photo_request_status: NONE / REQUESTED / APPROVED
    photos_revealed_count: increments each time photos are approved for viewing
    photos_currently_visible: flips to False after first view, requires new
                               PhotoRequest cycle to flip back to True

Roles:
    Male initiates: connection requests AND wali requests.
    Female/Wali receive and respond to everything (Wali acts on behalf
    of the female profile they manage).

Many-to-many nature:
    A male can have multiple Match rows (one per female/wali target) and
    vice versa — enforced via unique_together on (male_user, other_user).
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Choices
# ─────────────────────────────────────────────────────────────────────────────

class MatchStatus(models.TextChoices):
    PENDING        = "pending",        "Pending"
    DECLINED       = "declined",       "Declined"
    ACCEPTED       = "accepted",       "Accepted (Matched)"
    CANCELLED      = "cancelled",      "Cancelled"
    WALI_REQUESTED = "wali_requested", "Wali Requested"
    WALI_ACCEPTED  = "wali_accepted",  "Wali Accepted"
    IN_DISCUSSION  = "in_discussion",  "In Discussion"
    MARRIED        = "married",        "Married"
    DROPPED        = "dropped",        "Dropped"


class PhotoRequestStatus(models.TextChoices):
    NONE       = "none",       "None"
    REQUESTED  = "requested",  "Requested"
    APPROVED   = "approved",   "Approved"


class SecondPhotoRequestStatus(models.TextChoices):
    NONE     = "none",     "None"
    PENDING  = "pending",  "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"


class WaliRequestStatus(models.TextChoices):
    NONE      = "none",      "None"
    REQUESTED = "requested", "Requested"
    ACCEPTED  = "accepted",  "Accepted"
    DECLINED  = "declined",  "Declined"


# ─────────────────────────────────────────────────────────────────────────────
# Match Model
# ─────────────────────────────────────────────────────────────────────────────

class Match(models.Model):
    """
    Central model representing the connection between a Male user and a
    Female/Wali user, covering the full lifecycle from initial request
    through to marriage or drop-off.

    Field naming convention:
        male_user   — always the Male user in this match
        other_user  — the Female or Wali user (Wali acts on behalf of the
                       female profile they manage)
        initiated_by — who SENT the original connection request
                        (always male_user, per business rule, but stored
                        explicitly for clarity/future flexibility)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    match_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        help_text="Unique match identifier, format: MT-<n> (e.g. MT-1, MT-238).",
    )

    male_user  = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="matches_as_male",
        help_text="The Male user in this match.",
    )
    other_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="matches_as_other",
        help_text="The Female or Wali user in this match.",
    )

    initiated_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="matches_initiated",
        help_text="User who sent the original connection request (always male_user).",
    )

    # ── Overall status ────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=MatchStatus.choices,
        default=MatchStatus.PENDING,
        db_index=True,
    )

    # ── Cancellation tracking (pre-wali stage) ───────────────────────────────
    cancelled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="matches_cancelled",
        help_text="Who cancelled the connection (CANCELLED status, pre-wali stage).",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # ── Drop tracking (post-wali stage) ──────────────────────────────────────
    dropped_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="matches_dropped",
        help_text="Who initiated the drop (DROPPED status, post-wali-accepted stage).",
    )
    dropped_at = models.DateTimeField(null=True, blank=True)

    # ── Photo visibility tracking ────────────────────────────────────────────
    photo_request_status = models.CharField(
        max_length=20,
        choices=PhotoRequestStatus.choices,
        default=PhotoRequestStatus.NONE,
        help_text="Tracks the current photo-view request cycle.",
    )
    photo_requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="photo_requests_made",
        help_text="Who requested to view photos again (most recent request).",
    )
    photos_currently_visible = models.BooleanField(
        default=False,
        help_text="True if photos are currently viewable (resets to False after viewing).",
    )
    photos_revealed_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of times photos have been revealed for this match.",
    )
    photo_view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of female-photo viewing windows granted to the male user.",
    )
    second_photo_request_status = models.CharField(
        max_length=20,
        choices=SecondPhotoRequestStatus.choices,
        default=SecondPhotoRequestStatus.NONE,
        help_text="Tracks the one-time second female-photo viewing request.",
    )
    first_photos_revealed_at = models.DateTimeField(null=True, blank=True)
    last_photos_revealed_at  = models.DateTimeField(null=True, blank=True)

    # ── Wali request tracking ────────────────────────────────────────────────
    wali_request_status = models.CharField(
        max_length=20,
        choices=WaliRequestStatus.choices,
        default=WaliRequestStatus.NONE,
        help_text="Tracks the wali-request cycle (male-initiated only).",
    )
    wali_requested_at = models.DateTimeField(null=True, blank=True)
    wali_responded_at = models.DateTimeField(null=True, blank=True)

    # ── Lifecycle timestamps ──────────────────────────────────────────────────
    requested_at      = models.DateTimeField(auto_now_add=True)
    responded_at      = models.DateTimeField(null=True, blank=True, help_text="When ACCEPTED or DECLINED.")
    accepted_at       = models.DateTimeField(null=True, blank=True)
    in_discussion_at  = models.DateTimeField(null=True, blank=True)
    married_at        = models.DateTimeField(null=True, blank=True)

    # ── Admin override tracking ───────────────────────────────────────────────
    last_status_changed_by_admin = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="matches_admin_overridden",
        help_text="Set when an admin manually overrides the status.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Match"
        verbose_name_plural = "Matches"
        ordering            = ["-created_at"]
        unique_together     = [("male_user", "other_user")]
        indexes = [
            models.Index(fields=["male_user", "status"]),
            models.Index(fields=["other_user", "status"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.match_id or self.id} | {self.male_user.codename} ↔ {self.other_user.codename} | {self.status}"

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def is_mutual(self) -> bool:
        """True once mutual interest has been established (ACCEPTED or beyond)."""
        return self.status in (
            MatchStatus.ACCEPTED,
            MatchStatus.WALI_REQUESTED,
            MatchStatus.WALI_ACCEPTED,
            MatchStatus.IN_DISCUSSION,
            MatchStatus.MARRIED,
            MatchStatus.DROPPED,
        )

    @property
    def wali_details_visible(self) -> bool:
        """True once the wali request has been accepted — male can see wali details."""
        return self.wali_request_status == WaliRequestStatus.ACCEPTED

    def other_party(self, user) -> "User":
        """Given one party in the match, return the other."""
        return self.other_user if user == self.male_user else self.male_user


# ─────────────────────────────────────────────────────────────────────────────
# Match ID Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_match_id() -> str:
    """
    Generate a unique sequential match ID in the format MT-<n>.
    No fixed digit width — e.g. MT-1, MT-238, MT-10000.
    """
    import re

    existing = Match.objects.filter(match_id__startswith="MT-").values_list("match_id", flat=True)
    max_num = 0
    for mid in existing:
        match = re.match(r"^MT-(\d+)$", mid)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"MT-{max_num + 1}"
