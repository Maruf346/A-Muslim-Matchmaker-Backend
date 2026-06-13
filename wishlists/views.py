"""
wishlists/views.py

Swagger tag strategy:
    Wishlists - Saved      — save/unsave toggle, list saved profiles
    Wishlists - Views      — "who viewed me" list
    Wishlists - Block      — block/unblock toggle, list blocked
    Wishlists - Hide       — hide/unhide toggle, list hidden
    Wishlists - Report     — file a report
    Wishlists - Admin      — admin report list/detail/update
"""

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminUser, IsNormalUser

from .models import BlockedProfile, HiddenProfile, ProfileView, Report, SavedProfile
from .serializers import (
    AdminReportDetailSerializer,
    AdminReportListSerializer,
    AdminReportUpdateSerializer,
    BlockedProfileListSerializer,
    BlockToggleResponseSerializer,
    CreateReportSerializer,
    HiddenProfileListSerializer,
    HideToggleResponseSerializer,
    ProfileViewListSerializer,
    ReportCreateResponseSerializer,
    SavedProfileListSerializer,
    SaveToggleResponseSerializer,
    ToggleTargetSerializer,
)
from .services import BlockService, HideService, ReportService, SavedProfileService

logger = logging.getLogger(__name__)
User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════════
# SAVED PROFILES
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Wishlists - Saved"])
class ToggleSaveProfileView(APIView):
    """
    POST — Toggle save/unsave for a profile (the "love button").
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Toggle save (favorite) a profile",
        description=(
            "Toggles the save/favorite state for `target_user_id`. "
            "If already saved, this unsaves it (and vice versa). "
            "Response indicates the new state via `is_saved`."
        ),
        request=ToggleTargetSerializer,
        responses={
            200: SaveToggleResponseSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = ToggleTargetSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        target_user = User.objects.get(id=serializer.validated_data["target_user_id"])

        is_saved, _ = SavedProfileService.toggle_save(request.user, target_user)

        message = "Profile saved." if is_saved else "Profile removed from saved list."
        return Response(
            {"is_saved": is_saved, "message": message},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Wishlists - Saved"])
class SavedProfilesListView(APIView):
    """
    GET — List all profiles saved/favorited by the authenticated user.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="List my saved profiles",
        responses={200: SavedProfileListSerializer(many=True)},
    )
    def get(self, request):
        qs = SavedProfile.objects.filter(user=request.user).select_related("saved_user")
        return Response(
            SavedProfileListSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE VIEWS  ("who viewed me")
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Wishlists - Views"])
class ProfileViewersListView(APIView):
    """
    GET — List users who viewed the authenticated user's profile.
    Gated by subscription: Free users cannot see this (can_see_viewers=False).
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="List who viewed my profile",
        description=(
            "Returns users who viewed the authenticated user's profile, most "
            "recent first. **Requires Monthly or Annual subscription** — "
            "Free users receive a 403 with an upgrade message.\n\n"
            "Shows the most recent view per viewer (deduplicated)."
        ),
        responses={
            200: ProfileViewListSerializer(many=True),
            403: OpenApiResponse(description="Free plan — subscription required to view this list."),
        },
    )
    def get(self, request):
        if not request.user.can_see_viewers:
            return Response(
                {"error": "Upgrade to Monthly or Annual to see who viewed your profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get most recent view per viewer
        from django.db.models import Max
        latest_view_ids = (
            ProfileView.objects
            .filter(viewed_user=request.user)
            .values("viewer")
            .annotate(latest=Max("viewed_at"))
            .values_list("latest", flat=True)
        )
        qs = (
            ProfileView.objects
            .filter(viewed_user=request.user, viewed_at__in=latest_view_ids)
            .select_related("viewer")
            .order_by("-viewed_at")
        )

        return Response(
            ProfileViewListSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Wishlists - Block"])
class ToggleBlockProfileView(APIView):
    """
    POST — Toggle block/unblock for a profile.
    Blocking is mutual — neither party will see the other afterward.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Toggle block a profile",
        description=(
            "Toggles the block state for `target_user_id`. Blocking is mutual: "
            "neither user will see the other in directory/search/lists. "
            "Also removes any existing saved-profile relations between the two users. "
            "If already blocked, this unblocks."
        ),
        request=ToggleTargetSerializer,
        responses={
            200: BlockToggleResponseSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = ToggleTargetSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        target_user = User.objects.get(id=serializer.validated_data["target_user_id"])

        is_blocked, _ = BlockService.toggle_block(request.user, target_user)

        message = "Profile blocked." if is_blocked else "Profile unblocked."
        return Response(
            {"is_blocked": is_blocked, "message": message},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Wishlists - Block"])
class BlockedProfilesListView(APIView):
    """
    GET — List all profiles the authenticated user has blocked.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="List profiles I've blocked",
        responses={200: BlockedProfileListSerializer(many=True)},
    )
    def get(self, request):
        qs = BlockedProfile.objects.filter(blocker=request.user).select_related("blocked")
        return Response(
            BlockedProfileListSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# HIDE
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Wishlists - Hide"])
class ToggleHideProfileView(APIView):
    """
    POST — Toggle hide/unhide for a profile.
    Hiding is one-directional — only affects the authenticated user's view.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Toggle hide a profile",
        description=(
            "Toggles the hide state for `target_user_id`. Hiding is one-directional: "
            "the profile is removed from your directory/search/lists only. "
            "Also removes any saved-profile relation. If already hidden, this unhides."
        ),
        request=ToggleTargetSerializer,
        responses={
            200: HideToggleResponseSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = ToggleTargetSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        target_user = User.objects.get(id=serializer.validated_data["target_user_id"])

        is_hidden, _ = HideService.toggle_hide(request.user, target_user)

        message = "Profile hidden." if is_hidden else "Profile unhidden."
        return Response(
            {"is_hidden": is_hidden, "message": message},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Wishlists - Hide"])
class HiddenProfilesListView(APIView):
    """
    GET — List all profiles the authenticated user has hidden.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="List profiles I've hidden",
        responses={200: HiddenProfileListSerializer(many=True)},
    )
    def get(self, request):
        qs = HiddenProfile.objects.filter(user=request.user).select_related("hidden_user")
        return Response(
            HiddenProfileListSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Wishlists - Report"])
class CreateReportView(APIView):
    """
    POST — File a report against a profile.
    Reporting also hides the profile from the reporter's lists.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Report a profile",
        description=(
            "Files a report against `target_user_id` with a `reason` and optional "
            "`details`. The reported profile is also removed from the reporter's "
            "saved profiles. A user may report the same profile multiple times "
            "(e.g. for different reasons). Admins review reports via the admin endpoints."
        ),
        request=CreateReportSerializer,
        responses={
            201: ReportCreateResponseSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = CreateReportSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        target_user = User.objects.get(id=d["target_user_id"])

        report = ReportService.create_report(
            reporter=request.user,
            target_user=target_user,
            reason=d["reason"],
            details=d.get("details", ""),
        )

        return Response(
            {"id": report.id, "message": "Report submitted. Our team will review it shortly."},
            status=status.HTTP_201_CREATED,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Wishlists - Admin"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin — List all reports",
        description="Returns all reports filed by users. Filterable by `status` and `reason`.",
        responses={200: AdminReportListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Admin — Get report detail",
        responses={200: AdminReportDetailSerializer},
    ),
)
class AdminReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin read access to all reports, plus status-update action.
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]
    filter_backends    = [OrderingFilter]
    ordering_fields    = ["created_at", "status"]
    ordering           = ["-created_at"]
    filterset_fields   = ["status", "reason"]

    def get_queryset(self):
        qs = Report.objects.all().select_related("reporter", "reported_user", "reviewed_by")
        status_filter = self.request.query_params.get("status")
        reason_filter = self.request.query_params.get("reason")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if reason_filter:
            qs = qs.filter(reason=reason_filter)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminReportDetailSerializer
        return AdminReportListSerializer

    @extend_schema(
        tags=["Wishlists - Admin"],
        summary="Admin — Update report status",
        description=(
            "Update a report's `status` (pending/reviewed/resolved) and add "
            "optional `admin_notes`. Records the reviewing admin and timestamp."
        ),
        request=AdminReportUpdateSerializer,
        responses={200: AdminReportDetailSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="update-status")
    def update_status(self, request, pk=None):
        report = self.get_object()
        serializer = AdminReportUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report.status      = serializer.validated_data["status"]
        report.admin_notes = serializer.validated_data.get("admin_notes", report.admin_notes)
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "admin_notes", "reviewed_by", "reviewed_at"])

        return Response(
            AdminReportDetailSerializer(report, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )