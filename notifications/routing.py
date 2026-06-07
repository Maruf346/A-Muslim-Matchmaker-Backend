"""
notifications/routing.py

WebSocket URL patterns for the notifications consumer.
Included in core/asgi.py — not in Django's HTTP URL conf.

WebSocket endpoint:
    ws://host/ws/notifications/?token=<access_token>

Access: Admin only (Matchmaker & Superadmin).
Non-admin connections are rejected with close code 4003.
Unauthenticated connections are rejected with close code 4001.
"""

from django.urls import path

from .consumers import NotificationConsumer

websocket_urlpatterns = [
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
