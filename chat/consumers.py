"""
chat/consumers.py

WebSocket consumer for real-time chat — used by BOTH normal users
(Male/Female/Wali, for their own room) AND admins (Matchmaker/Superadmin,
for any room in the shared inbox).

Connection:
    ws://host/ws/chat/<room_id>/?token=<access_token>

Access control:
    - Normal user → can only connect to THEIR OWN room (room.user == self)
    - Admin       → can connect to ANY room (shared inbox)
    - Anyone else → rejected with close code 4003

Incoming client actions:
    { "action": "mark_read" }
        → marks all unread messages from the other side as read,
          broadcasts a read_receipt event to the room group.

    { "action": "ping" }
        → responds with {"type": "pong"}

Outgoing server events:
    { "type": "connection_established", "room_id": "...", ... }
    { "type": "chat_message", "message": {...} }
        → broadcast when ChatService.send_message() is called (via REST)
    { "type": "read_receipt", "message_ids": [...], "read_by": "...", "read_at": "..." }
    { "type": "mark_read_response", "marked_count": N }
    { "type": "pong" }

Note: Sending messages (including file attachments) is done via REST
(POST /api/chat/rooms/<room_id>/messages/) — NOT over this WebSocket,
since file uploads aren't practical over a JSON WS connection. The REST
endpoint pushes the new message to this WebSocket group automatically.
"""

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a single chat room.
    Both the room's normal user and any admin can connect.
    """

    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]

        token = self._extract_token()
        self.user = await self._get_user_from_token(token)

        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("Chat WS rejected — unauthenticated connection attempt.")
            await self.close(code=4001)
            return

        has_access = await self._check_room_access(self.user, self.room_id)
        if not has_access:
            logger.warning(
                "Chat WS rejected — user %s has no access to room %s.",
                self.user.email, self.room_id,
            )
            await self.close(code=4003)
            return

        self.group_name = f"chat_{self.room_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info("Chat WS connected: %s → room %s", self.user.email, self.room_id)

        await self.send(text_data=json.dumps({
            "type":    "connection_established",
            "room_id": self.room_id,
            "user_id": str(self.user.id),
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info("Chat WS disconnected: room %s (code=%s)", self.room_id, close_code)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = data.get("action")

        if action == "mark_read":
            count = await self._mark_messages_read()
            await self.send(text_data=json.dumps({
                "type":         "mark_read_response",
                "marked_count": count,
            }))

        elif action == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    # ── Channel layer event handlers ──────────────────────────────────────────

    async def chat_message(self, event):
        """Receives a new message from ChatService and forwards to the client."""
        await self.send(text_data=json.dumps({
            "type":    "chat_message",
            "message": event["message"],
        }))

    async def read_receipt(self, event):
        """Receives a read-receipt event and forwards to the client."""
        await self.send(text_data=json.dumps({
            "type":        "read_receipt",
            "message_ids": event["message_ids"],
            "read_by":     event["read_by"],
            "read_at":     event["read_at"],
        }))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_token(self) -> str:
        qs = self.scope.get("query_string", b"").decode()
        for part in qs.split("&"):
            if part.startswith("token="):
                return part[len("token="):]
        return ""

    @database_sync_to_async
    def _get_user_from_token(self, token: str):
        if not token:
            return AnonymousUser()
        try:
            UntypedToken(token)
            from rest_framework_simplejwt.authentication import JWTAuthentication
            jwt_auth = JWTAuthentication()
            validated = jwt_auth.get_validated_token(token)
            return jwt_auth.get_user(validated)
        except (InvalidToken, TokenError):
            return AnonymousUser()

    @database_sync_to_async
    def _check_room_access(self, user, room_id: str) -> bool:
        """Normal user → only their own room. Admin → any room."""
        from .models import ChatRoom
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return False

        if getattr(user, "is_admin_user", False):
            return True

        return room.user_id == user.id

    @database_sync_to_async
    def _mark_messages_read(self) -> int:
        from .models import ChatRoom
        from .services import ChatService
        try:
            room = ChatRoom.objects.get(id=self.room_id)
        except ChatRoom.DoesNotExist:
            return 0
        return ChatService.mark_messages_read(room, self.user)
