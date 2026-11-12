"""
matches/services.py

Service layer for the matches app — keeps views thin and business logic
testable.

Classes:
    SubscriptionLimitService — enforces plan-based connection request limits
    MatchService             — connection request lifecycle, photo cycle,
                                wali request cycle, status transitions
"""

import logging

from django.db.models import Q
from django.utils import timezone

from notifications.services import NotificationTemplates
from users.models import UserRole

from .models import *

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Subscription Limit Service
# ─────────────────────────────────────────────────────────────────────────────

class SubscriptionLimitService:
    """
    Enforces connection-request limits based on subscription plan.

    Plan rules:
        FREE    → 2 connection requests total on the free plan
        MONTHLY → 10 connection requests per cycle
                  Cycle resets on the user's subscription_start anniversary
                  each month (e.g. subscribed on the 15th → cycle renews
                  on the 15th of every month).
        ANNUAL  → unlimited
    """

    FREE_REQUEST_LIMIT = 2
    MONTHLY_REQUEST_LIMIT = 10

    @classmethod
    def get_plan_request_limit(cls, user) -> int | None:
        """Return the request cap for the user's current plan, or None if unlimited."""
        if user.subscription_plan == "annual":
            return None
        if user.subscription_plan == "monthly":
            return cls.MONTHLY_REQUEST_LIMIT
        return cls.FREE_REQUEST_LIMIT

    @classmethod
    def get_current_cycle_start(cls, user) -> "timezone.datetime":
        """
        Compute the start of the user's active request-counting window.

        Free users are lifetime-capped from account creation.
        Monthly/annual users use their subscription anniversary cycle.
        """
        if user.subscription_plan == "free":
            return user.created_at

        now = timezone.now()
        sub_start = user.subscription_start or user.created_at

        anniversary_day = sub_start.day
        # Try this month's anniversary first
        try:
            cycle_start = now.replace(
                day=anniversary_day, hour=0, minute=0, second=0, microsecond=0
            )
        except ValueError:
            # Handle months with fewer days (e.g. Feb 30 doesn't exist)
            cycle_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if cycle_start > now:
            # Anniversary hasn't occurred yet this month — go back one month
            if cycle_start.month == 1:
                cycle_start = cycle_start.replace(year=cycle_start.year - 1, month=12)
            else:
                try:
                    cycle_start = cycle_start.replace(month=cycle_start.month - 1)
                except ValueError:
                    cycle_start = cycle_start.replace(month=cycle_start.month - 1, day=1)

        return cycle_start

    @classmethod
    def get_requests_sent_this_cycle(cls, user) -> int:
        """Count connection requests sent by this user in the active plan window."""
        cycle_start = cls.get_current_cycle_start(user)
        return Match.objects.filter(
            initiated_by=user,
            requested_at__gte=cycle_start,
        ).count()

    @classmethod
    def can_send_request(cls, user) -> tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        """
        limit = cls.get_plan_request_limit(user)
        if limit is None:
            return True, ""

        sent = cls.get_requests_sent_this_cycle(user)
        if sent >= limit:
            if user.subscription_plan == "free":
                return False, (
                    f"Free users can send up to {cls.FREE_REQUEST_LIMIT} connection requests. "
                    "Upgrade to Monthly or Annual for more."
                )

            cycle_start = cls.get_current_cycle_start(user)
            return False, (
                f"You have reached your monthly limit of {cls.MONTHLY_REQUEST_LIMIT} "
                f"connection requests. Your limit resets on your subscription "
                f"anniversary date."
            )

        return True, ""

    @classmethod
    def get_remaining_requests(cls, user) -> int | None:
        """Returns remaining requests in the active plan window, or None if unlimited."""
        limit = cls.get_plan_request_limit(user)
        if limit is None:
            return None
        sent = cls.get_requests_sent_this_cycle(user)
        return max(0, limit - sent)


# ─────────────────────────────────────────────────────────────────────────────
# Match Service
# ─────────────────────────────────────────────────────────────────────────────

class MatchService:
    """
    Core business logic for the connection/match lifecycle.

    All methods assume role validation has already happened in the view
    (e.g. only Male can call send_connection_request, only Female/Wali
    can call respond_to_connection_request).
    """

    LOCKED_MATCH_STATUSES = (MatchStatus.WALI_ACCEPTED, MatchStatus.IN_DISCUSSION)

    @classmethod
    def get_active_locked_match(cls, user, exclude_match_id=None) -> "Match | None":
        """Return the active Wali-discussion match locking `user`, if any."""
        if not user or not getattr(user, "is_authenticated", False):
            return None
        qs = Match.objects.filter(
            Q(male_user=user) | Q(other_user=user),
            status__in=cls.LOCKED_MATCH_STATUSES,
        )
        if exclude_match_id is not None:
            qs = qs.exclude(id=exclude_match_id)
        return qs.first()

    @classmethod
    def is_user_locked(cls, user, exclude_match_id=None) -> bool:
        """True if `user` is currently locked in an active Wali discussion."""
        return cls.get_active_locked_match(user, exclude_match_id=exclude_match_id) is not None

    @classmethod
    def _assert_users_unlocked(cls, actor, target_user, exclude_match_id=None) -> None:
        """Raise ValueError if either party is locked in an active Wali discussion."""
        if cls.is_user_locked(actor, exclude_match_id=exclude_match_id):
            raise ValueError(
                "Your profile is currently locked because a discussion with Wali is in progress. "
                "Unlock it before sending or accepting requests."
            )
        if cls.is_user_locked(target_user, exclude_match_id=exclude_match_id):
            raise ValueError(
                "This profile is currently locked because a discussion with Wali is in progress."
            )

    # ── Connection requests ───────────────────────────────────────────────────

    @staticmethod
    def _resolve_pair(sender, target_user):
        """Return (male_user, other_user) for a valid Brother <-> Sister/Wali pair."""
        if sender.role == UserRole.MALE and target_user.role in (UserRole.FEMALE, UserRole.WALI):
            return sender, target_user
        if sender.role in (UserRole.FEMALE, UserRole.WALI) and target_user.role == UserRole.MALE:
            return target_user, sender
        raise ValueError("Connection requests can only be sent between Brother and Sister/Wali profiles.")

    @staticmethod
    def send_connection_request(sender, target_user) -> Match:
        """
        Either Brother or Sister/Wali sends a connection request to an opposite-side profile.

        Raises:
            ValueError if a match already exists between these two users,
            if either user is locked in an active Wali discussion,
            or if the sender has hit their subscription limit.
        """
        male_user, other_user = MatchService._resolve_pair(sender, target_user)
        MatchService._assert_users_unlocked(sender, target_user)

        existing = Match.objects.filter(male_user=male_user, other_user=other_user).first()
        if existing:
            if existing.status in [MatchStatus.DECLINED, MatchStatus.CANCELLED]:
                return MatchService.resend_request(sender, target_user)
            raise ValueError("A connection already exists with this user.")

        allowed, reason = SubscriptionLimitService.can_send_request(sender)
        if not allowed:
            raise ValueError(reason)

        match = Match.objects.create(
            male_user=male_user,
            other_user=other_user,
            initiated_by=sender,
            status=MatchStatus.PENDING,
        )

        try:
            NotificationTemplates.connection_request_received(
                receiver=target_user, sender=sender
            )
        except Exception:
            logger.exception("connection_request_received notification failed for match %s", match.id)

        return match

    @staticmethod
    def accept_connection_request(match: Match, responder) -> Match:
        """
        Receiver (Female/Wali or Male, depending on who initiated) accepts a pending request.
        Transitions PENDING → ACCEPTED. Assigns match_id.
        """
        if match.status != MatchStatus.PENDING:
            raise ValueError(f"Cannot accept a match with status '{match.status}'.")
        expected_receiver = match.other_party(match.initiated_by)
        if responder != expected_receiver:
            raise ValueError("Only the receiver can accept this request.")
        MatchService._assert_users_unlocked(responder, match.initiated_by, exclude_match_id=match.id)

        now = timezone.now()
        match.status       = MatchStatus.ACCEPTED
        match.responded_at = now
        match.accepted_at  = now
        match.photos_currently_visible = True
        match.photos_revealed_count += 1
        match.photo_view_count = 1
        match.first_photos_revealed_at = now
        match.last_photos_revealed_at = now
        if not match.match_id:
            match.match_id = generate_match_id()
        match.save(update_fields=[
            "status", "responded_at", "accepted_at", "match_id",
            "photos_currently_visible", "photos_revealed_count",
            "photo_view_count", "first_photos_revealed_at",
            "last_photos_revealed_at", "updated_at",
        ])
        from dashboard.services import RecentActivityService
        RecentActivityService.match_created(match)

        try:
            NotificationTemplates.connection_request_accepted(
                sender=match.initiated_by, receiver=responder
            )
            NotificationTemplates.match_created(
                user=match.male_user,
                match_id=match.match_id,
                other_user_id=str(match.other_user_id),
            )
            NotificationTemplates.match_created(
                user=match.other_user,
                match_id=match.match_id,
                other_user_id=str(match.male_user_id),
            )
        except Exception:
            logger.exception("Post-accept notifications failed for match %s", match.id)

        return match

    @staticmethod
    def decline_connection_request(match: Match, responder) -> Match:
        """Receiver declines a pending connection request."""
        if match.status != MatchStatus.PENDING:
            raise ValueError(f"Cannot decline a match with status '{match.status}'.")
        expected_receiver = match.other_party(match.initiated_by)
        if responder != expected_receiver:
            raise ValueError("Only the receiver can decline this request.")

        match.status       = MatchStatus.DECLINED
        match.responded_at = timezone.now()
        match.save(update_fields=["status", "responded_at", "updated_at"])

        try:
            NotificationTemplates.connection_request_declined(
                sender=match.initiated_by, receiver=responder
            )
        except Exception:
            logger.exception("connection_request_declined notification failed for match %s", match.id)

        return match

    @staticmethod
    def cancel_pending_request(match: Match, requester) -> Match:
        """
        Sender cancels their own PENDING (not yet responded) request.
        Instead of hard delete, transitions to CANCELLED status so the request
        remains counted against the user's free or plan limit.
        """
        if match.status != MatchStatus.PENDING:
            raise ValueError("Only pending requests can be cancelled this way.")
        if requester != match.initiated_by:
            raise ValueError("Only the sender can cancel a pending request.")

        other_user = match.other_party(requester)
        match.status = MatchStatus.CANCELLED
        match.cancelled_by = requester
        match.cancelled_at = timezone.now()
        match.save(update_fields=["status", "cancelled_by", "cancelled_at", "updated_at"])

        try:
            NotificationTemplates.connection_request_cancelled(
                receiver=other_user, sender=requester
            )
        except Exception:
            logger.exception("connection_request_cancelled notification failed.")

        return match

    @staticmethod
    def resend_request(sender, target_user) -> Match:
        """
        Sender sends a new connection request after a previous DECLINE or CANCELLED status.
        Only allowed if no existing match row exists, or the existing row has status
        DECLINED / CANCELLED (in which case it's reset to PENDING).
        """
        male_user, other_user = MatchService._resolve_pair(sender, target_user)
        MatchService._assert_users_unlocked(sender, target_user)

        existing = Match.objects.filter(male_user=male_user, other_user=other_user).first()

        if existing is None:
            return MatchService.send_connection_request(sender, target_user)

        if existing.status in [MatchStatus.DECLINED, MatchStatus.CANCELLED]:
            allowed, reason = SubscriptionLimitService.can_send_request(sender)
            if not allowed:
                raise ValueError(reason)

            existing.initiated_by = sender
            existing.status       = MatchStatus.PENDING
            existing.responded_at = None
            existing.cancelled_by = None
            existing.cancelled_at = None
            existing.requested_at = timezone.now()
            existing.save(update_fields=[
                "initiated_by", "status", "responded_at",
                "cancelled_by", "cancelled_at", "requested_at", "updated_at",
            ])

            try:
                NotificationTemplates.connection_request_received(
                    receiver=target_user, sender=sender
                )
            except Exception:
                logger.exception("Resend notification failed for match %s", existing.id)

            return existing

        raise ValueError(
            f"Cannot resend — existing connection has status '{existing.status}'."
        )

    # ── Cancel after mutual interest (pre-wali stage) ────────────────────────

    @staticmethod
    def cancel_match(match: Match, requester) -> Match:
        """
        Either party cancels after mutual interest (ACCEPTED stage),
        before any wali request has been made.

        Transitions ACCEPTED → CANCELLED. Tracks cancelled_by/cancelled_at.
        """
        if match.status != MatchStatus.ACCEPTED:
            raise ValueError(
                f"Match can only be cancelled from 'accepted' status. Current status: '{match.status}'."
            )

        if requester not in (match.male_user, match.other_user):
            raise ValueError("You are not a participant in this match.")

        match.status       = MatchStatus.CANCELLED
        match.cancelled_by = requester
        match.cancelled_at = timezone.now()
        match.save(update_fields=["status", "cancelled_by", "cancelled_at", "updated_at"])

        other_party = match.other_party(requester)
        try:
            NotificationTemplates.connection_request_cancelled(
                receiver=other_party, sender=requester
            )
        except Exception:
            logger.exception("Cancel notification failed for match %s", match.id)

        return match

    # ── Photo request cycle ───────────────────────────────────────────────────

    @staticmethod
    def request_second_photo_view(match: Match, requester) -> Match:
        """
        Male requests one final 60-second viewing window for the female/wali photos.
        Transitions second_photo_request_status: NONE -> PENDING.
        """
        if requester != match.male_user:
            raise ValueError("Only the male user can request to view photos one more time.")

        if not match.is_mutual:
            raise ValueError("Photo requests are only available after mutual interest.")
        if match.photos_currently_visible:
            raise ValueError("Photos are already currently visible.")
        if match.photo_view_count < 1:
            raise ValueError("The first photo viewing window has not been used yet.")
        if match.photo_view_count >= 2:
            raise ValueError("The one-time second photo view has already been used.")
        if match.second_photo_request_status != SecondPhotoRequestStatus.NONE:
            raise ValueError("The one-time second photo request has already been submitted.")

        match.second_photo_request_status = SecondPhotoRequestStatus.PENDING
        match.photo_request_status = PhotoRequestStatus.REQUESTED
        match.photo_requested_by = requester
        match.save(update_fields=[
            "second_photo_request_status",
            "photo_request_status",
            "photo_requested_by",
            "updated_at",
        ])

        try:
            NotificationTemplates.photo_request_received(
                receiver=match.other_user, requester=requester, match_id=match.match_id
            )
        except Exception:
            logger.exception("second photo_request_received notification failed for match %s", match.id)

        return match

    @staticmethod
    def respond_second_photo_request(match: Match, responder, accepted: bool) -> Match:
        """
        Female/Wali accepts or rejects the male user's one-time second photo request.
        On accept, grants the second 60-second viewing window.
        """
        if responder != match.other_user:
            raise ValueError("Only the female/wali user can respond to this photo request.")
        if match.second_photo_request_status != SecondPhotoRequestStatus.PENDING:
            raise ValueError("There is no pending second photo request to respond to.")
        if match.photo_requested_by_id != match.male_user_id:
            raise ValueError("Invalid photo request state.")

        requester = match.photo_requested_by

        if not accepted:
            match.second_photo_request_status = SecondPhotoRequestStatus.REJECTED
            match.photo_request_status = PhotoRequestStatus.NONE
            match.photo_requested_by = None
            match.save(update_fields=[
                "second_photo_request_status",
                "photo_request_status",
                "photo_requested_by",
                "updated_at",
            ])

            try:
                NotificationTemplates.photo_request_declined(
                    requester=requester, match_id=match.match_id
                )
            except Exception:
                logger.exception("second photo_request_declined notification failed for match %s", match.id)

            return match

        now = timezone.now()
        match.second_photo_request_status = SecondPhotoRequestStatus.ACCEPTED
        match.photo_request_status = PhotoRequestStatus.APPROVED
        match.photos_currently_visible = True
        match.photos_revealed_count += 1
        match.photo_view_count = 2
        match.last_photos_revealed_at = now
        if not match.first_photos_revealed_at:
            match.first_photos_revealed_at = now
        match.save(update_fields=[
            "second_photo_request_status", "photo_request_status",
            "photos_currently_visible", "photos_revealed_count",
            "photo_view_count", "last_photos_revealed_at",
            "first_photos_revealed_at", "updated_at",
        ])

        try:
            NotificationTemplates.photo_request_approved(
                requester=requester, match_id=match.match_id
            )
        except Exception:
            logger.exception("second photo_request_approved notification failed for match %s", match.id)

        return match

    @staticmethod
    def request_photo_view(match: Match, requester) -> Match:
        """
        Either party (post mutual-interest) requests to view photos
        again after they've been hidden.

        Transitions photo_request_status: NONE/APPROVED → REQUESTED.
        """
        if not match.is_mutual:
            raise ValueError("Photo requests are only available after mutual interest.")
        if requester not in (match.male_user, match.other_user):
            raise ValueError("You are not a participant in this match.")
        if match.photo_request_status == PhotoRequestStatus.REQUESTED:
            raise ValueError("A photo request is already pending.")

        match.photo_request_status = PhotoRequestStatus.REQUESTED
        match.photo_requested_by   = requester
        match.save(update_fields=["photo_request_status", "photo_requested_by", "updated_at"])

        other_party = match.other_party(requester)
        try:
            NotificationTemplates.photo_request_received(
                receiver=other_party, requester=requester, match_id=match.match_id
            )
        except Exception:
            logger.exception("photo_request_received notification failed for match %s", match.id)

        return match

    @staticmethod
    def approve_photo_request(match: Match, responder) -> Match:
        """
        The other party approves the photo view request.
        Sets photos_currently_visible=True, increments counter,
        records timestamps. Resets photo_request_status to NONE
        (ready for a future cycle).
        """
        if match.photo_request_status != PhotoRequestStatus.REQUESTED:
            raise ValueError("There is no pending photo request to approve.")
        if responder == match.photo_requested_by:
            raise ValueError("You cannot approve your own photo request.")
        if responder not in (match.male_user, match.other_user):
            raise ValueError("You are not a participant in this match.")

        now = timezone.now()
        match.photo_request_status   = PhotoRequestStatus.APPROVED
        match.photos_currently_visible = True
        match.photos_revealed_count += 1
        match.last_photos_revealed_at = now
        if not match.first_photos_revealed_at:
            match.first_photos_revealed_at = now
        match.save(update_fields=[
            "photo_request_status", "photos_currently_visible",
            "photos_revealed_count", "last_photos_revealed_at",
            "first_photos_revealed_at", "updated_at",
        ])

        requester = match.photo_requested_by
        try:
            NotificationTemplates.photo_request_approved(
                requester=requester, match_id=match.match_id
            )
        except Exception:
            logger.exception("photo_request_approved notification failed for match %s", match.id)

        return match

    @staticmethod
    def decline_photo_request(match: Match, responder) -> Match:
        """The other party declines the photo view request. Resets to NONE."""
        if match.photo_request_status != PhotoRequestStatus.REQUESTED:
            raise ValueError("There is no pending photo request to decline.")
        if responder == match.photo_requested_by:
            raise ValueError("You cannot decline your own photo request.")

        requester = match.photo_requested_by

        match.photo_request_status = PhotoRequestStatus.NONE
        match.photo_requested_by   = None
        match.save(update_fields=["photo_request_status", "photo_requested_by", "updated_at"])

        try:
            NotificationTemplates.photo_request_declined(
                requester=requester, match_id=match.match_id
            )
        except Exception:
            logger.exception("photo_request_declined notification failed for match %s", match.id)

        return match

    @staticmethod
    def request_photo_view(match: Match, requester) -> Match:
        """Compatibility endpoint for the strict one-time second photo request."""
        return MatchService.request_second_photo_view(match, requester)

    @staticmethod
    def approve_photo_request(match: Match, responder) -> Match:
        """Compatibility endpoint for accepting the strict second photo request."""
        return MatchService.respond_second_photo_request(match, responder, accepted=True)

    @staticmethod
    def decline_photo_request(match: Match, responder) -> Match:
        """Compatibility endpoint for rejecting the strict second photo request."""
        return MatchService.respond_second_photo_request(match, responder, accepted=False)

    @staticmethod
    def mark_photos_viewed(match: Match, viewer) -> Match:
        """
        Called when the user actually opens/views the revealed photos.
        Flips photos_currently_visible back to False — a new PhotoRequest
        cycle is required to view again.
        """
        if not match.photos_currently_visible:
            raise ValueError("Photos are not currently visible.")
        if viewer not in (match.male_user, match.other_user):
            raise ValueError("You are not a participant in this match.")

        match.photos_currently_visible = False
        match.photo_request_status     = PhotoRequestStatus.NONE
        match.save(update_fields=["photos_currently_visible", "photo_request_status", "updated_at"])
        return match

    # ── Wali request cycle (Male-initiated only) ─────────────────────────────

    @staticmethod
    def send_wali_request(match: Match, requester) -> Match:
        """
        Male sends a wali request. Only available post mutual-interest,
        and only the male_user can initiate.

        Transitions:
            wali_request_status: NONE/DECLINED → REQUESTED
            status: ACCEPTED → WALI_REQUESTED
        """
        if requester != match.male_user:
            raise ValueError("Only the male user can send a wali request.")
        MatchService._assert_users_unlocked(requester, match.other_user, exclude_match_id=match.id)
        if not match.is_mutual or match.status != MatchStatus.ACCEPTED:
            raise ValueError(
                f"Wali request can only be sent from 'accepted' status. Current status: '{match.status}'."
            )
        if match.wali_request_status == WaliRequestStatus.REQUESTED:
            raise ValueError("A wali request is already pending.")

        now = timezone.now()
        match.wali_request_status = WaliRequestStatus.REQUESTED
        match.wali_requested_at   = now
        match.status              = MatchStatus.WALI_REQUESTED
        match.save(update_fields=["wali_request_status", "wali_requested_at", "status", "updated_at"])

        try:
            NotificationTemplates.wali_request_received(
                receiver=match.other_user, requester=requester, match_id=match.match_id
            )
        except Exception:
            logger.exception("wali_request_received notification failed for match %s", match.id)

        return match

    @staticmethod
    def accept_wali_request(match: Match, responder) -> Match:
        """
        Female/Wali accepts the wali request.

        Transitions:
            wali_request_status: REQUESTED → ACCEPTED
            status: WALI_REQUESTED → WALI_ACCEPTED → IN_DISCUSSION
                    (both transitions happen together per business rule:
                     "After accepting wali request from both ends... status
                     is in_discussion")
        """
        if responder != match.other_user:
            raise ValueError("Only the receiver can accept the wali request.")
        MatchService._assert_users_unlocked(responder, match.male_user, exclude_match_id=match.id)
        if match.wali_request_status != WaliRequestStatus.REQUESTED:
            raise ValueError("There is no pending wali request to accept.")

        now = timezone.now()
        match.wali_request_status = WaliRequestStatus.ACCEPTED
        match.wali_responded_at   = now
        match.status              = MatchStatus.IN_DISCUSSION
        match.in_discussion_at    = now
        match.save(update_fields=[
            "wali_request_status", "wali_responded_at",
            "status", "in_discussion_at", "updated_at",
        ])

        try:
            NotificationTemplates.wali_request_approved(
                requester=match.male_user, match_id=match.match_id
            )
        except Exception:
            logger.exception("wali_request_approved notification failed for match %s", match.id)

        return match

    @staticmethod
    def decline_wali_request(match: Match, responder) -> Match:
        """
        Female/Wali declines the wali request.

        Transitions:
            wali_request_status: REQUESTED → DECLINED
            status: WALI_REQUESTED → ACCEPTED (back to mutual-interest stage,
                    male can send another wali request later)
        """
        if responder != match.other_user:
            raise ValueError("Only the receiver can decline the wali request.")
        if match.wali_request_status != WaliRequestStatus.REQUESTED:
            raise ValueError("There is no pending wali request to decline.")

        now = timezone.now()
        match.wali_request_status = WaliRequestStatus.DECLINED
        match.wali_responded_at   = now
        match.status              = MatchStatus.ACCEPTED  # back to mutual stage
        match.save(update_fields=["wali_request_status", "wali_responded_at", "status", "updated_at"])

        try:
            NotificationTemplates.wali_request_declined(
                requester=match.male_user, match_id=match.match_id
            )
        except Exception:
            logger.exception("wali_request_declined notification failed for match %s", match.id)

        return match

    # ── Unlock flow (post wali-accepted → drop) ──────────────────────────────

    @staticmethod
    def request_unlock(match: Match, requester) -> Match:
        """
        Either party requests to "unlock" (end) the connection during/after
        the wali-accepted stage (status IN_DISCUSSION).

        This directly transitions status → DROPPED and notifies the other
        party. Per business rule: "when user presses unlock, then it shows
        the cancellation of connection request is sent to the other end's
        user" — so this is an immediate action with notification, not a
        two-step approval.
        """
        if match.status not in MatchService.LOCKED_MATCH_STATUSES:
            raise ValueError(
                f"Unlock is only available from an active Wali discussion. Current status: '{match.status}'."
            )
        if requester not in (match.male_user, match.other_user):
            raise ValueError("You are not a participant in this match.")

        match.status              = MatchStatus.DROPPED
        match.dropped_by          = requester
        match.dropped_at          = timezone.now()
        match.wali_request_status = WaliRequestStatus.NONE
        match.save(update_fields=[
            "status", "dropped_by", "dropped_at", "wali_request_status", "updated_at",
        ])

        other_party = match.other_party(requester)
        try:
            NotificationTemplates.unlock_request_received(
                receiver=other_party, requester=requester, match_id=match.match_id
            )
        except Exception:
            logger.exception("unlock_request_received notification failed for match %s", match.id)

        return match

    # ── Mark married (either party or admin) ──────────────────────────────────

    @staticmethod
    def mark_married(match: Match, actor) -> Match:
        """
        Mark the match as MARRIED. Can be called by either participant
        (post IN_DISCUSSION) or by an admin via override.
        """
        if match.status not in (MatchStatus.IN_DISCUSSION,):
            raise ValueError(
                f"Match can only be marked married from 'in_discussion' status. Current status: '{match.status}'."
            )

        is_admin      = getattr(actor, "is_admin_user", False)
        is_participant = actor in (match.male_user, match.other_user)
        if not is_admin and not is_participant:
            raise ValueError("You are not authorized to update this match.")

        match.status     = MatchStatus.MARRIED
        match.married_at = timezone.now()
        if is_admin:
            match.last_status_changed_by_admin = actor
        match.save(update_fields=["status", "married_at", "last_status_changed_by_admin", "updated_at"])
        from dashboard.services import RecentActivityService
        RecentActivityService.user_married(match, actor=actor if is_admin else None)

        return match

    # ── Admin override ────────────────────────────────────────────────────────

    @staticmethod
    def admin_override_status(match: Match, admin_user, new_status: str) -> Match:
        """
        Admin can manually set the match to ANY status, including MARRIED
        or DROPPED, regardless of the current status. Records the admin
        who made the change and sets relevant timestamps.
        """
        if new_status not in MatchStatus.values:
            raise ValueError(f"Invalid status: {new_status}")

        now = timezone.now()
        match.status = new_status
        match.last_status_changed_by_admin = admin_user

        should_log_married = new_status == MatchStatus.MARRIED and match.status != MatchStatus.MARRIED

        if new_status == MatchStatus.MARRIED and not match.married_at:
            match.married_at = now
        if new_status == MatchStatus.DROPPED and not match.dropped_at:
            match.dropped_at = now
        if new_status == MatchStatus.CANCELLED and not match.cancelled_at:
            match.cancelled_at = now
        if new_status == MatchStatus.ACCEPTED and not match.accepted_at:
            match.accepted_at = now
            if not match.match_id:
                match.match_id = generate_match_id()
        if new_status == MatchStatus.IN_DISCUSSION and not match.in_discussion_at:
            match.in_discussion_at = now

        match.save()
        if should_log_married:
            from dashboard.services import RecentActivityService
            RecentActivityService.user_married(match, actor=admin_user)
        return match
