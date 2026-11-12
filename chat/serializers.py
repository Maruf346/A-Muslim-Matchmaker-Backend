"""
chat/serializers.py

Organized by concern:
    1. Messages — send (text/attachment), list, read-tracking
    2. Chat room — user-side (single room) and admin-side (inbox list/detail)
"""

from rest_framework import serializers

from core.utils import format_last_active_display

from .models import ChatRoom, Message


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────────────────────────────────────

def _last_active_display(user) -> str | None:
    return format_last_active_display(user)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Messages
# ─────────────────────────────────────────────────────────────────────────────

class MessageSerializer(serializers.ModelSerializer):
    """
    Read representation of a chat message.
    Includes sender info, timestamp, and attachment metadata (with absolute URL).
    """
    sender_id       = serializers.SerializerMethodField()
    sender_codename = serializers.SerializerMethodField()
    sender_name     = serializers.SerializerMethodField()
    attachment_url  = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()

    class Meta:
        model  = Message
        fields = [
            "id", "room",
            "sender_id", "sender_codename", "sender_name", "sender_is_admin",
            "text",
            "attachment_url", "attachment_name",
            "is_read", "read_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_sender_id(self, obj) -> str | None:
        return str(obj.sender.id) if obj.sender else None

    def get_sender_codename(self, obj) -> str | None:
        return obj.sender.codename if obj.sender else None

    def get_sender_name(self, obj) -> str | None:
        """
        For normal users: full_name once mutual-context applies — but in chat,
        the user is talking directly to admin, so full_name is always shown
        for the sender's own messages (no blurring rules apply to chat).
        For admins: their own full_name.
        """
        return obj.sender.full_name if obj.sender else None

    def get_attachment_url(self, obj) -> str | None:
        if not obj.attachment:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.attachment.url)
        return obj.attachment.url

    def get_attachment_name(self, obj) -> str | None:
        return obj.attachment_filename


class SendMessageSerializer(serializers.Serializer):
    """
    Payload for sending a message.
    At least one of `text` or `attachment` must be provided.
    """
    text       = serializers.CharField(required=False, allow_blank=True)
    attachment = serializers.FileField(required=False, allow_null=True)

    def validate(self, data):
        text       = data.get("text", "").strip() if data.get("text") else ""
        attachment = data.get("attachment")
        if not text and not attachment:
            raise serializers.ValidationError(
                "A message must contain text, an attachment, or both."
            )
        data["text"] = text or None
        return data


# ─────────────────────────────────────────────────────────────────────────────
# 2. Chat Room — User side
# ─────────────────────────────────────────────────────────────────────────────

class UserChatRoomSerializer(serializers.ModelSerializer):
    """
    The normal user's view of their own chat room.
    Includes unread count (unread admin messages).
    """
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model  = ChatRoom
        fields = ["id", "unread_count", "last_message", "created_at", "updated_at"]
        read_only_fields = fields

    def get_unread_count(self, obj) -> int:
        request = self.context.get("request")
        user    = request.user if request else obj.user
        return obj.unread_count_for(user)

    def get_last_message(self, obj) -> dict | None:
        msg = obj.last_message
        if not msg:
            return None
        return MessageSerializer(msg, context=self.context).data


# ─────────────────────────────────────────────────────────────────────────────
# 2b. Chat Room — Admin side (inbox)
# ─────────────────────────────────────────────────────────────────────────────

class AdminChatRoomListSerializer(serializers.ModelSerializer):
    """
    Admin inbox list item.

    Includes:
        - The normal user's identity (codename, full_name, profile picture)
        - Last message preview (text or "Sent an attachment")
        - Last message timestamp
        - Unread count (unread user messages, for admin)
        - User's online/last-active status
    """
    user_id              = serializers.SerializerMethodField()
    codename             = serializers.SerializerMethodField()
    full_name            = serializers.SerializerMethodField()
    profile_picture      = serializers.SerializerMethodField()
    role                 = serializers.SerializerMethodField()
    last_active          = serializers.SerializerMethodField()
    last_active_display  = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    last_message_at      = serializers.SerializerMethodField()
    unread_count         = serializers.SerializerMethodField()

    class Meta:
        model  = ChatRoom
        fields = [
            "id",
            "user_id", "codename", "full_name", "profile_picture", "role",
            "last_active", "last_active_display",
            "last_message_preview", "last_message_at",
            "unread_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_id(self, obj) -> str:
        return str(obj.user.id)

    def get_codename(self, obj) -> str:
        return obj.user.codename

    def get_full_name(self, obj) -> str:
        return obj.user.full_name

    def get_profile_picture(self, obj) -> str | None:
        if not obj.user.profile_picture:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.user.profile_picture.url)
        return obj.user.profile_picture.url

    def get_role(self, obj) -> str:
        return obj.user.role

    def get_last_active(self, obj):
        return obj.user.last_active

    def get_last_active_display(self, obj) -> str | None:
        return _last_active_display(obj.user)

    def get_last_message_preview(self, obj) -> str | None:
        msg = obj.last_message
        return msg.preview_text if msg else None

    def get_last_message_at(self, obj):
        msg = obj.last_message
        return msg.created_at if msg else None

    def get_unread_count(self, obj) -> int:
        """Unread messages from the normal user (admin's perspective)."""
        return obj.messages.filter(sender_is_admin=False, is_read=False).count()


class AdminChatRoomDetailSerializer(AdminChatRoomListSerializer):
    """Extended detail — same fields as list for now, room for future expansion."""
    pass
