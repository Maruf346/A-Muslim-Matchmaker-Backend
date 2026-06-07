"""
notifications/views.py

REST endpoints for notifications — separated by Swagger tag for clean API docs.

Swagger tag structure:
    "Notifications - Shared"  → Male, Female, Wali (all poll via REST)
    "Notifications - Admin"   → Matchmaker & Superadmin (REST + WebSocket)

Both tag groups hit the same underlying logic via _NotificationMixin.
The tag split is purely for documentation clarity — no duplicate code.

WebSocket (Admin dashboard only):
    ws://host/ws/notifications/?token=<access_token>
    Handled by NotificationConsumer in consumers.py.
    Admins receive real-time pushes automatically when NotificationTemplates
    methods targeting admins are called anywhere in the codebase.

URL registration:
    See notifications/urls.py for router setup.
"""

import logging

from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import *
from .serializers import *

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Inline response schemas for Swagger
# ─────────────────────────────────────────────────────────────────────────────

_mark_all_read_response = inline_serializer(
    name="MarkAllReadResponse",
    fields={
        "message": drf_serializers.CharField(),
        "count":   drf_serializers.IntegerField(),
    },
)

_unread_count_response = inline_serializer(
    name="UnreadCountResponse",
    fields={"unread_count": drf_serializers.IntegerField()},
)

