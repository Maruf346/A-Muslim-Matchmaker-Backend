"""
wishlists/models.py

Models:
    SavedProfile   — "love button" favorites (toggleable)
    ProfileView    — tracks who viewed whose profile (for "who viewed me")
    BlockedProfile — user blocks another user
    HiddenProfile  — user hides another user from their lists
    Report         — user reports another user to admin

Visibility rule (enforced in matches/wishlists views via a shared helper):
    A user U should NEVER see profile P in directory/search/lists if:
        - U has blocked P, OR
        - U has hidden P, OR
        - U has reported P, OR
        - P has blocked U
    (Hiding/reporting is one-directional; blocking is checked both ways
     since a block should be mutual in effect.)
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Saved Profile  ("love button" favorites)
# ─────────────────────────────────────────────────────────────────────────────

class SavedProfile(models.Model):
    """
    A user saves/favorites another user's profile.
    Toggleable — presence of a row means "saved".
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_profiles",
        help_text="The user who saved the profile.",
    )
    saved_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_by",
        help_text="The profile that was saved.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Saved Profile"
        verbose_name_plural = "Saved Profiles"
        unique_together     = [("user", "saved_user")]
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "saved_user"]),
        ]

    def __str__(self):
        return f"{self.user.codename} saved {self.saved_user.codename}"


# ─────────────────────────────────────────────────────────────────────────────
# Profile View  (for "who viewed me")
# ─────────────────────────────────────────────────────────────────────────────

class ProfileView(models.Model):
    """
    Records that `viewer` viewed `viewed_user`'s profile.

    Multiple views are recorded (not unique) so "last viewed at" can be
    tracked, but the API typically shows the most recent view per viewer.

    Visibility of "who viewed me" is gated by subscription (can_see_viewers)
    at the view/serializer level — the record itself is always created
    regardless of the viewed user's plan.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    viewer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="profile_views_made",
        help_text="The user who viewed the profile.",
    )
    viewed_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="profile_views_received",
        help_text="The profile that was viewed.",
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Profile View"
        verbose_name_plural = "Profile Views"
        ordering            = ["-viewed_at"]
        indexes = [
            models.Index(fields=["viewed_user", "-viewed_at"]),
            models.Index(fields=["viewer", "viewed_user"]),
        ]

    def __str__(self):
        return f"{self.viewer.codename} viewed {self.viewed_user.codename} at {self.viewed_at}"


# ─────────────────────────────────────────────────────────────────────────────
# Blocked Profile
# ─────────────────────────────────────────────────────────────────────────────

class BlockedProfile(models.Model):
    """
    A user blocks another user.
    Blocking is checked BOTH WAYS for visibility — if A blocks B,
    neither A nor B should see each other in directories/lists.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blocker = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="blocked_profiles",
        help_text="The user who initiated the block.",
    )
    blocked = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="blocked_by",
        help_text="The user who was blocked.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Blocked Profile"
        verbose_name_plural = "Blocked Profiles"
        unique_together     = [("blocker", "blocked")]
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.blocker.codename} blocked {self.blocked.codename}"


# ─────────────────────────────────────────────────────────────────────────────
# Hidden Profile
# ─────────────────────────────────────────────────────────────────────────────

class HiddenProfile(models.Model):
    """
    A user hides another user's profile from their own directory/lists.
    One-directional — the hidden user is unaffected.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="hidden_profiles",
        help_text="The user who hid the profile.",
    )
    hidden_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="hidden_by",
        help_text="The profile that was hidden.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Hidden Profile"
        verbose_name_plural = "Hidden Profiles"
        unique_together     = [("user", "hidden_user")]
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.user.codename} hid {self.hidden_user.codename}"


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

class ReportReason(models.TextChoices):
    FAKE_PROFILE    = "fake_profile",    "Fake Profile"
    INAPPROPRIATE   = "inappropriate",   "Inappropriate Content/Behavior"
    SPAM            = "spam",            "Spam"
    HARASSMENT      = "harassment",      "Harassment"
    OTHER           = "other",           "Other"


class ReportStatus(models.TextChoices):
    PENDING   = "pending",   "Pending"
    REVIEWED  = "reviewed",  "Reviewed"
    RESOLVED  = "resolved",  "Resolved"


class Report(models.Model):
    """
    A user reports another user's profile to admin.
    Reporting also hides the profile from the reporter's view
    (one-directional, like HiddenProfile).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reports_made",
        help_text="The user who filed the report.",
    )
    reported_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reports_received",
        help_text="The user being reported.",
    )
    reason  = models.CharField(max_length=30, choices=ReportReason.choices)
    details = models.TextField(blank=True, null=True, help_text="Optional additional details.")
    status  = models.CharField(max_length=20, choices=ReportStatus.choices, default=ReportStatus.PENDING)

    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reports_reviewed",
        help_text="Admin who reviewed this report.",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Report"
        verbose_name_plural = "Reports"
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["reported_user"]),
        ]

    def __str__(self):
        return f"{self.reporter.codename} reported {self.reported_user.codename} ({self.reason})"