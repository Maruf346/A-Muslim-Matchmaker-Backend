"""
matches/views.py

Swagger tag strategy:
    Matches - Directory     — browse opposite-gender profiles, search/filter
    Matches - Requests      — send/list/respond to connection requests
    Matches - Matches       — list/detail of established matches, cancel
    Matches - Photos        — photo request cycle
    Matches - Wali          — wali request cycle (male-initiated)
    Matches - Subscription  — usage/limits info
    Matches - Admin         — admin match list/detail/status override
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from questions.models import FemaleBasicInfo, MaleBasicInfo, WaliBasicInfo
from users.filters import AdminUserFilterSet
from users.models import UserRole
from users.permissions import IsAdminUser, IsFemaleUser, IsMaleUser, IsNormalUser, IsWaliUser
from wishlists.services import ProfileViewService, VisibilityService

from .models import Match, MatchStatus
from .permissions import CanSendConnectionRequest, IsParticipantInMatch
from .serializers import *
from .services import MatchService, SubscriptionLimitService

logger = logging.getLogger(__name__)
User = get_user_model()

DIRECTORY_BASIC_INFO_RELATIONS = ("male_basic_info", "female_basic_info", "wali_basic_info")
DIRECTORY_SEARCH_USER_FIELDS = ("codename",)
DIRECTORY_SEARCH_BASIC_INFO_FIELDS = (
    "city",
    "country",
    "sect",
    "marital_status",
    "ethnicity",
    "nationality",
    "height",
    "weight",
    "pray_5x",
    "open_to_relocate",
    "employment",
    "education",
    "income",
    "frame",
    "languages_spoken",
    "pref_marital_status",
    "pref_ethnicity",
    "pref_country_of_residence",
    "relationship_with_islam",
    "role_as_spouse",
    "about_yourself",
    "envision_spouse",
    "envision_marriage",
    "spouse_religious_status_pref",
    "open_to_relocate_details",
    "health_concerns",
    "other_preferences",
    "dress",
    "preferred_dress",
    "about",
)
DIRECTORY_FILTER_PARAMETERS = [
    OpenApiParameter("online", bool, description="Only show users active in the last 5 minutes."),
    OpenApiParameter("new", bool, description="Only show users registered in the last 7 days."),
    OpenApiParameter("search", str, description="Search by codename and searchable basic-info text fields."),
    OpenApiParameter("ordering", str, description="Order by `last_active`, `-last_active`, `created_at`, or `-created_at`."),
    OpenApiParameter("date_of_birth", str, description="Filter by exact date of birth (`YYYY-MM-DD`)."),
    OpenApiParameter("age", int, description="Filter by exact age in years."),
    OpenApiParameter("min_age", int, description="Minimum age."),
    OpenApiParameter("max_age", int, description="Maximum age."),
    OpenApiParameter("how_found", str, description="Filter by how the user found the platform."),
    OpenApiParameter("sect", str, description="Filter by sect."),
    OpenApiParameter("city", str, description="Filter by city."),
    OpenApiParameter("country", str, description="Filter by country."),
    OpenApiParameter("marital_status", str, description="Filter by marital status."),
    OpenApiParameter("ethnicity", str, description="Filter by ethnicity."),
    OpenApiParameter("nationality", str, description="Filter by nationality."),
    OpenApiParameter("has_children", bool, description="Filter by whether the user has children."),
    OpenApiParameter("children_count", str, description="Filter by number of children."),
    OpenApiParameter("height", str, description="Filter by height choice."),
    OpenApiParameter("weight", str, description="Filter by weight choice."),
    OpenApiParameter("pray_5x", str, description="Filter by prayer consistency."),
    OpenApiParameter("open_to_relocate", str, description="Filter by relocation choice."),
    OpenApiParameter("employment", str, description="Filter by employment."),
    OpenApiParameter("education", str, description="Filter by education choice."),
    OpenApiParameter("income", str, description="Filter by income choice."),
    OpenApiParameter("frame", str, description="Filter by body frame choice."),
    OpenApiParameter("languages_spoken", str, description="Filter by spoken language."),
    OpenApiParameter("pref_age_min", int, description="Filter by preferred minimum age."),
    OpenApiParameter("pref_age_max", int, description="Filter by preferred maximum age."),
    OpenApiParameter("pref_marital_status", str, description="Filter by preferred marital status."),
    OpenApiParameter("pref_ethnicity", str, description="Filter by preferred ethnicity."),
    OpenApiParameter("pref_country_of_residence", str, description="Filter by preferred country of residence."),
    OpenApiParameter("relationship_with_islam", str, description="Filter by relationship with Islam."),
    OpenApiParameter("role_as_spouse", str, description="Filter by role as spouse."),
    OpenApiParameter("about_yourself", str, description="Filter by about yourself."),
    OpenApiParameter("envision_spouse", str, description="Filter by envision spouse."),
    OpenApiParameter("envision_marriage", str, description="Filter by envision marriage."),
    OpenApiParameter("spouse_religious_status_pref", str, description="Filter by spouse religious status preference."),
    OpenApiParameter("open_to_relocate_details", str, description="Filter by relocation details."),
    OpenApiParameter("health_concerns", str, description="Filter by health concerns."),
    OpenApiParameter("other_preferences", str, description="Filter by other preferences."),
    OpenApiParameter("dress", str, description="Filter by dress choice (Female/Wali profiles)."),
    OpenApiParameter("preferred_dress", str, description="Filter by preferred dress choice (Male profiles)."),
    OpenApiParameter("about", str, description="Filter by Wali-managed sister profile summary."),
]


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _opposite_gender_roles(user) -> list:
    """
    Returns the roles a user can browse/connect with.
        Male   → [FEMALE, WALI]
        Female → [MALE]
        Wali   → [MALE]
    """
    if user.role == UserRole.MALE:
        return [UserRole.FEMALE, UserRole.WALI]
    return [UserRole.MALE]


def _get_match_or_404(pk, user):
    """Fetch a match the user participates in, or return None."""
    try:
        return Match.objects.get(
            Q(id=pk) & (Q(male_user=user) | Q(other_user=user))
        )
    except Match.DoesNotExist:
        return None


def _shift_years(base_date, years):
    try:
        return base_date.replace(year=base_date.year - years)
    except ValueError:
        return base_date.replace(month=2, day=28, year=base_date.year - years)


def _apply_directory_search(queryset, search_term):
    if not search_term:
        return queryset

    query = Q()
    for field in DIRECTORY_SEARCH_USER_FIELDS:
        query |= Q(**{f"{field}__icontains": search_term})
    for relation in DIRECTORY_BASIC_INFO_RELATIONS:
        for field in DIRECTORY_SEARCH_BASIC_INFO_FIELDS:
            query |= Q(**{f"{relation}__{field}__icontains": search_term})
    return queryset.filter(query)


def _apply_age_range_filters(queryset, min_age=None, max_age=None):
    from datetime import timedelta
    from django.utils import timezone

    if min_age is None and max_age is None:
        return queryset

    today = timezone.now().date()
    query = Q()
    for relation in DIRECTORY_BASIC_INFO_RELATIONS:
        relation_query = Q()
        if min_age is not None:
            relation_query &= Q(**{f"{relation}__date_of_birth__lte": _shift_years(today, min_age)})
        if max_age is not None:
            relation_query &= Q(**{f"{relation}__date_of_birth__gte": _shift_years(today, max_age + 1) + timedelta(days=1)})
        query |= relation_query
    return queryset.filter(query)


# ═══════════════════════════════════════════════════════════════════════════════
# DIRECTORY / BROWSE
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Matches - Directory"])
class DirectoryListView(APIView):
    """
    Browse profiles of the opposite gender.

    Male sees Female + Wali profiles.
    Female/Wali see Male profiles.

    Excludes:
        - The requesting user's own blocked/hidden/reported profiles
          (handled by the reports app — not yet integrated here)
        - Users with no basic info record at all are still shown
          (completion_percentage will be 0)

    Supports search and filtering across basic info fields.
    """
    permission_classes = [IsNormalUser]
    filter_backends    = [SearchFilter, OrderingFilter]
    search_fields      = ["codename", "email"]
    ordering_fields    = ["last_active", "created_at"]
    ordering           = ["-last_active"]

    @extend_schema(
        summary="Browse profiles (opposite gender)",
        description=(
            "Returns a paginated list of opposite-gender profiles for browsing.\n\n"
            "- **Male** sees Female + Wali profiles\n"
            "- **Female / Wali** see Male profiles\n\n"
            "**Filters available:**\n"
            "- `online` — only users active in the last 5 minutes\n"
            "- `new` — only users created in the last 7 days\n"
            "- `sect`, `marital_status`, `city`, `country` — exact match on basic info fields\n"
            "- `min_age`, `max_age` — filter by computed age\n\n"
            "Photos are always blurred in directory view (no mutual interest yet)."
        ),
        parameters=DIRECTORY_FILTER_PARAMETERS,
        responses={200: DirectoryProfileSerializer(many=True)},
    )
    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta

        roles = _opposite_gender_roles(request.user)
        qs = User.objects.filter(role__in=roles, is_active=True).exclude(id=request.user.id).select_related(
            "male_basic_info",
            "female_basic_info",
            "wali_basic_info",
            "wali_profile",
        )

        # ── exclude blocked / hidden / reported profiles ─────────────────────
        excluded_ids = VisibilityService.get_excluded_user_ids(request.user)
        if excluded_ids:
            qs = qs.exclude(id__in=excluded_ids)

        # Always exclude private matchmaking clients from standard directory
        qs = qs.filter(is_private_matchmaking_client=False)

        # ── online / new filters ─────────────────────────────────────────────
        if request.query_params.get("online", "").lower() == "true":
            cutoff = timezone.now() - timedelta(minutes=5)
            qs = qs.filter(last_active__gte=cutoff)

        if request.query_params.get("new", "").lower() == "true":
            cutoff = timezone.now() - timedelta(days=7)
            qs = qs.filter(created_at__gte=cutoff)

        # ── search by codename ───────────────────────────────────────────────
        qs = _apply_directory_search(qs, request.query_params.get("search"))
        qs = AdminUserFilterSet(data=request.query_params, queryset=qs, request=request).qs

        # ── basic-info field filters ─────────────────────────────────────────
        sect           = request.query_params.get("sect")
        marital_status = request.query_params.get("marital_status")
        city           = request.query_params.get("city")
        country        = request.query_params.get("country")
        min_age        = request.query_params.get("min_age")
        max_age        = request.query_params.get("max_age")

        if any([sect, marital_status, city, country, min_age, max_age]):
            matching_ids = []
            for u in qs:
                info = None
                if u.role == UserRole.MALE:
                    info = MaleBasicInfo.objects.filter(user=u).first()
                elif u.role == UserRole.FEMALE:
                    info = FemaleBasicInfo.objects.filter(user=u).first()
                elif u.role == UserRole.WALI:
                    info = WaliBasicInfo.objects.filter(user=u).first()

                if not info:
                    continue
                if sect and info.sect != sect:
                    continue
                if marital_status and info.marital_status != marital_status:
                    continue
                if city and (info.city or "").lower() != city.lower():
                    continue
                if country and (info.country or "").lower() != country.lower():
                    continue
                if min_age and (info.age is None or info.age < int(min_age)):
                    continue
                if max_age and (info.age is None or info.age > int(max_age)):
                    continue
                matching_ids.append(u.id)

            qs = qs.filter(id__in=matching_ids)

        # ── ordering ──────────────────────────────────────────────────────────
        ordering = request.query_params.get("ordering", "-last_active")
        if ordering in ("last_active", "-last_active", "created_at", "-created_at"):
            qs = qs.order_by(ordering)

        serializer = DirectoryProfileSerializer(qs.distinct(), many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(tags=["Matches - Directory"])
class DirectoryProfileDetailView(APIView):
    """
    GET — View a single profile from the directory by User UUID.
    Records a ProfileView entry. Photos remain blurred (no mutual interest).
    Available to: Male, Female, Wali (opposite gender only).
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="View a single directory profile",
        description=(
            "Returns the directory-style profile card plus the target user's "
            "role-appropriate basic info record, and records a `ProfileView` "
            "entry (used for the 'who viewed me' feature). "
            "Only opposite-gender profiles are accessible. Blocked/hidden/reported "
            "profiles return 404."
        ),
        responses={
            200: DirectoryProfileDetailSerializer,
            404: OpenApiResponse(description="Profile not found or not accessible."),
        },
    )
    def get(self, request, user_id):
        roles = _opposite_gender_roles(request.user)
        try:
            target = User.objects.select_related(
                "male_basic_info",
                "female_basic_info",
                "wali_basic_info",
            ).get(id=user_id, role__in=roles, is_active=True)
        except User.DoesNotExist:
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if not VisibilityService.can_view_profile(request.user, target):
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            ProfileViewService.record_view(viewer=request.user, viewed_user=target)
        except Exception:
            logger.exception("Failed to record profile view for user %s", target.id)

        return Response(
            DirectoryProfileDetailSerializer(target, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CONNECTION REQUESTS
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Matches - Requests"])
class SendConnectionRequestView(APIView):
    """
    POST — Male sends a connection request to a Female/Wali.
    Available to: Male only. Subject to subscription limits.
    """
    permission_classes = [IsMaleUser, CanSendConnectionRequest]

    @extend_schema(
        summary="Send a connection request",
        description=(
            "Male sends a connection request to a Female or Wali profile by `target_user_id`.\n\n"
            "**Subscription rules:**\n"
            "- Free: blocked (403)\n"
            "- Monthly: limited to 10 requests per billing cycle (anniversary-based)\n"
            "- Annual: unlimited\n\n"
            "If a connection already exists with this user, returns 400."
        ),
        request=SendConnectionRequestSerializer,
        responses={
            201: MatchDetailSerializer,
            400: OpenApiResponse(description="Already connected, limit reached, or validation error."),
            403: OpenApiResponse(description="Free plan — subscription required."),
        },
    )
    def post(self, request):
        serializer = SendConnectionRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        target_user = User.objects.get(id=serializer.validated_data["target_user_id"])

        try:
            match = MatchService.send_connection_request(request.user, target_user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Matches - Requests"])
class SentRequestsListView(APIView):
    """
    GET — List connection requests sent by the authenticated Male user
    that are still PENDING.
    Available to: Male only.
    """
    permission_classes = [IsMaleUser]

    @extend_schema(
        summary="List my sent (pending) requests",
        responses={200: ConnectionRequestListSerializer(many=True)},
    )
    def get(self, request):
        qs = Match.objects.filter(male_user=request.user, status=MatchStatus.PENDING)
        return Response(
            ConnectionRequestListSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Requests"])
class ReceivedRequestsListView(APIView):
    """
    GET — List connection requests received by the authenticated
    Female/Wali user that are still PENDING.
    Available to: Female, Wali only.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="List my received (pending) requests",
        description="Available to Female and Wali users only.",
        responses={
            200: ConnectionRequestListSerializer(many=True),
            403: OpenApiResponse(description="Male users do not receive connection requests."),
        },
    )
    def get(self, request):
        if request.user.role == UserRole.MALE:
            return Response(
                {"error": "Male users do not receive connection requests."},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = Match.objects.filter(other_user=request.user, status=MatchStatus.PENDING)
        return Response(
            ConnectionRequestListSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Requests"])
class RespondToRequestView(APIView):
    """
    PATCH — Female/Wali accepts or declines a pending connection request.
    Available to: Female, Wali only (must be the receiver).
    """
    permission_classes = [IsNormalUser, IsParticipantInMatch]

    @extend_schema(
        summary="Accept or decline a connection request",
        description=(
            "Pass `action`: `accept` or `decline`.\n\n"
            "On accept: status → ACCEPTED, match_id is generated, both parties notified.\n"
            "On decline: status → DECLINED, sender notified."
        ),
        request=None,
        parameters=[
            OpenApiParameter("action", str, required=True, description="`accept` or `decline`."),
        ],
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="Invalid action or wrong status."),
        },
    )
    def patch(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        action_param = request.query_params.get("action")
        try:
            if action_param == "accept":
                match = MatchService.accept_connection_request(match, request.user)
            elif action_param == "decline":
                match = MatchService.decline_connection_request(match, request.user)
            else:
                return Response(
                    {"error": "Invalid action. Must be 'accept' or 'decline'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Requests"])
class CancelPendingRequestView(APIView):
    """
    DELETE — Male cancels their own PENDING request (hard delete).
    Available to: Male only (must be the sender).
    """
    permission_classes = [IsMaleUser, IsParticipantInMatch]

    @extend_schema(
        summary="Cancel a pending request (before any response)",
        description="Permanently removes the pending request. The receiver is notified.",
        responses={
            204: OpenApiResponse(description="Request cancelled and removed."),
            400: OpenApiResponse(description="Request is not in pending status."),
        },
    )
    def delete(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        try:
            MatchService.cancel_pending_request(match, request.user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Matches - Requests"])
class ResendRequestView(APIView):
    """
    POST — Male resends a connection request after a previous DECLINE.
    Available to: Male only.
    """
    permission_classes = [IsMaleUser, CanSendConnectionRequest]

    @extend_schema(
        summary="Resend a connection request after decline",
        description=(
            "Resends a connection request to a previously-declined target. "
            "If no prior connection exists, behaves like a new request. "
            "Subject to the same subscription limits as sending a new request."
        ),
        request=SendConnectionRequestSerializer,
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="Cannot resend — invalid current status or limit reached."),
        },
    )
    def post(self, request):
        serializer = SendConnectionRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        target_user = User.objects.get(id=serializer.validated_data["target_user_id"])

        try:
            match = MatchService.resend_request(request.user, target_user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MATCHES (post mutual-interest)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Matches - Matches"])
class MatchListView(APIView):
    """
    GET — List all matches for the authenticated user where mutual
    interest has been established (status != PENDING/DECLINED).
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="List my matches",
        description=(
            "Returns all matches with mutual interest established "
            "(ACCEPTED, WALI_REQUESTED, WALI_ACCEPTED, IN_DISCUSSION, MARRIED, "
            "CANCELLED, DROPPED). Filter by `status` query param if needed."
        ),
        parameters=[
            OpenApiParameter("status", str, description="Filter by match status."),
        ],
        responses={200: MatchListSerializer(many=True)},
    )
    def get(self, request):
        user = request.user
        qs = Match.objects.filter(Q(male_user=user) | Q(other_user=user)).exclude(
            status__in=[MatchStatus.PENDING, MatchStatus.DECLINED]
        )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response(
            MatchListSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Matches"])
class MatchDetailView(APIView):
    """
    GET — Retrieve full detail of a specific match.
    Available to: Male, Female, Wali (must be a participant).
    """
    permission_classes = [IsNormalUser, IsParticipantInMatch]

    @extend_schema(
        summary="Get match detail",
        description=(
            "Returns full match detail including the other party's profile "
            "with visibility rules applied (full name, photos, phone, wali "
            "details all conditional on match state)."
        ),
        responses={200: MatchDetailSerializer},
    )
    def get(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        # Record that this user viewed the other party's profile
        other_party = match.other_party(request.user)
        try:
            ProfileViewService.record_view(viewer=request.user, viewed_user=other_party)
        except Exception:
            logger.exception("Failed to record profile view for match %s", match.id)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Matches"])
class CancelMatchView(APIView):
    """
    POST — Either party cancels after mutual interest, before wali stage.
    Available to: Male, Female, Wali (must be a participant).
    """
    permission_classes = [IsNormalUser, IsParticipantInMatch]

    @extend_schema(
        summary="Cancel a match (post mutual-interest, pre-wali)",
        description=(
            "Cancels the match. Only allowed from `accepted` status "
            "(before any wali request). Tracks `cancelled_by` and `cancelled_at`. "
            "The other party is notified."
        ),
        request=EmptyActionSerializer,
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="Match is not in 'accepted' status."),
        },
    )
    def post(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        try:
            match = MatchService.cancel_match(match, request.user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Matches"])
class MarkMarriedView(APIView):
    """
    POST — Either participant marks the match as MARRIED.
    Available to: Male, Female, Wali (must be a participant).
    """
    permission_classes = [IsNormalUser, IsParticipantInMatch]

    @extend_schema(
        summary="Mark match as married",
        description="Only allowed from `in_discussion` status. Either participant can call this.",
        request=EmptyActionSerializer,
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="Match is not in 'in_discussion' status."),
        },
    )
    def post(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        try:
            match = MatchService.mark_married(match, request.user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Matches"])
class UnlockMatchView(APIView):
    """
    POST — Either party unlocks (drops) the connection during/after
    wali-accepted stage (status IN_DISCUSSION).
    Available to: Male, Female, Wali (must be a participant).
    """
    permission_classes = [IsNormalUser, IsParticipantInMatch]

    @extend_schema(
        summary="Unlock (drop) the connection — Wali stage",
        description=(
            "Use this when 'things have not worked out' during the Wali stage. "
            "Transitions status → DROPPED immediately and notifies the other party "
            "that a cancellation request has been sent. Only allowed from "
            "`in_discussion` status."
        ),
        request=EmptyActionSerializer,
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="Match is not in 'in_discussion' status."),
        },
    )
    def post(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        try:
            match = MatchService.request_unlock(match, request.user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PHOTO REQUEST CYCLE
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Matches - Photos"])
class RequestPhotoViewView(APIView):
    """
    POST — Either party requests to view photos again (post mutual-interest).
    Available to: Male, Female, Wali (must be a participant).
    """
    permission_classes = [IsNormalUser, IsParticipantInMatch]

    @extend_schema(
        summary="Request to view photos again",
        description=(
            "Available after mutual interest. Sets `photo_request_status=requested`. "
            "The other party is notified and can approve or decline.\n\n"
            "Note: backend supports unlimited requests — frontend should disable "
            "the resend button while a request is pending."
        ),
        request=EmptyActionSerializer,
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="Not mutual yet, or a request is already pending."),
        },
    )
    def post(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        try:
            match = MatchService.request_photo_view(match, request.user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Photos"])
class RespondToPhotoRequestView(APIView):
    """
    PATCH — The other party approves or declines a pending photo request.
    Available to: Male, Female, Wali (must be a participant, not the requester).
    """
    permission_classes = [IsNormalUser, IsParticipantInMatch]

    @extend_schema(
        summary="Approve or decline a photo view request",
        description=(
            "Pass `action`: `approve` or `decline`.\n\n"
            "On approve: `photos_currently_visible=true`, `photos_revealed_count` "
            "increments, timestamps recorded.\n"
            "On decline: resets to `photo_request_status=none`."
        ),
        parameters=[
            OpenApiParameter("action", str, required=True, description="`approve` or `decline`."),
        ],
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="No pending request or invalid action."),
        },
    )
    def patch(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        action_param = request.query_params.get("action")
        try:
            if action_param == "approve":
                match = MatchService.approve_photo_request(match, request.user)
            elif action_param == "decline":
                match = MatchService.decline_photo_request(match, request.user)
            else:
                return Response(
                    {"error": "Invalid action. Must be 'approve' or 'decline'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Photos"])
class MarkPhotosViewedView(APIView):
    """
    POST — Mark currently-visible photos as viewed.
    Flips photos_currently_visible back to False (requires new request to view again).
    Available to: Male, Female, Wali (must be a participant).
    """
    permission_classes = [IsNormalUser, IsParticipantInMatch]

    @extend_schema(
        summary="Mark photos as viewed (re-blur)",
        description=(
            "Call this once the user has viewed the revealed photos. "
            "Sets `photos_currently_visible=false` — a new photo request "
            "is required to view again."
        ),
        request=EmptyActionSerializer,
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="Photos are not currently visible."),
        },
    )
    def post(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        try:
            match = MatchService.mark_photos_viewed(match, request.user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# WALI REQUEST CYCLE  (Male-initiated only)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Matches - Wali"])
class SendWaliRequestView(APIView):
    """
    POST — Male sends a wali request.
    Available to: Male only.
    """
    permission_classes = [IsMaleUser, IsParticipantInMatch]

    @extend_schema(
        summary="Send a wali request",
        description=(
            "Male sends a wali request. Only available from `accepted` status. "
            "Transitions status → WALI_REQUESTED and "
            "wali_request_status → REQUESTED. The other party (Female/Wali) "
            "is notified."
        ),
        request=EmptyActionSerializer,
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="Not in 'accepted' status, or already requested."),
        },
    )
    def post(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        try:
            match = MatchService.send_wali_request(match, request.user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matches - Wali"])
class RespondToWaliRequestView(APIView):
    """
    PATCH — Female/Wali accepts or declines the wali request.
    Available to: Female, Wali only (must be the receiver).
    """
    permission_classes = [IsNormalUser, IsParticipantInMatch]

    @extend_schema(
        summary="Accept or decline a wali request",
        description=(
            "Pass `action`: `accept` or `decline`.\n\n"
            "On accept: wali_request_status → ACCEPTED, status → IN_DISCUSSION. "
            "Male can now see wali details (wali_details_visible=true).\n\n"
            "On decline: wali_request_status → DECLINED, status reverts to ACCEPTED "
            "(male may send another wali request later)."
        ),
        parameters=[
            OpenApiParameter("action", str, required=True, description="`accept` or `decline`."),
        ],
        responses={
            200: MatchDetailSerializer,
            400: OpenApiResponse(description="No pending wali request or invalid action."),
        },
    )
    def patch(self, request, pk):
        match = _get_match_or_404(pk, request.user)
        if not match:
            return Response({"error": "Match not found."}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, match)

        action_param = request.query_params.get("action")
        try:
            if action_param == "accept":
                match = MatchService.accept_wali_request(match, request.user)
            elif action_param == "decline":
                match = MatchService.decline_wali_request(match, request.user)
            else:
                return Response(
                    {"error": "Invalid action. Must be 'accept' or 'decline'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION USAGE
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Matches - Subscription"])
class ConnectionUsageView(APIView):
    """
    GET — Returns the authenticated user's connection request usage
    for the current billing cycle.
    Available to: Male only (only Male sends requests).
    """
    permission_classes = [IsMaleUser]

    @extend_schema(
        summary="Get my connection request usage",
        description=(
            "Returns subscription plan, requests sent this cycle, and remaining "
            "requests. `requests_remaining` and `monthly_limit` are `null` for "
            "Annual (unlimited)."
        ),
        responses={200: ConnectionUsageSerializer},
    )
    def get(self, request):
        user = request.user
        sent       = SubscriptionLimitService.get_requests_sent_this_cycle(user)
        remaining  = SubscriptionLimitService.get_remaining_requests(user)
        cycle_start = SubscriptionLimitService.get_current_cycle_start(user)
        monthly_limit = (
            SubscriptionLimitService.MONTHLY_REQUEST_LIMIT
            if user.subscription_plan == "monthly" else None
        )

        data = {
            "subscription_plan":  user.subscription_plan,
            "requests_sent":      sent,
            "requests_remaining": remaining,
            "monthly_limit":      monthly_limit,
            "cycle_start":        cycle_start,
        }
        return Response(ConnectionUsageSerializer(data).data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Matches - Admin"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin — List all matches",
        description=(
            "Returns all matches across the platform with Groom/Bride summary, "
            "status, and photo reveal info. Filterable by `status`, recent matches, "
            "`photos_revealed`, and created date range."
        ),
        parameters=[
            OpenApiParameter(
                "status", str,
                description=(
                    "Filter by status: pending, declined, accepted, cancelled, "
                    "wali_requested, wali_accepted, in_discussion, married, dropped."
                ),
            ),
            OpenApiParameter(
                "start_date",
                str,
                description="Filter matches created on or after this date (`YYYY-MM-DD`).",
            ),
            OpenApiParameter(
                "end_date",
                str,
                description="Filter matches created on or before this date (`YYYY-MM-DD`).",
            ),
            OpenApiParameter(
                "recent",
                bool,
                description="If true, return matches created in the last 7 days.",
            ),
            OpenApiParameter(
                "photos_revealed",
                bool,
                description="If true, return only matches with at least one photo reveal.",
            ),
            OpenApiParameter(
                "search",
                str,
                description=(
                    "Search by match ID, status, groom/bride first name, last name, "
                    "email, or codename."
                ),
            ),
        ],
        responses={200: AdminMatchListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Admin — Get match detail",
        responses={200: AdminMatchDetailSerializer},
    ),
)
class AdminMatchViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin read access to all matches, plus status override action.
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]
    filter_backends    = [SearchFilter, OrderingFilter]
    search_fields      = [
        "match_id",
        "status",
        "male_user__first_name",
        "male_user__last_name",
        "male_user__email",
        "male_user__codename",
        "other_user__first_name",
        "other_user__last_name",
        "other_user__email",
        "other_user__codename",
        "created_at",
    ]
    ordering_fields    = ["created_at", "updated_at", "accepted_at", "married_at"]
    ordering           = ["-created_at"]
    filterset_fields   = ["status"]

    def get_queryset(self):
        from datetime import timedelta
        from django.utils import timezone

        qs = Match.objects.all()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)

        if self.request.query_params.get("recent") == "true":
            cutoff = timezone.now() - timedelta(days=7)
            qs = qs.filter(created_at__gte=cutoff)

        photos_revealed = self.request.query_params.get("photos_revealed")
        if photos_revealed == "true":
            qs = qs.filter(photos_revealed_count__gt=0)
        elif photos_revealed == "false":
            qs = qs.filter(photos_revealed_count=0)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminMatchDetailSerializer
        return AdminMatchListSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        counters = {
            "total_matches": queryset.count(),
            "in_discussion_count": queryset.filter(status=MatchStatus.IN_DISCUSSION).count(),
            "married_count": queryset.filter(status=MatchStatus.MARRIED).count(),
            "dropped_count": queryset.filter(status=MatchStatus.DROPPED).count(),
        }
        serializer = self.get_serializer(
            queryset,
            many=True,
            context={**self.get_serializer_context(), "match_counters": counters},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Matches - Admin"],
        summary="Admin — Override match status",
        description=(
            "Manually set a match to ANY status, including `married` (mark "
            "successful) or `dropped`, regardless of the current status. "
            "Records which admin made the change and sets relevant timestamps."
        ),
        request=AdminMatchStatusOverrideSerializer,
        responses={
            200: AdminMatchDetailSerializer,
            400: OpenApiResponse(description="Invalid status value."),
        },
    )
    @action(detail=True, methods=["patch"], url_path="override-status")
    def override_status(self, request, pk=None):
        match = self.get_object()
        serializer = AdminMatchStatusOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            match = MatchService.admin_override_status(
                match, request.user, serializer.validated_data["status"]
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            AdminMatchDetailSerializer(match, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
