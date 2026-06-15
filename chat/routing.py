"""
chat/routing.py

WebSocket URL patterns for the chat consumer.
Included in core/asgi.py — not in Django's HTTP URL conf.

WebSocket endpoint:
    ws://host/ws/chat/<room_id>/?token=<access_token>

Access:
    - Normal user (Male/Female/Wali) → only their own room
    - Admin (Matchmaker/Superadmin)  → any room (shared inbox)
    Unauthorized connections rejected with close code 4001 (unauthenticated)
    or 4003 (no access to this room).
"""

from django.urls import path

from .consumers import ChatConsumer

websocket_urlpatterns = [
    path("ws/chat/<uuid:room_id>/", ChatConsumer.as_asgi()),
]
