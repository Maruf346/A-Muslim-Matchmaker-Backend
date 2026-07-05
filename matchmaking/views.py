"""
matchmaking/views.py

Swagger tags:
    Matchmaking - User   — submit request, view own request status
    Matchmaking - Admin  — list/detail/approve/decline requests, list private clients
"""

import logging
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminUser, IsNormalUser
from .models import PrivateMatchmakingRequest, RequestStatus
from .serializers import *
from .services import MatchmakingRequestService

logger = logging.getLogger(__name__)
User = get_user_model()


# ── User side ──────────────────────────────────────────────────────────────────

@extend_schema(tags=["Matchmaking - User"])
class MyMatchmakingRequestView(APIView):
    """
    GET  — Get my current private matchmaking request status.
    POST — Submit a new private matchmaking request.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Get my private matchmaking request",
        description="Returns the user's current (or most recent) private matchmaking request.",
        responses={
            200: PrivateMatchmakingRequestSerializer,
            404: OpenApiResponse(description="No request found."),
        },
    )
    def get(self, request):
        req = (
            PrivateMatchmakingRequest.objects
            .filter(user=request.user)
            .order_by("-created_at")
            .first()
        )
        if not req:
            return Response({"detail": "No request found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            PrivateMatchmakingRequestSerializer(req).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Submit a private matchmaking request",
        description=(
            "Submits a new private matchmaking request. Only one active request "
            "allowed at a time. Admin/matchmaker will review and approve or decline."
        ),
        request=SubmitRequestSerializer,
        responses={
            201: PrivateMatchmakingRequestSerializer,
            400: OpenApiResponse(description="Already has an active request."),
        },
    )
    def post(self, request):
        try:
            req = MatchmakingRequestService.submit_request(request.user)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PrivateMatchmakingRequestSerializer(req).data,
            status=status.HTTP_201_CREATED,
        )


# ── Admin side ─────────────────────────────────────────────────────────────────

@extend_schema(tags=["Matchmaking - Admin"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin — List all private matchmaking requests",
        description="Filterable by `status`. Searchable by codename, email.",
        parameters=[
            OpenApiParameter("status", str, description="pending / approved / declined"),
            OpenApiParameter("search", str, description="Search by codename or email."),
        ],
        responses={200: AdminRequestListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Admin — Get request detail",
        responses={200: AdminRequestDetailSerializer},
    ),
)
class AdminMatchmakingRequestViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    filter_backends    = [SearchFilter, OrderingFilter]
    search_fields      = ["user__codename", "user__email", "user__first_name", "user__last_name"]
    ordering           = ["-created_at"]

    def get_queryset(self):
        qs = PrivateMatchmakingRequest.objects.select_related("user", "reviewed_by")
        s  = self.request.query_params.get("status")
        if s:
            qs = qs.filter(status=s)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminRequestDetailSerializer
        return AdminRequestListSerializer

    @extend_schema(
        tags=["Matchmaking - Admin"],
        summary="Admin — Approve or decline a request",
        description=(
            "Pass `action`: `approve` or `decline` with optional `admin_notes`.\n\n"
            "On **approve**: user's `is_private_matchmaking_client` is set to `true`, "
            "they are hidden from the standard directory, and they receive a notification.\n\n"
            "On **decline**: user receives a notification with the optional note."
        ),
        request=AdminReviewSerializer,
        responses={
            200: AdminRequestDetailSerializer,
            400: OpenApiResponse(description="Invalid action or wrong status."),
        },
    )
    @action(detail=True, methods=["patch"], url_path="review")
    def review(self, request, pk=None):
        req        = self.get_object()
        serializer = AdminReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        try:
            if d["action"] == "approve":
                req = MatchmakingRequestService.approve(req, request.user, d.get("admin_notes", ""))
            else:
                req = MatchmakingRequestService.decline(req, request.user, d.get("admin_notes", ""))
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            AdminRequestDetailSerializer(req, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Matchmaking - Admin"])
class AdminPrivateClientListView(APIView):
    """
    GET — List all users who are currently private matchmaking clients.
    Filterable by gender (male / female+wali).
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — List private matchmaking clients",
        description=(
            "Returns all users with `is_private_matchmaking_client=true`. "
            "Filter by `gender`: `male` returns Male users; "
            "`female` returns Female + Wali users."
        ),
        parameters=[
            OpenApiParameter("gender", str, description="`male` or `female` (female includes wali)."),
            OpenApiParameter("search", str, description="Search by codename, name, or email."),
        ],
        responses={200: OpenApiResponse(description="List of private clients.")},
    )
    def get(self, request):
        from users.models import UserRole
        from users.serializers import AdminUserListSerializer

        qs = User.objects.filter(is_private_matchmaking_client=True, is_active=True)

        gender = request.query_params.get("gender")
        if gender == "male":
            qs = qs.filter(role=UserRole.MALE)
        elif gender == "female":
            qs = qs.filter(role__in=[UserRole.FEMALE, UserRole.WALI])

        search = request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(codename__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )

        from users.serializers import AdminUserListSerializer
        return Response(
            AdminUserListSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
        
