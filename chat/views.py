"""
chat/views.py

Swagger tag strategy:
    Chat - User    — normal user's own room: get room, list/send messages, mark read
    Chat - Admin   — admin inbox: list rooms (search/pagination), room detail,
                     list/send messages, mark read, download attachment

Both sides use REST for sending messages (including file attachments) and
listing message history. Real-time delivery happens over
ws://host/ws/chat/<room_id>/ — the REST send-message endpoint pushes to
that WebSocket group automatically via ChatService.

Attachment download:
    Since attachments are stored via FileField under MEDIA_ROOT, they are
    served directly via the `attachment_url` in MessageSerializer (absolute
    URL to MEDIA_URL). A dedicated download endpoint is also provided for
    both user and admin that forces Content-Disposition: attachment, useful
    for clients that need an explicit "download" action (vs inline preview).
"""

import logging

from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminUser, IsNormalUser

from .models import ChatRoom, Message
from .serializers import (
    AdminChatRoomDetailSerializer,
    AdminChatRoomListSerializer,
    MessageSerializer,
    SendMessageSerializer,
    UserChatRoomSerializer,
)
from .services import ChatService

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Pagination
# ─────────────────────────────────────────────────────────────────────────────

class MessagePagination(PageNumberPagination):
    """Paginate message history — most recent page first (newest messages)."""
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


class ChatRoomPagination(PageNumberPagination):
    """Paginate admin inbox room list."""
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ═══════════════════════════════════════════════════════════════════════════════
# USER SIDE
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Chat - User"])
class MyChatRoomView(APIView):
    """
    GET — Retrieve (or create) the authenticated user's chat room with admin.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Get my chat room",
        description=(
            "Returns the authenticated user's chat room, creating it if it "
            "doesn't exist yet. Includes unread count (unread admin messages) "
            "and a preview of the last message."
        ),
        responses={200: UserChatRoomSerializer},
    )
    def get(self, request):
        room = ChatService.get_or_create_room(request.user)
        return Response(
            UserChatRoomSerializer(room, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Chat - User"])
class MyMessagesView(APIView):
    """
    GET  — List messages in my chat room (paginated, oldest-first within page).
    POST — Send a message (text and/or single file attachment).
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]
    pagination_class   = MessagePagination

    @extend_schema(
        summary="List my messages",
        description=(
            "Returns paginated message history for the authenticated user's "
            "chat room, ordered oldest-to-newest within each page. "
            "Use `page` and `page_size` query params; most recent messages "
            "are on the highest page number."
        ),
        parameters=[
            OpenApiParameter("page",      int, description="Page number."),
            OpenApiParameter("page_size", int, description="Messages per page (default 30, max 100)."),
        ],
        responses={200: MessageSerializer(many=True)},
    )
    def get(self, request):
        room = ChatService.get_or_create_room(request.user)
        qs = room.messages.all().order_by("created_at")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = MessageSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Send a message",
        description=(
            "Send a message to admin. Provide `text`, an `attachment` file, "
            "or both. At least one is required. Accepts multipart/form-data "
            "for file uploads.\n\n"
            "The message is pushed in real-time to "
            "`ws://host/ws/chat/<room_id>/` for any connected admins, and "
            "all active admins receive a `new_message` notification."
        ),
        request=SendMessageSerializer,
        responses={
            201: MessageSerializer,
            400: OpenApiResponse(description="Validation error — text or attachment required."),
        },
    )
    def post(self, request):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        room = ChatService.get_or_create_room(request.user)
        message = ChatService.send_message(
            room=room,
            sender=request.user,
            text=d.get("text"),
            attachment=d.get("attachment"),
        )

        return Response(
            MessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Chat - User"])
class MyMarkReadView(APIView):
    """
    POST — Mark all unread admin messages in my room as read.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Mark admin messages as read",
        description="Marks all unread messages from admin as read. Pushes a read_receipt over WebSocket.",
        responses={200: OpenApiResponse(description='{"marked_count": N}')},
    )
    def post(self, request):
        room = ChatService.get_or_create_room(request.user)
        count = ChatService.mark_messages_read(room, request.user)
        return Response({"marked_count": count}, status=status.HTTP_200_OK)


@extend_schema(tags=["Chat - User"])
class MyAttachmentDownloadView(APIView):
    """
    GET — Download an attachment from my chat room (forces download disposition).
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Download an attachment (my room)",
        description=(
            "Streams the attachment file with `Content-Disposition: attachment`, "
            "forcing a download rather than inline preview. Only attachments "
            "from the authenticated user's own room are accessible."
        ),
        parameters=[
            OpenApiParameter("message_id", str, location="path", description="Message UUID."),
        ],
        responses={
            200: OpenApiResponse(description="File stream."),
            404: OpenApiResponse(description="Message or attachment not found."),
        },
    )
    def get(self, request, message_id):
        room = ChatService.get_or_create_room(request.user)
        try:
            message = Message.objects.get(id=message_id, room=room)
        except Message.DoesNotExist:
            return Response({"error": "Message not found."}, status=status.HTTP_404_NOT_FOUND)

        if not message.attachment:
            return Response({"error": "This message has no attachment."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return FileResponse(
                message.attachment.open("rb"),
                as_attachment=True,
                filename=message.attachment_filename,
            )
        except FileNotFoundError:
            raise Http404("Attachment file not found on server.")


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN SIDE
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Chat - Admin"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin — List chat inbox",
        description=(
            "Returns all chat rooms (one per normal user), paginated, ordered "
            "by most recently updated. Each entry includes the user's identity "
            "(codename, full_name, profile picture, role), online/last-active "
            "status, last message preview (\"Sent an attachment\" for file-only "
            "messages), and unread count.\n\n"
            "**Search:** by `search` query param — matches codename, first name, "
            "last name, or email.\n\n"
            "**Pagination:** `page` and `page_size` query params."
        ),
        parameters=[
            OpenApiParameter("search",    str, description="Search by codename, first/last name, or email."),
            OpenApiParameter("page",      int, description="Page number."),
            OpenApiParameter("page_size", int, description="Rooms per page (default 20, max 100)."),
        ],
        responses={200: AdminChatRoomListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Admin — Get chat room detail",
        responses={200: AdminChatRoomDetailSerializer},
    ),
)
class AdminChatRoomViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin inbox — list and detail of all chat rooms.
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]
    serializer_class   = AdminChatRoomListSerializer
    pagination_class   = ChatRoomPagination

    def get_queryset(self):
        qs = ChatRoom.objects.select_related("user").order_by("-updated_at")

        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(user__codename__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__email__icontains=search)
            )

        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminChatRoomDetailSerializer
        return AdminChatRoomListSerializer


