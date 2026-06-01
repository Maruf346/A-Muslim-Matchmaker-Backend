# notifications/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import *


# router = DefaultRouter()

# router.register(r"client",  ClientNotificationViewSet,  basename="notification-client")
# router.register(r"artisan", ArtisanNotificationViewSet, basename="notification-artisan")
# router.register(r"admin",   AdminNotificationViewSet,   basename="notification-admin")


# urlpatterns = [
#     path("", include(router.urls)),
# ]

# WebSocket is registered in core/asgi.py via notifications/routing.py — not here.
# ws://host/ws/notifications/?token=<access_token>