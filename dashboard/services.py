import logging

from .models import ActivityType, RecentActivity

logger = logging.getLogger(__name__)


class RecentActivityService:
    @staticmethod
    def _display_name(user) -> str:
        if not user:
            return ""
        full_name = getattr(user, "full_name", "") or ""
        if full_name.strip():
            return full_name.strip()
        return getattr(user, "codename", None) or getattr(user, "email", "") or ""

    @classmethod
    def _create(
        cls,
        activity_type: str,
        title: str,
        description: str = "",
        primary_user=None,
        secondary_user=None,
        actor_user=None,
        metadata: dict | None = None,
    ) -> None:
        try:
            RecentActivity.objects.create(
                activity_type=activity_type,
                title=title,
                description=description,
                primary_user=primary_user,
                secondary_user=secondary_user,
                actor_user=actor_user,
                primary_user_name=cls._display_name(primary_user),
                secondary_user_name=cls._display_name(secondary_user),
                actor_user_name=cls._display_name(actor_user),
                metadata=metadata or {},
            )
        except Exception:
            logger.exception("Failed to create recent activity log for %s", activity_type)

    @classmethod
    def user_registered(cls, user) -> None:
        cls._create(
            activity_type=ActivityType.USER_REGISTERED,
            title="New user registered",
            description=f"{cls._display_name(user)} joined the platform.",
            primary_user=user,
        )

    @classmethod
    def match_created(cls, match) -> None:
        cls._create(
            activity_type=ActivityType.MATCH_CREATED,
            title="New match created",
            description=(
                f"{cls._display_name(match.male_user)} matched with "
                f"{cls._display_name(match.other_user)}."
            ),
            primary_user=match.male_user,
            secondary_user=match.other_user,
            metadata={"match_id": match.match_id},
        )

    @classmethod
    def matchmaking_request_created(cls, request) -> None:
        cls._create(
            activity_type=ActivityType.MATCHMAKING_REQUEST_CREATED,
            title="New matchmaking request arrived",
            description=f"{cls._display_name(request.user)} submitted a private matchmaking request.",
            primary_user=request.user,
            metadata={"request_id": request.request_id},
        )

    @classmethod
    def matchmaking_request_approved(cls, request, admin) -> None:
        cls._create(
            activity_type=ActivityType.MATCHMAKING_REQUEST_APPROVED,
            title="Matchmaking request approved",
            description=f"{cls._display_name(request.user)}'s request was approved.",
            primary_user=request.user,
            actor_user=admin,
            metadata={"request_id": request.request_id},
        )

    @classmethod
    def matchmaking_request_declined(cls, request, admin) -> None:
        cls._create(
            activity_type=ActivityType.MATCHMAKING_REQUEST_DECLINED,
            title="Matchmaking request declined",
            description=f"{cls._display_name(request.user)}'s request was declined.",
            primary_user=request.user,
            actor_user=admin,
            metadata={"request_id": request.request_id},
        )

    @classmethod
    def user_married(cls, match, actor=None) -> None:
        cls._create(
            activity_type=ActivityType.USER_MARRIED,
            title="Users marked as married",
            description=(
                f"{cls._display_name(match.male_user)} and "
                f"{cls._display_name(match.other_user)} were marked as married."
            ),
            primary_user=match.male_user,
            secondary_user=match.other_user,
            actor_user=actor,
            metadata={"match_id": match.match_id},
        )

    @classmethod
    def user_verified(cls, user, admin=None) -> None:
        cls._create(
            activity_type=ActivityType.USER_VERIFIED,
            title="User verified",
            description=f"{cls._display_name(user)} was marked as verified.",
            primary_user=user,
            actor_user=admin,
        )
