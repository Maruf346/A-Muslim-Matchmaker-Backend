"""
matchmaking/services.py
"""

import logging
from django.utils import timezone
from .models import PrivateMatchmakingRequest, RequestStatus, generate_request_id

logger = logging.getLogger(__name__)


class MatchmakingRequestService:

    @staticmethod
    def submit_request(user) -> PrivateMatchmakingRequest:
        """
        User submits a private matchmaking request.
        Only one active (PENDING or APPROVED) request allowed at a time.
        """
        active = PrivateMatchmakingRequest.objects.filter(
            user=user, status__in=[RequestStatus.PENDING, RequestStatus.APPROVED]
        ).first()
        if active:
            raise ValueError(
                "You already have an active private matchmaking request. "
                "Please wait for it to be reviewed."
            )

        req = PrivateMatchmakingRequest.objects.create(user=user)
        req.request_id = generate_request_id()
        req.save(update_fields=["request_id"])
        from dashboard.services import RecentActivityService
        RecentActivityService.matchmaking_request_created(req)
        return req

    @staticmethod
    def approve(request: PrivateMatchmakingRequest, admin, notes: str = "") -> PrivateMatchmakingRequest:
        if request.status != RequestStatus.PENDING:
            raise ValueError(f"Cannot approve a request with status '{request.status}'.")

        now = timezone.now()
        request.status      = RequestStatus.APPROVED
        request.reviewed_by = admin
        request.reviewed_at = now
        request.admin_notes = notes or ""
        request.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_notes", "updated_at"])

        # Flip the user flag
        user = request.user
        user.is_private_matchmaking_client = True
        user.save(update_fields=["is_private_matchmaking_client"])
        from dashboard.services import RecentActivityService
        RecentActivityService.matchmaking_request_approved(request, admin)

        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.private_matchmaking_approved(user)
        except Exception:
            logger.exception("Approval notification failed for request %s", request.id)

        return request

    @staticmethod
    def decline(request: PrivateMatchmakingRequest, admin, notes: str = "") -> PrivateMatchmakingRequest:
        if request.status != RequestStatus.PENDING:
            raise ValueError(f"Cannot decline a request with status '{request.status}'.")

        request.status      = RequestStatus.DECLINED
        request.reviewed_by = admin
        request.reviewed_at = timezone.now()
        request.admin_notes = notes or ""
        request.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_notes", "updated_at"])
        from dashboard.services import RecentActivityService
        RecentActivityService.matchmaking_request_declined(request, admin)

        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.private_matchmaking_declined(request.user, notes)
        except Exception:
            logger.exception("Decline notification failed for request %s", request.id)

        return request
