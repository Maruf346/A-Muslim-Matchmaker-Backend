"""
wishlists/services.py

Services:
    VisibilityService — computes which user IDs should be excluded from
                        a viewer's directory/search/lists due to
                        block/hide/report relationships.
    SavedProfileService — toggle save/unsave
    ProfileViewService  — record a profile view
    BlockService / HideService / ReportService — create block/hide/report
        and clean up related data where appropriate.

This module is imported by matches/views.py (DirectoryListView) to filter
out blocked/hidden/reported profiles from browse results.
"""

import logging

from django.db.models import Q

from .models import BlockedProfile, HiddenProfile, ProfileView, Report, SavedProfile

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Visibility Service
# ─────────────────────────────────────────────────────────────────────────────

class VisibilityService:
    """
    Computes the set of user IDs that should be excluded from a given
    user's directory, search results, and lists.

    Rules:
        - Blocking is mutual: if A blocks B, B is excluded from A's view
          AND A is excluded from B's view.
        - Hiding is one-directional: if A hides B, B is excluded from A's
          view only.
        - Reporting also hides: if A reports B, B is excluded from A's
          view only (in addition to being flagged for admin review).
    """

    @staticmethod
    def get_excluded_user_ids(user) -> set:
        """
        Returns a set of user IDs that `user` should NOT see in any
        directory, search, or list.
        """
        excluded = set()

        # Blocking — mutual
        blocked_by_me = BlockedProfile.objects.filter(blocker=user).values_list("blocked_id", flat=True)
        blocked_me    = BlockedProfile.objects.filter(blocked=user).values_list("blocker_id", flat=True)
        excluded.update(blocked_by_me)
        excluded.update(blocked_me)

        # Hiding — one-directional (only I don't see them)
        hidden_by_me = HiddenProfile.objects.filter(user=user).values_list("hidden_user_id", flat=True)
        excluded.update(hidden_by_me)

        # Reporting — one-directional (only I don't see them)
        reported_by_me = Report.objects.filter(reporter=user).values_list("reported_user_id", flat=True)
        excluded.update(reported_by_me)

        return excluded

    @staticmethod
    def can_view_profile(viewer, target_user) -> bool:
        """
        Returns False if target_user should be hidden from viewer
        due to any block/hide/report relationship.
        """
        excluded = VisibilityService.get_excluded_user_ids(viewer)
        return target_user.id not in excluded


# ─────────────────────────────────────────────────────────────────────────────
# Saved Profile Service
# ─────────────────────────────────────────────────────────────────────────────

class SavedProfileService:

    @staticmethod
    def toggle_save(user, target_user) -> tuple[bool, "SavedProfile | None"]:
        """
        Toggles save/unsave for target_user.

        Returns:
            (is_saved: bool, saved_profile_or_none)
            is_saved=True  → profile was just saved (record created)
            is_saved=False → profile was just unsaved (record deleted)
        """
        existing = SavedProfile.objects.filter(user=user, saved_user=target_user).first()
        if existing:
            existing.delete()
            return False, None

        saved = SavedProfile.objects.create(user=user, saved_user=target_user)
        return True, saved


# ─────────────────────────────────────────────────────────────────────────────
# Profile View Service
# ─────────────────────────────────────────────────────────────────────────────

class ProfileViewService:

    @staticmethod
    def record_view(viewer, viewed_user) -> "ProfileView | None":
        """
        Records that `viewer` viewed `viewed_user`'s profile.
        Does not record self-views.
        Always creates a record regardless of viewed_user's subscription —
        visibility of "who viewed me" is gated separately at the read side.
        """
        if viewer == viewed_user:
            return None

        return ProfileView.objects.create(viewer=viewer, viewed_user=viewed_user)


# ─────────────────────────────────────────────────────────────────────────────
# Block Service
# ─────────────────────────────────────────────────────────────────────────────

class BlockService:

    @staticmethod
    def toggle_block(user, target_user) -> tuple[bool, "BlockedProfile | None"]:
        """
        Toggles block/unblock for target_user.

        Returns:
            (is_blocked: bool, blocked_profile_or_none)
        """
        existing = BlockedProfile.objects.filter(blocker=user, blocked=target_user).first()
        if existing:
            existing.delete()
            return False, None

        blocked = BlockedProfile.objects.create(blocker=user, blocked=target_user)

        # Clean up: remove any saved-profile relations in both directions
        SavedProfile.objects.filter(user=user, saved_user=target_user).delete()
        SavedProfile.objects.filter(user=target_user, saved_user=user).delete()

        return True, blocked


# ─────────────────────────────────────────────────────────────────────────────
# Hide Service
# ─────────────────────────────────────────────────────────────────────────────

class HideService:

    @staticmethod
    def toggle_hide(user, target_user) -> tuple[bool, "HiddenProfile | None"]:
        """
        Toggles hide/unhide for target_user.

        Returns:
            (is_hidden: bool, hidden_profile_or_none)
        """
        existing = HiddenProfile.objects.filter(user=user, hidden_user=target_user).first()
        if existing:
            existing.delete()
            return False, None

        hidden = HiddenProfile.objects.create(user=user, hidden_user=target_user)

        # Clean up: remove saved-profile relation if it exists
        SavedProfile.objects.filter(user=user, saved_user=target_user).delete()

        return True, hidden


# ─────────────────────────────────────────────────────────────────────────────
# Report Service
# ─────────────────────────────────────────────────────────────────────────────

class ReportService:

    @staticmethod
    def create_report(reporter, target_user, reason: str, details: str = "") -> "Report":
        """
        Creates a report. A user can report the same profile multiple times
        (e.g. for different reasons) — no uniqueness constraint.

        Also removes the reported user from the reporter's saved profiles,
        since reporting implies hiding.
        """
        report = Report.objects.create(
            reporter=reporter,
            reported_user=target_user,
            reason=reason,
            details=details or "",
        )

        SavedProfile.objects.filter(user=reporter, saved_user=target_user).delete()

        return report
