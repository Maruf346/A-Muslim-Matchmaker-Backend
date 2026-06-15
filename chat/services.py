"""
chat/services.py

Service layer for the chat app.

Classes:
    ChatService — room get-or-create, send message, mark as read,
                  push real-time updates over the chat WebSocket.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from .models import ChatRoom, Message

logger = logging.getLogger(__name__)


class ChatService:

    # ── Room management ──────────────────────────────────────────────────────

    @staticmethod
    def get_or_create_room(user) -> ChatRoom:
        """Get or create the chat room for a normal user (Male/Female/Wali)."""
        room, _ = ChatRoom.objects.get_or_create(user=user)
        return room

    # ── Sending messages ──────────────────────────────────────────────────────

    @staticmethod
    def send_message(room: ChatRoom, sender, text: str | None, attachment=None) -> Message:
        """
        Create a new message in the room and push it over the chat WebSocket
        to all connected participants (the room's user + any admins viewing it).

        Also sends a `new_message` notification (DB + WS for admin, DB-only
        for normal users) via NotificationTemplates.
        """
        sender_is_admin = getattr(sender, "is_admin_user", False)

        message = Message.objects.create(
            room=room,
            sender=sender,
            sender_is_admin=sender_is_admin,
            text=text,
            attachment=attachment,
        )

        # Touch room.updated_at for inbox ordering
        room.save(update_fields=["updated_at"])

        ChatService._push_ws_message(room, message)
        ChatService._send_notification(room, message, sender, sender_is_admin)

        return message

    # ── Read tracking ─────────────────────────────────────────────────────────

    @staticmethod
    def mark_messages_read(room: ChatRoom, reader) -> int:
        """
        Mark all unread messages FROM THE OTHER SIDE as read.

        If reader is the room's normal user → marks admin messages as read.
        If reader is an admin → marks the normal user's messages as read.

        Returns the number of messages marked.
        """
        reader_is_admin = getattr(reader, "is_admin_user", False)

        # Messages to mark: sent by the OTHER side
        qs = room.messages.filter(is_read=False)
        if reader_is_admin:
            qs = qs.filter(sender_is_admin=False)
        else:
            qs = qs.filter(sender_is_admin=True)

        message_ids = list(qs.values_list("id", flat=True))
        if not message_ids:
            return 0

        count = qs.update(is_read=True, read_at=timezone.now())

        ChatService._push_ws_read_receipt(room, message_ids, reader)

        return count

    # ── WebSocket push helpers ───────────────────────────────────────────────

    @staticmethod
    def _push_ws_message(room: ChatRoom, message: Message) -> None:
        """Push the new message to ws/chat/<room_id>/ group."""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"chat_{room.id}",
                {
                    "type":    "chat_message",
                    "message": {
                        "id":              str(message.id),
                        "room":            str(room.id),
                        "sender_id":       str(message.sender.id) if message.sender else None,
                        "sender_codename": message.sender.codename if message.sender else None,
                        "sender_name":     message.sender.full_name if message.sender else None,
                        "sender_is_admin": message.sender_is_admin,
                        "text":            message.text,
                        "attachment_url":  message.attachment.url if message.attachment else None,
                        "attachment_name": message.attachment_filename,
                        "is_read":         message.is_read,
                        "created_at":      message.created_at.isoformat(),
                    },
                },
            )
        except Exception as exc:
            logger.error("Failed to push chat message over WS for room %s: %s", room.id, exc)

    @staticmethod
    def _push_ws_read_receipt(room: ChatRoom, message_ids: list, reader) -> None:
        """Push a read-receipt event to ws/chat/<room_id>/ group."""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"chat_{room.id}",
                {
                    "type":       "read_receipt",
                    "message_ids": [str(mid) for mid in message_ids],
                    "read_by":     str(reader.id),
                    "read_at":     timezone.now().isoformat(),
                },
            )
        except Exception as exc:
            logger.error("Failed to push read receipt over WS for room %s: %s", room.id, exc)

    # ── Notification ──────────────────────────────────────────────────────────

    @staticmethod
    def _send_notification(room: ChatRoom, message: Message, sender, sender_is_admin: bool) -> None:
        """
        Notify the recipient(s) of a new message.

        - If sender is a normal user → notify all admins (DB + WS).
        - If sender is an admin → notify the normal user (DB only, REST poll).
        """
        from notifications.services import NotificationTemplates

        sender_name = sender.full_name if sender_is_admin else (sender.codename if sender else "User")

        try:
            if sender_is_admin:
                NotificationTemplates.new_message(
                    receiver=room.user,
                    sender_name=sender_name,
                    room_id=str(room.id),
                )
            else:
                # Notify all admins
                from users.models import User, UserRole
                admins = User.objects.filter(
                    role__in=[UserRole.MATCHMAKER, UserRole.SUPERADMIN],
                    is_active=True,
                )
                for admin in admins:
                    NotificationTemplates.new_message(
                        receiver=admin,
                        sender_name=sender_name,
                        room_id=str(room.id),
                    )
        except Exception:
            logger.exception("Failed to send new_message notification for room %s", room.id)
