"""
notifications/urls.py

REST URL registration for notification viewsets.

WebSocket is registered separately in core/asgi.py via notifications/routing.py:
    ws://host/ws/notifications/?token=<access_token>

REST endpoints registered here:
    /api/notification/shared/              → SharedNotificationViewSet (Male, Female, Wali)
    /api/notification/shared/<id>/         → retrieve
    /api/notification/shared/<id>/mark-read/
    /api/notification/shared/mark-all-read/
    /api/notification/shared/unread-count/
    /api/notification/shared/clear-read/

    /api/notification/admin/               → AdminNotificationViewSet (Matchmaker, Superadmin)
    /api/notification/admin/<id>/          → retrieve
    /api/notification/admin/<id>/mark-read/
    /api/notification/admin/mark-all-read/
    /api/notification/admin/unread-count/
    /api/notification/admin/clear-read/
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminNotificationViewSet, SharedNotificationViewSet

router = DefaultRouter()
router.register(r"shared", SharedNotificationViewSet, basename="notification-shared")
router.register(r"admin",  AdminNotificationViewSet,  basename="notification-admin")

urlpatterns = [
    path("", include(router.urls)),
]