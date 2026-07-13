"""
private_matches/views.py

Swagger tags:
    Private Matches - Client    — private client sees/responds to suggestions
    Private Matches - Prospect  — prospect sees/responds to special match
    Private Matches - Admin     — matchmaker creates suggestions, sees all statuses
"""

import logging
from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import UserRole
from users.permissions import IsAdminUser, IsNormalUser
from .models import PrivateMatchSuggestion, SuggestionStatus
from .serializers import *
from .services import PrivateMatchService
from core.pagination import FlexiblePageNumberPagination


logger = logging.getLogger(__name__)
User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT SIDE  (private matchmaking client)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Private Matches - Client"])
class MySuggestionsView(APIView):
    """
    GET — List all suggestions the matchmaker has sent to the private client.
    Available to: Normal users with is_private_matchmaking_client=True.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Client — List my suggestions",
        description=(
            "Returns all prospect profiles the matchmaker has pushed to the "
            "private client, with current status for each."
        ),
        parameters=[
            OpenApiParameter("status", str, description="Filter by suggestion status."),
        ],
        responses={200: ClientSuggestionSerializer(many=True)},
    )
    def get(self, request):
        if not request.user.is_private_matchmaking_client:
            return Response(
                {"error": "Only available to private matchmaking clients."},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = PrivateMatchSuggestion.objects.filter(private_client=request.user)
        s  = request.query_params.get("status")
        if s:
            qs = qs.filter(status=s)
        return Response(
            ClientSuggestionSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Private Matches - Client"])
class ClientRespondView(APIView):
    """
    POST — Private client responds YES or NO to a suggestion.
    Available to: Normal users with is_private_matchmaking_client=True.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Client — Respond to a suggestion (YES / NO)",
        description=(
            "Pass `accepted: true` to say YES (prospect will receive a Special Match notification). "
            "Pass `accepted: false` with optional `feedback` to say NO "
            "(prospect is NEVER notified; admin receives a PRIVATE_MATCH_UPDATE notification)."
        ),
        request=ClientRespondSerializer,
        responses={
            200: ClientSuggestionSerializer,
            400: OpenApiResponse(description="Cannot respond at this stage."),
            403: OpenApiResponse(description="Not a private matchmaking client."),
            404: OpenApiResponse(description="Suggestion not found."),
        },
    )
    def post(self, request, suggestion_id):
        if not request.user.is_private_matchmaking_client:
            return Response(
                {"error": "Only available to private matchmaking clients."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            suggestion = PrivateMatchSuggestion.objects.get(
                id=suggestion_id, private_client=request.user
            )
        except PrivateMatchSuggestion.DoesNotExist:
            return Response({"error": "Suggestion not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClientRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            suggestion = PrivateMatchService.client_respond(
                suggestion,
                accepted=serializer.validated_data["accepted"],
                feedback=serializer.validated_data.get("feedback", ""),
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ClientSuggestionSerializer(suggestion, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# PROSPECT SIDE
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Private Matches - Prospect"])
class MySpecialMatchesView(APIView):
    """
    GET — Prospect sees their Special Match(es).
    Available to: Any authenticated user (standard or private client).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Prospect — List my special matches",
        description=(
            "Returns special match suggestions sent to the prospect. "
            "Only shown once the private client has accepted (status=sent_to_prospect or beyond)."
        ),
        responses={200: ProspectSpecialMatchSerializer(many=True)},
    )
    def get(self, request):
        qs = PrivateMatchSuggestion.objects.filter(
            prospect=request.user,
            status__in=[
                SuggestionStatus.SENT_TO_PROSPECT,
                SuggestionStatus.PROSPECT_ACCEPTED,
                SuggestionStatus.PROSPECT_DECLINED,
            ],
        )
        return Response(
            ProspectSpecialMatchSerializer(qs, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Private Matches - Prospect"])
class ProspectRespondView(APIView):
    """
    POST — Prospect responds YES or NO to a Special Match.
    NO standard connection is created — matchmaker manages next steps via chat.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Prospect — Respond to a special match (YES / NO)",
        description=(
            "Pass `accepted: true` or `accepted: false`. "
            "No connection is created automatically. "
            "Matchmaker receives a PRIVATE_MATCH_UPDATE notification and will "
            "contact both parties via in-app chat if both respond YES."
        ),
        request=ProspectRespondSerializer,
        responses={
            200: ProspectSpecialMatchSerializer,
            400: OpenApiResponse(description="Cannot respond at this stage."),
            404: OpenApiResponse(description="Suggestion not found."),
        },
    )
    def post(self, request, suggestion_id):
        try:
            suggestion = PrivateMatchSuggestion.objects.get(
                id=suggestion_id, prospect=request.user
            )
        except PrivateMatchSuggestion.DoesNotExist:
            return Response({"error": "Suggestion not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProspectRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            suggestion = PrivateMatchService.prospect_respond(
                suggestion,
                accepted=serializer.validated_data["accepted"],
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ProspectSpecialMatchSerializer(suggestion, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN SIDE
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Private Matches - Admin"])
class AdminCreateSuggestionView(APIView):
    """
    POST — Matchmaker pushes a prospect's profile to a private client.
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — Push a prospect to a private client",
        description=(
            "Creates a new suggestion for `private_client_id` with `prospect_id`. "
            "The prospect is NOT notified — they only receive notification if the "
            "private client responds YES. Gender compatibility is validated automatically."
        ),
        request=CreateSuggestionSerializer,
        responses={
            201: AdminSuggestionListSerializer,
            400: OpenApiResponse(description="Validation error or incompatible genders."),
        },
    )
    def post(self, request):
        serializer = CreateSuggestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        private_client = User.objects.get(id=d["private_client_id"])
        prospect       = User.objects.get(id=d["prospect_id"])

        try:
            suggestion = PrivateMatchService.create_suggestion(
                matchmaker=request.user,
                private_client=private_client,
                prospect=prospect,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            AdminSuggestionListSerializer(suggestion, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Private Matches - Admin"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin — List all suggestions",
        description="Filterable by `status`, `private_client_id`, or `prospect_id`.",
        parameters=[
            OpenApiParameter("status",            str, description="Filter by status."),
            OpenApiParameter("private_client_id", str, description="Filter by private client UUID."),
            OpenApiParameter("prospect_id",       str, description="Filter by prospect UUID."),
        ],
        responses={200: AdminSuggestionListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Admin — Get suggestion detail",
        responses={200: AdminSuggestionListSerializer},
    ),
)
class AdminSuggestionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin read access to all private match suggestions.
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]
    serializer_class   = AdminSuggestionListSerializer
    filter_backends    = [OrderingFilter]
    ordering           = ["-created_at"]

    def get_queryset(self):
        qs = PrivateMatchSuggestion.objects.select_related(
            "private_client", "prospect", "suggested_by"
        )
        s  = self.request.query_params.get("status")
        pc = self.request.query_params.get("private_client_id")
        pr = self.request.query_params.get("prospect_id")
        if s:
            qs = qs.filter(status=s)
        if pc:
            qs = qs.filter(private_client_id=pc)
        if pr:
            qs = qs.filter(prospect_id=pr)
        return qs


@extend_schema(tags=["Private Matches - Admin"])
class AdminProspectDirectoryView(APIView):
    """
    GET — Admin browses potential prospects to suggest for a private client.
    Returns gender-appropriate users (opposite gender of the private client).
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]
    pagination_class   = FlexiblePageNumberPagination

    @extend_schema(
        summary="Admin — Browse prospects for a private client",
        description=(
            "Pass `private_client_id` to auto-filter by opposite gender. "
            "Returns all eligible users (standard + private clients). "
            "Searchable by codename, name, or email."
        ),
        parameters=[
            OpenApiParameter("private_client_id", str, required=True,
                description="UUID of the private client — used to determine gender filter."),
            OpenApiParameter("search", str, description="Search by codename, name, or email."),
            OpenApiParameter("page", int, description="Page number."),
            OpenApiParameter("page_size", int, description="Number of results per page."),
        ],
        responses={200: AdminProspectDirectorySerializer(many=True)},
    )
    def get(self, request):
        client_id = request.query_params.get("private_client_id")
        if not client_id:
            return Response(
                {"error": "private_client_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            private_client = User.objects.get(id=client_id, is_private_matchmaking_client=True)
        except User.DoesNotExist:
            return Response({"error": "Private client not found."}, status=status.HTTP_404_NOT_FOUND)

        # Opposite gender roles
        client_is_female = private_client.role in (UserRole.FEMALE, UserRole.WALI)
        if client_is_female:
            prospect_roles = [UserRole.MALE]
        else:
            prospect_roles = [UserRole.FEMALE, UserRole.WALI]

        qs = User.objects.filter(role__in=prospect_roles, is_active=True).exclude(
            id=private_client.id
        ).order_by("id")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(codename__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)

        from private_matches.serializers import _user_card
        target_qs = page if page is not None else qs
        result = []
        for u in target_qs:
            card = _user_card(u, request)
            card["is_private_matchmaking_client"] = u.is_private_matchmaking_client
            result.append(card)

        if page is not None:
            return paginator.get_paginated_response(result)

        return Response(result, status=status.HTTP_200_OK)
