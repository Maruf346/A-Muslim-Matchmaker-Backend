"""
chat/models.py

Models:
    ChatRoom — one per normal user (Male/Female/Wali), shared inbox for all admins
    Message  — text and/or single file attachment, with read tracking

Design notes:
    • One ChatRoom per normal user — any admin (Matchmaker/Superadmin) can
      respond, all see the same conversation (shared inbox).
    • A Message can have text, an attachment, or both (at least one required —
      validated at serializer level).
    • is_read tracks whether the OTHER side has read the message:
        - If sender is a normal user → is_read becomes True when ANY admin reads it
        - If sender is an admin → is_read becomes True when the normal user reads it
    • Attachment uses a plain FileField — no type/size restriction at model level.
"""

import os
import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


def chat_attachment_path(instance, filename):
    """Store attachments under chat/attachments/<room_id>/<filename>."""
    return f"chat/attachments/{instance.room_id}/{filename}"


class ChatRoom(models.Model):
    """
    One chat room per normal user (Male/Female/Wali).
    All admins (Matchmaker/Superadmin) share visibility into every room —
    this is the "admin inbox".
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="chat_room",
        help_text="The normal user (Male/Female/Wali) this room belongs to.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Chat Room"
        verbose_name_plural = "Chat Rooms"
        ordering            = ["-updated_at"]

    def __str__(self):
        return f"ChatRoom → {self.user.codename or self.user.email}"

    @property
    def last_message(self) -> "Message | None":
        return self.messages.order_by("-created_at").first()

    def unread_count_for(self, user) -> int:
        """
        Count unread messages FROM THE OTHER SIDE for the given user.

        If `user` is the room's normal user → counts unread admin messages.
        If `user` is an admin → counts unread messages from the normal user.
        """
        if user == self.user:
            return self.messages.filter(sender_is_admin=True, is_read=False).count()
        return self.messages.filter(sender_is_admin=False, is_read=False).count()


class Message(models.Model):
    """
    A single chat message — text and/or one file attachment.

    sender_is_admin denormalizes whether the sender was an admin at send time,
    making unread-count queries simple without joining to User.role
    (which can change over time, e.g. matchmaker → superadmin).
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="chat_messages_sent",
    )
    sender_is_admin = models.BooleanField(
        default=False,
        help_text="True if sender was an admin (Matchmaker/Superadmin) at send time.",
    )

    text       = models.TextField(blank=True, null=True)
    attachment = models.FileField(
        upload_to=chat_attachment_path,
        blank=True,
        null=True,
        help_text="Single file attachment (image, PDF, document, etc.). No type/size restriction.",
    )

    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = "Chat Message"
        verbose_name_plural = "Chat Messages"
        ordering            = ["created_at"]
        indexes = [
            models.Index(fields=["room", "created_at"]),
            models.Index(fields=["room", "sender_is_admin", "is_read"]),
        ]

    def __str__(self):
        preview = self.text[:30] if self.text else "[attachment]"
        return f"{self.sender.codename if self.sender else 'unknown'}: {preview}"

    @property
    def attachment_filename(self) -> str | None:
        if not self.attachment:
            return None
        return os.path.basename(self.attachment.name)

    @property
    def preview_text(self) -> str:
        """Used for admin inbox 'last message' preview."""
        if self.text:
            return self.text
        if self.attachment:
            return "Sent an attachment"
        return ""