"""
matches/suggestion_views.py

Add these to matches/views.py (or keep separate and import in urls.py).

Endpoints:
    GET /api/matches/suggestions/           — list suggested matches
    GET /api/matches/suggestions/<user_id>/ — retrieve a single suggested profile

Swagger tag: "Matches - Suggestions"
Subscription gate: Monthly + Annual only (Free → 403)
"""

import logging

from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from questions.models import FemaleBasicInfo, MaleBasicInfo, UserPhoto, WaliBasicInfo
from questions.serializers import UserPhotoSerializer
from users.models import UserRole
from users.permissions import IsNormalUser

from .suggestions import get_suggested_matches, _get_info

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Serialization helper (inline — avoids circular imports)
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_suggestion(user_obj, info, score: int, request) -> dict:
    """
    Builds the suggestion card for a candidate.
    Photos always blurred (no mutual interest) — frontend handles blur.
    Full name hidden — codename shown instead.
    """
    return {
        "id":                   str(user_obj.id),
        "codename":             user_obj.codename,
        "role":                 user_obj.role,
        "gender":               user_obj.gender,
        "subscription_plan":    user_obj.subscription_plan,
        "last_active":          user_obj.last_active,
        "last_active_display":  _last_active_display(user_obj),
        "match_score":          score,
        # Basic info fields — safe to show in directory context
        "age":                  getattr(info, "age", None),
        "city":                 getattr(info, "city", None),
        "country":              getattr(info, "country", None),
        "sect":                 getattr(info, "sect", None),
        "marital_status":       getattr(info, "marital_status", None),
        "height":               getattr(info, "height", None),
        "frame":                getattr(info, "frame", None),
        "ethnicity":            getattr(info, "ethnicity", None) or [],
        "languages_spoken":     getattr(info, "languages_spoken", None) or [],
        # Photos blurred until mutual interest
        "photos":               UserPhotoSerializer(
            UserPhoto.objects.filter(user=user_obj),
            many=True,
            context={"request": request},
        ).data,
        "photo_blurred":        True,
        "completion_percentage": getattr(info, "completion_percentage", 0),
    }


def _last_active_display(user) -> str | None:
    if not user.last_active:
        return None
    from django.utils import timezone
    delta   = timezone.now() - user.last_active
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "Active now"
    if seconds < 3600:
        return f"Active {seconds // 60} min(s) ago"
    if seconds < 86400:
        return f"Active {seconds // 3600} hr(s) ago"
    return f"Active {seconds // 86400} day(s) ago"


SuggestionCardSchema = inline_serializer(
    name="SuggestionCard",
    fields={
        "id":                    drf_serializers.UUIDField(),
        "codename":              drf_serializers.CharField(),
        "role":                  drf_serializers.CharField(),
        "gender":                drf_serializers.CharField(allow_null=True),
        "subscription_plan":     drf_serializers.CharField(),
        "last_active":           drf_serializers.DateTimeField(allow_null=True),
        "last_active_display":   drf_serializers.CharField(allow_null=True),
        "match_score":           drf_serializers.IntegerField(),
        "age":                   drf_serializers.IntegerField(allow_null=True),
        "city":                  drf_serializers.CharField(allow_null=True),
        "country":               drf_serializers.CharField(allow_null=True),
        "sect":                  drf_serializers.CharField(allow_null=True),
        "marital_status":        drf_serializers.CharField(allow_null=True),
        "height":                drf_serializers.CharField(allow_null=True),
        "frame":                 drf_serializers.CharField(allow_null=True),
        "ethnicity":             drf_serializers.ListField(child=drf_serializers.CharField()),
        "languages_spoken":      drf_serializers.ListField(child=drf_serializers.CharField()),
        "photos":                UserPhotoSerializer(many=True),
        "photo_blurred":         drf_serializers.BooleanField(),
        "completion_percentage": drf_serializers.IntegerField(),
    },
)

_upgrade_error = inline_serializer(
    name="SubscriptionRequiredError",
    fields={"error": drf_serializers.CharField()},
)

