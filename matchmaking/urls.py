"""
matchmaking/urls.py
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import AdminMatchmakingRequestViewSet, AdminPrivateClientListView, MyMatchmakingRequestView

router = DefaultRouter()
router.register(r"admin/requests", AdminMatchmakingRequestViewSet, basename="admin-pm-requests")

urlpatterns = [
    path("my-request/",          MyMatchmakingRequestView.as_view(),  name="my-pm-request"),
    path("admin/clients/",       AdminPrivateClientListView.as_view(), name="admin-pm-clients"),
    path("", include(router.urls)),
]