_clear_read_response = inline_serializer(
    name="ClearReadResponse",
    fields={
        "message":       drf_serializers.CharField(),
        "deleted_count": drf_serializers.IntegerField(),
    },
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared mixin — all logic lives here once
# ─────────────────────────────────────────────────────────────────────────────

class _NotificationMixin:
    """
    Shared queryset and custom actions.
    Concrete view classes only differ in permission_classes and Swagger tags.
    """

    serializer_class = NotificationSerializer
    filterset_fields = ["is_read", "notification_type", "priority"]
    ordering_fields  = ["created_at"]
    ordering         = ["-created_at"]

    def get_queryset(self):
        """Return only the authenticated user's notifications."""
        return Notification.objects.filter(user=self.request.user)

    # ── Custom actions ────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Bulk-mark every unread notification as read."""
        count = (
            Notification.objects
            .filter(user=request.user, is_read=False)
            .update(is_read=True, read_at=timezone.now())
        )
        return Response({
            "message": f"{count} notification(s) marked as read.",
            "count":   count,
        })

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Return the count of unread notifications for the current user."""
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=["delete"], url_path="clear-read")
    def clear_read(self, request):
        """Permanently delete all read notifications for the current user."""
        deleted, _ = Notification.objects.filter(user=request.user, is_read=True).delete()
        return Response(
            {
                "message":       f"{deleted} notification(s) deleted.",
                "deleted_count": deleted,
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Shared — Male, Female, Wali
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=["Notifications - Shared"])
@extend_schema_view(
    list=extend_schema(
        summary="List my notifications",
        description=(
            "Returns all notifications for the authenticated user (Male, Female, or Wali), "
            "ordered newest first.\n\n"
            "Mobile clients should **poll this endpoint** periodically to fetch new notifications "
            "— no WebSocket is used for these roles.\n\n"
            "**Filterable by:** `is_read`, `notification_type`, `priority`\n\n"
            "**Notification types relevant to this role:**\n"
            "- `connection_request_received` / `connection_request_accepted` / "
            "`connection_request_declined` / `connection_request_cancelled`\n"
            "- `match_created`\n"
            "- `photo_request_received` / `photo_request_approved` / `photo_request_declined`\n"
            "- `wali_request_received` / `wali_request_approved` / `wali_request_declined`\n"
            "- `unlock_request_received`\n"
            "- `new_message`\n"
            "- `private_matchmaking_confirmed`\n"
            "- `welcome`, `pass_changed`, `account_blocked`, `profile_approved`"
        ),
        parameters=[
            OpenApiParameter("is_read",            bool, description="Filter by read status. `true` or `false`."),
            OpenApiParameter("notification_type",  str,  description="Filter by notification type slug."),
            OpenApiParameter("priority",           str,  description="Filter by priority: `low`, `normal`, `high`, `urgent`."),
            OpenApiParameter("page",               int,  description="Page number."),
            OpenApiParameter("page_size",          int,  description="Results per page (default 8, max 600)."),
        ],
        responses={200: NotificationSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Get a single notification",
        description="Retrieve full details of a single notification by its UUID.",
        responses={200: NotificationSerializer},
    ),
    mark_read=extend_schema(
        summary="Mark a notification as read",
        description="Sets `is_read=true` and records `read_at` timestamp for a single notification.",
        responses={200: NotificationSerializer},
    ),
    mark_all_read=extend_schema(
        summary="Mark all notifications as read",
        description="Bulk-marks every unread notification as read in one call.",
        responses={200: _mark_all_read_response},
    ),
    unread_count=extend_schema(
        summary="Get unread notification count",
        description="Returns the number of unread notifications for the current user.",
        responses={200: _unread_count_response},
    ),
    clear_read=extend_schema(
        summary="Delete all read notifications",
        description="Permanently removes all read notifications. This action is irreversible.",
        responses={200: _clear_read_response},
    ),
)
class SharedNotificationViewSet(_NotificationMixin, viewsets.ReadOnlyModelViewSet):
    """
    Notification feed for **Male, Female, and Wali** users.

    All roles share these endpoints — mobile clients poll REST periodically.
    No WebSocket is used for non-admin users.
    """
    permission_classes = [IsAuthenticated]


# ─────────────────────────────────────────────────────────────────────────────
# Admin — Matchmaker & Superadmin
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=["Notifications - Admin"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin — List my notifications",
        description=(
            "Returns all notifications for the authenticated admin "
            "(Matchmaker or Superadmin), ordered newest first.\n\n"
            "Admin notifications are **also pushed in real-time via WebSocket**:\n"
            "```\n"
            "ws://host/ws/notifications/?token=<access_token>\n"
            "```\n"
            "The dashboard should connect to the WebSocket on load and fall back to "
            "polling this REST endpoint if the socket disconnects.\n\n"
            "**Notification types relevant to admins:**\n"
            "- `new_user_joined` — new user registered\n"
            "- `private_matchmaking_requested` — user booked a consultation\n"
            "- `new_message` — user sent a chat message\n\n"
            "**Filterable by:** `is_read`, `notification_type`, `priority`\n\n"
            "Response includes `websocket_pushed` and `websocket_success` fields "
            "for delivery-status visibility."
        ),
        parameters=[
            OpenApiParameter("is_read",            bool, description="Filter by read status. `true` or `false`."),
            OpenApiParameter("notification_type",  str,  description="Filter by notification type slug."),
            OpenApiParameter("priority",           str,  description="Filter by priority: `low`, `normal`, `high`, `urgent`."),
            OpenApiParameter("page",               int,  description="Page number."),
            OpenApiParameter("page_size",          int,  description="Results per page (default 8, max 600)."),
        ],
        responses={200: NotificationSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Admin — Get a single notification",
        description=(
            "Retrieve full details of a single notification by its UUID.\n\n"
            "Includes `websocket_pushed` and `websocket_success` delivery metadata "
            "to help debug real-time delivery issues."
        ),
        responses={200: NotificationSerializer},
    ),
    mark_read=extend_schema(
        summary="Admin — Mark a notification as read",
        description="Sets `is_read=true` and records `read_at` timestamp for a single notification.",
        responses={200: NotificationSerializer},
    ),
    mark_all_read=extend_schema(
        summary="Admin — Mark all notifications as read",
        description="Bulk-marks every unread admin notification as read in one call.",
        responses={200: _mark_all_read_response},
    ),
    unread_count=extend_schema(
        summary="Admin — Get unread notification count",
        description="Returns the number of unread notifications for the current admin user.",
        responses={200: _unread_count_response},
    ),
    clear_read=extend_schema(
        summary="Admin — Delete all read notifications",
        description="Permanently removes all read notifications for the current admin. Irreversible.",
        responses={200: _clear_read_response},
    ),
)
class AdminNotificationViewSet(_NotificationMixin, viewsets.ReadOnlyModelViewSet):
    """
    Notification feed for **Matchmaker and Superadmin** users.

    Admins receive DB-persisted notifications AND real-time WebSocket pushes.
    `websocket_pushed` / `websocket_success` fields reflect delivery status.

    WebSocket: ws://host/ws/notifications/?token=<access_token>
    """
    # permission_classes = [IsAdminUser]  # TODO: swap in once permission class is defined
    permission_classes = [IsAuthenticated]