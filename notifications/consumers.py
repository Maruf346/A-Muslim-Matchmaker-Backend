import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.

    Connect:
        ws://host/ws/notifications/?token=<access_token>

    Incoming actions (client → server):
        { "action": "mark_read", "notification_id": "<uuid>" }

    Outgoing events (server → client):
        { "type": "connection_established", ... }
        { "type": "notification", "notification_type": ..., "title": ..., ... }
    """

    async def connect(self):
        qs = self.scope.get("query_string", b"").decode()
        token = ""
        for part in qs.split("&"):
            if part.startswith("token="):
                token = part[len("token="):]
                break

        self.user = await self._get_user_from_token(token)

        if self.user and not isinstance(self.user, AnonymousUser):
            self.group_name = f"user_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            await self.send(text_data=json.dumps({
                "type": "connection_established",
                "message": "Connected to FixGo notification service",
                "user_id": str(self.user.id),
            }))
        else:
            await self.close(code=4001)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = data.get("action")

        if action == "mark_read":
            notification_id = data.get("notification_id")
            if notification_id:
                success = await self._mark_notification_read(notification_id)
                await self.send(text_data=json.dumps({
                    "type": "mark_read_response",
                    "notification_id": notification_id,
                    "success": success,
                }))

        elif action == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    # ── Channel layer event handlers ──────────────────────────────────────────

    async def notification_message(self, event):
        """Receives from channel layer → forwards to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type": "notification",
            "notification_type": event.get("notification_type"),
            "title": event["title"],
            "body": event["body"],
            "data": event.get("data", {}),
            "priority": event.get("priority", "normal"),
            "timestamp": event.get("timestamp"),
            "notification_id": event.get("notification_id"),
        }))

    # ── Helpers ───────────────────────────────────────────────────────────────

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
    def _mark_notification_read(self, notification_id: str) -> bool:
        from django.utils import timezone
        from notifications.models import Notification
        try:
            n = Notification.objects.get(id=notification_id, user=self.user)
            if not n.is_read:
                n.is_read = True
                n.read_at = timezone.now()
                n.save(update_fields=["is_read", "read_at"])
            return True
        except Notification.DoesNotExist:
            return False