_no_prefs_error = inline_serializer(
    name="NoPreferencesError",
    fields={"error": drf_serializers.CharField()},
)


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=["Matches - Suggestions"])
class SuggestedMatchesListView(APIView):
    """
    GET — List suggested matches for the authenticated user based on
    mutual preference matching.

    Subscription gate: Monthly or Annual only.
    Free users receive HTTP 403 with an upgrade message.

    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Get my suggested matches",
        description=(
            "Returns a scored list of suggested profiles based on mutual preference "
            "matching. Both the requesting user's preferences AND the candidate's "
            "preferences must be satisfied (mutual match).\n\n"
            "**Criteria matched:**\n"
            "- Preferred age range\n"
            "- Preferred marital status\n"
            "- Preferred ethnicity (any overlap)\n"
            "- Preferred dress style (Male's preference vs Female/Wali's actual dress)\n\n"
            "**Exclusions:**\n"
            "- Blocked / hidden / reported profiles\n"
            "- Private matchmaking clients\n"
            "- Users already connected (any non-final match status)\n"
            "- Candidates with no basic info or no preferences set\n\n"
            "**Ordering:** Match score (descending), then last active (most recent first).\n\n"
            "**Subscription required:** Monthly or Annual plan. "
            "Free users receive HTTP 403."
        ),
        parameters=[
            OpenApiParameter(
                "limit", int,
                description="Max number of suggestions to return (default 50, max 100).",
            ),
        ],
        responses={
            200: SuggestionCardSchema.__class__(many=True),
            403: _upgrade_error,
            400: _no_prefs_error,
        },
    )
    def get(self, request):
        # Subscription gate
        if not request.user.is_subscribed:
            return Response(
                {
                    "error": (
                        "Suggested matches are available on Monthly and Annual plans. "
                        "Please upgrade your subscription to access this feature."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            limit = min(int(request.query_params.get("limit", 50)), 100)
        except (ValueError, TypeError):
            limit = 50

        suggestions = get_suggested_matches(request.user, limit=limit)

        if not suggestions:
            # Distinguish between "no preferences" vs "no matches found"
            from .suggestions import _get_info, _has_any_preferences
            info = _get_info(request.user)
            if not _has_any_preferences(info):
                return Response(
                    {
                        "error": (
                            "You haven't set any preferences yet. "
                            "Complete your profile to see suggested matches."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response([], status=status.HTTP_200_OK)

        result = [
            _serialize_suggestion(s["user"], s["info"], s["score"], request)
            for s in suggestions
        ]
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(tags=["Matches - Suggestions"])
class SuggestedMatchDetailView(APIView):
    """
    GET — Retrieve a single suggested profile by User UUID.
    Records a ProfileView entry (same as directory detail view).

    Subscription gate: Monthly or Annual only.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Get a single suggested profile",
        description=(
            "Returns the full directory-style profile card for a specific "
            "suggested candidate. Records a ProfileView entry automatically. "
            "Photos remain blurred (no mutual interest). "
            "Returns 404 if the profile is not a valid suggestion for this user "
            "(wrong gender, blocked, private client, etc.).\n\n"
            "**Subscription required:** Monthly or Annual plan."
        ),
        parameters=[
            OpenApiParameter(
                "user_id", str, location="path",
                description="UUID of the suggested candidate.",
            ),
        ],
        responses={
            200: SuggestionCardSchema,
            403: _upgrade_error,
            404: inline_serializer(
                name="NotFoundError",
                fields={"error": drf_serializers.CharField()},
            ),
        },
    )
    def get(self, request, user_id):
        # Subscription gate
        if not request.user.is_subscribed:
            return Response(
                {
                    "error": (
                        "Suggested matches are available on Monthly and Annual plans. "
                        "Please upgrade your subscription to access this feature."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate candidate exists and is opposite gender
        from users.models import UserRole
        if request.user.role == UserRole.MALE:
            candidate_roles = [UserRole.FEMALE, UserRole.WALI]
        else:
            candidate_roles = [UserRole.MALE]

        try:
            candidate = User.objects.get(
                id=user_id,
                role__in=candidate_roles,
                is_active=True,
                is_private_matchmaking_client=False,
            )
        except User.DoesNotExist:
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        # Visibility check
        from wishlists.services import VisibilityService
        if not VisibilityService.can_view_profile(request.user, candidate):
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        # Record profile view
        try:
            from wishlists.services import ProfileViewService
            ProfileViewService.record_view(viewer=request.user, viewed_user=candidate)
        except Exception:
            logger.exception("Failed to record profile view for suggestion detail.")

        info = _get_info(candidate)
        if not info:
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        # Compute score for this specific candidate
        from .suggestions import _mutual_score
        requester_info = _get_info(request.user)
        score = _mutual_score(requester_info, info, request.user, candidate) if requester_info else 0

        return Response(
            _serialize_suggestion(candidate, info, score, request),
            status=status.HTTP_200_OK,
        )