@extend_schema(tags=["Chat - Admin"])
class AdminMessagesView(APIView):
    """
    GET  — List messages in a specific room (paginated).
    POST — Send a message as admin (text and/or single file attachment).
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]
    pagination_class   = MessagePagination

    @extend_schema(
        summary="Admin — List messages in a room",
        description="Returns paginated message history for the specified room, oldest-to-newest within each page.",
        parameters=[
            OpenApiParameter("room_id",   str, location="path", description="Chat room UUID."),
            OpenApiParameter("page",      int, description="Page number."),
            OpenApiParameter("page_size", int, description="Messages per page (default 30, max 100)."),
        ],
        responses={
            200: MessageSerializer(many=True),
            404: OpenApiResponse(description="Room not found."),
        },
    )
    def get(self, request, room_id):
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        qs = room.messages.all().order_by("created_at")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = MessageSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Admin — Send a message",
        description=(
            "Send a message to the user in this room. Provide `text`, an "
            "`attachment` file, or both. At least one is required.\n\n"
            "Pushed in real-time to `ws://host/ws/chat/<room_id>/` for the "
            "user (if connected) and any other admins viewing the room. "
            "The user receives a `new_message` notification (DB record, "
            "polled via REST)."
        ),
        request=SendMessageSerializer,
        responses={
            201: MessageSerializer,
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Room not found."),
        },
    )
    def post(self, request, room_id):
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        message = ChatService.send_message(
            room=room,
            sender=request.user,
            text=d.get("text"),
            attachment=d.get("attachment"),
        )

        return Response(
            MessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Chat - Admin"])
class AdminMarkReadView(APIView):
    """
    POST — Mark all unread user messages in a room as read (admin side).
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — Mark user messages as read",
        description="Marks all unread messages from the user as read. Pushes a read_receipt over WebSocket.",
        parameters=[
            OpenApiParameter("room_id", str, location="path", description="Chat room UUID."),
        ],
        responses={
            200: OpenApiResponse(description='{"marked_count": N}'),
            404: OpenApiResponse(description="Room not found."),
        },
    )
    def post(self, request, room_id):
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

        count = ChatService.mark_messages_read(room, request.user)
        return Response({"marked_count": count}, status=status.HTTP_200_OK)


@extend_schema(tags=["Chat - Admin"])
class AdminAttachmentDownloadView(APIView):
    """
    GET — Download an attachment from any chat room (forces download disposition).
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — Download an attachment",
        description="Streams the attachment file with `Content-Disposition: attachment` from any room.",
        parameters=[
            OpenApiParameter("room_id",    str, location="path", description="Chat room UUID."),
            OpenApiParameter("message_id", str, location="path", description="Message UUID."),
        ],
        responses={
            200: OpenApiResponse(description="File stream."),
            404: OpenApiResponse(description="Message or attachment not found."),
        },
    )
    def get(self, request, room_id, message_id):
        try:
            message = Message.objects.get(id=message_id, room_id=room_id)
        except Message.DoesNotExist:
            return Response({"error": "Message not found."}, status=status.HTTP_404_NOT_FOUND)

        if not message.attachment:
            return Response({"error": "This message has no attachment."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return FileResponse(
                message.attachment.open("rb"),
                as_attachment=True,
                filename=message.attachment_filename,
            )
        except FileNotFoundError:
            raise Http404("Attachment file not found on server.")