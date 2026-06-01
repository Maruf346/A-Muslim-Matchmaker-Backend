"""
notifications/views.py

Swagger tag strategy:
    Notifications - Male/Female   → list, retrieve, mark-read, unread-count, clear-read
    Notifications - Wali  → same endpoints, separate tag for clarity in docs
    Notifications - Admin    → same REST endpoints + WebSocket delivery info visible

All three share the same underlying queryset logic (own notifications only).
The tag split is purely for Swagger organisation — the frontend dev sees
exactly which endpoints each role should call.

WebSocket (admin dashboard):
    ws://host/ws/notifications/?token=<access_token>
    — Handled by NotificationConsumer in consumers.py (unchanged).
    — Admin receives real-time pushes automatically when NotificationTemplates
      methods targeting admins are called anywhere in the codebase.
"""

import logging

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import *
from .serializers import *

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Shared mixin — all the actual logic lives here once
# ─────────────────────────────────────────────────────────────────────────────

class _NotificationMixin:
    """
    Shared queryset + actions.
    Concrete subclasses only differ in permission_classes and Swagger tags.
    """
    serializer_class  = NotificationSerializer
    filterset_fields  = ["is_read", "notification_type", "priority"]
    ordering_fields   = ["created_at"]
    ordering          = ["-created_at"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

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
        return Response({"message": f"{count} notification(s) marked as read.", "count": count})

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Return count of unread notifications."""
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=["delete"], url_path="clear-read")
    def clear_read(self, request):
        """Permanently delete all read notifications."""
        deleted, _ = Notification.objects.filter(user=request.user, is_read=True).delete()
        return Response(
            {"message": f"{deleted} notification(s) deleted.", "deleted_count": deleted},
            status=status.HTTP_200_OK,
        )




# ─────────────────────────────────────────────────────────────────────────────
# Admin
# ─────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=["Notifications - Admin"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin — List my notifications",
        description=(
            "Returns all notifications for the authenticated **admin**, newest first.\n\n"
            "Admin notifications are **also pushed in real-time** via WebSocket:\n"
            "```\n"
            "ws://host/ws/notifications/?token=<access_token>\n"
            "```\n"
            "The dashboard should connect to the WebSocket on load and fall back to "
            "polling this REST endpoint if the socket disconnects."
        ),
        parameters=[
            OpenApiParameter("is_read",             bool, description="Filter by read status."),
            OpenApiParameter("notification_type",   str,  description="Filter by notification type."),
            OpenApiParameter("priority",            str,  description="Filter by priority."),
        ],
    ),
    retrieve=extend_schema(
        summary="Admin — Get a single notification",
        description="Includes `websocket_pushed` and `websocket_success` delivery metadata.",
    ),
    mark_read=extend_schema(
        summary="Admin — Mark notification as read",
        responses={200: NotificationSerializer},
    ),
    mark_all_read=extend_schema(
        summary="Admin — Mark all notifications as read",
        responses={200: OpenApiResponse(description='{"count": N}')},
    ),
    unread_count=extend_schema(
        summary="Admin — Get unread count",
        responses={200: OpenApiResponse(description='{"unread_count": N}')},
    ),
    clear_read=extend_schema(
        summary="Admin — Delete all read notifications",
        responses={200: OpenApiResponse(description='{"deleted_count": N}')},
    ),
)
class AdminNotificationViewSet(_NotificationMixin, viewsets.ReadOnlyModelViewSet):
    """
    REST notification feed for **admins**.
    Admins also receive real-time pushes via WebSocket (see consumers.py).
    `websocket_pushed` / `websocket_success` fields in the response reflect
    whether the real-time push was attempted and succeeded.
    """
    # permission_classes = [IsAdmin]
    
    
# Similar viewsets for other types of users would go here, inheriting from _NotificationMixin

