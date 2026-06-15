"""
core/asgi.py

ASGI configuration for AMM (A Muslim Matchmaker).

Handles both:
    HTTP  → Django's standard ASGI application
    WS    → Django Channels with Redis channel layer

Why no AllowedHostsOriginValidator:
    Mobile apps and non-browser clients (Flutter, Postman) don't send an Origin
    header — the validator would reject them with 403. Auth is already enforced
    inside each consumer via JWT in the query string. Nginx restricts hosts at
    the network level in production.

WebSocket routes:
    ws://host/ws/notifications/?token=<jwt>   → NotificationConsumer (admin only)
    ws://host/ws/chat/<room_id>/?token=<jwt>  → ChatConsumer (normal user: own room; admin: any room)
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

django_asgi_app = get_asgi_application()

from notifications.routing import websocket_urlpatterns as notification_ws
from chat.routing import websocket_urlpatterns as chat_ws

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            notification_ws
            + chat_ws
        )
    ),
})