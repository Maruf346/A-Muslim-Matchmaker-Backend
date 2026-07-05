"""
private_matches/services.py
"""

import logging
from django.utils import timezone
from .models import PrivateMatchSuggestion, SuggestionStatus

logger = logging.getLogger(__name__)


class PrivateMatchService:

    @staticmethod
    def create_suggestion(matchmaker, private_client, prospect) -> PrivateMatchSuggestion:
        """
        Matchmaker pushes a prospect to a private client.
        Validates: client must be a private client, prospect must be opposite gender.
        """
        from users.models import UserRole

        if not private_client.is_private_matchmaking_client:
            raise ValueError("This user is not a private matchmaking client.")

        # Gender check — client female/wali → prospect must be male, and vice versa
        client_is_female = private_client.role in (UserRole.FEMALE, UserRole.WALI)
        prospect_is_male = prospect.role == UserRole.MALE

        if client_is_female and not prospect_is_male:
            raise ValueError("Prospect must be Male for a Female/Wali private client.")
        if not client_is_female and prospect.role not in (UserRole.FEMALE, UserRole.WALI):
            raise ValueError("Prospect must be Female or Wali for a Male private client.")

        if PrivateMatchSuggestion.objects.filter(
            private_client=private_client, prospect=prospect
        ).exists():
            raise ValueError("This prospect has already been suggested to this client.")

        suggestion = PrivateMatchSuggestion.objects.create(
            private_client=private_client,
            prospect=prospect,
            suggested_by=matchmaker,
        )

        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.private_match_update(
                user=matchmaker,
                message=f"A new suggestion has been sent to {private_client.codename}.",
                suggestion_id=str(suggestion.id),
            )
        except Exception:
            logger.exception("Suggestion creation notification failed.")

        return suggestion

    @staticmethod
    def client_respond(suggestion: PrivateMatchSuggestion, accepted: bool, feedback: str = "") -> PrivateMatchSuggestion:
        """
        Private client responds YES or NO.
        On YES: status → CLIENT_ACCEPTED, then immediately → SENT_TO_PROSPECT,
                prospect receives a "Special Match" notification.
        On NO:  status → CLIENT_DECLINED, feedback stored, admin notified.
                Prospect is NEVER notified.
        """
        if suggestion.status != SuggestionStatus.PENDING_CLIENT_REVIEW:
            raise ValueError(f"Cannot respond — current status is '{suggestion.status}'.")

        now = timezone.now()
        suggestion.client_responded_at = now

        if accepted:
            suggestion.status = SuggestionStatus.SENT_TO_PROSPECT
            suggestion.save(update_fields=["status", "client_responded_at", "updated_at"])

            try:
                from notifications.services import NotificationTemplates
                # Notify prospect — "Special Match"
                NotificationTemplates.special_match_received(
                    prospect=suggestion.prospect,
                    suggestion_id=str(suggestion.id),
                )
                # Notify admin
                NotificationTemplates.private_match_update(
                    user=suggestion.suggested_by,
                    message=(
                        f"{suggestion.private_client.codename} accepted the suggestion. "
                        f"Profile sent to prospect {suggestion.prospect.codename}."
                    ),
                    suggestion_id=str(suggestion.id),
                )
            except Exception:
                logger.exception("Client YES notification failed for suggestion %s.", suggestion.id)
        else:
            suggestion.status          = SuggestionStatus.CLIENT_DECLINED
            suggestion.client_feedback = feedback or ""
            suggestion.save(update_fields=["status", "client_feedback", "client_responded_at", "updated_at"])

            try:
                from notifications.services import NotificationTemplates
                NotificationTemplates.private_match_update(
                    user=suggestion.suggested_by,
                    message=(
                        f"{suggestion.private_client.codename} declined the suggestion"
                        + (f": {feedback}" if feedback else "."),
                    ),
                    suggestion_id=str(suggestion.id),
                )
            except Exception:
                logger.exception("Client NO notification failed for suggestion %s.", suggestion.id)

        return suggestion

    @staticmethod
    def prospect_respond(suggestion: PrivateMatchSuggestion, accepted: bool) -> PrivateMatchSuggestion:
        """
        Prospect responds YES or NO to the Special Match.
        No standard connection is created — matchmaker manages everything via chat.
        """
        if suggestion.status != SuggestionStatus.SENT_TO_PROSPECT:
            raise ValueError(f"Cannot respond — current status is '{suggestion.status}'.")

        suggestion.status               = SuggestionStatus.PROSPECT_ACCEPTED if accepted else SuggestionStatus.PROSPECT_DECLINED
        suggestion.prospect_responded_at = timezone.now()
        suggestion.save(update_fields=["status", "prospect_responded_at", "updated_at"])

        action_word = "accepted" if accepted else "declined"
        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.private_match_update(
                user=suggestion.suggested_by,
                message=(
                    f"Prospect {suggestion.prospect.codename} has {action_word} the special match "
                    f"with {suggestion.private_client.codename}."
                ),
                suggestion_id=str(suggestion.id),
            )
        except Exception:
            logger.exception("Prospect response notification failed for suggestion %s.", suggestion.id)

        return suggestion
