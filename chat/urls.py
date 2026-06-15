"""
chat/urls.py

Registered at: /api/chat/ (add to api/urls.py)

WebSocket is registered separately in core/asgi.py via chat/routing.py:
    ws://host/ws/chat/<room_id>/?token=<access_token>

Full endpoint map:
    ── User side ────────────────────────────────────────────────────────────
    GET  /api/chat/my-room/                          MyChatRoomView
    GET  /api/chat/my-room/messages/                 MyMessagesView (list)
    POST /api/chat/my-room/messages/                 MyMessagesView (send)
    POST /api/chat/my-room/mark-read/                MyMarkReadView
    GET  /api/chat/my-room/messages/<message_id>/download/  MyAttachmentDownloadView

    ── Admin side ───────────────────────────────────────────────────────────
    GET  /api/chat/admin/rooms/                      AdminChatRoomViewSet (list — inbox)
    GET  /api/chat/admin/rooms/<room_id>/            AdminChatRoomViewSet (retrieve)
    GET  /api/chat/admin/rooms/<room_id>/messages/   AdminMessagesView (list)
    POST /api/chat/admin/rooms/<room_id>/messages/   AdminMessagesView (send)
    POST /api/chat/admin/rooms/<room_id>/mark-read/  AdminMarkReadView
    GET  /api/chat/admin/rooms/<room_id>/messages/<message_id>/download/  AdminAttachmentDownloadView
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminAttachmentDownloadView,
    AdminChatRoomViewSet,
    AdminMarkReadView,
    AdminMessagesView,
    MyAttachmentDownloadView,
    MyChatRoomView,
    MyMarkReadView,
    MyMessagesView,
)

router = DefaultRouter()
router.register(r"admin/rooms", AdminChatRoomViewSet, basename="admin-chat-rooms")

urlpatterns = [
    # ── User side ─────────────────────────────────────────────────────────────
    path("my-room/",                       MyChatRoomView.as_view(),   name="my-chat-room"),
    path("my-room/messages/",              MyMessagesView.as_view(),   name="my-chat-messages"),
    path("my-room/mark-read/",             MyMarkReadView.as_view(),   name="my-chat-mark-read"),
    path(
        "my-room/messages/<uuid:message_id>/download/",
        MyAttachmentDownloadView.as_view(),
        name="my-chat-attachment-download",
    ),

    # ── Admin side ────────────────────────────────────────────────────────────
    path(
        "admin/rooms/<uuid:room_id>/messages/",
        AdminMessagesView.as_view(),
        name="admin-chat-messages",
    ),
    path(
        "admin/rooms/<uuid:room_id>/mark-read/",
        AdminMarkReadView.as_view(),
        name="admin-chat-mark-read",
    ),
    path(
        "admin/rooms/<uuid:room_id>/messages/<uuid:message_id>/download/",
        AdminAttachmentDownloadView.as_view(),
        name="admin-chat-attachment-download",
    ),

    # ── Admin inbox (router) ──────────────────────────────────────────────────
    path("", include(router.urls)),
]
