"""
wishlists/urls.py

Registered at: /api/wishlists/ (add to api/urls.py)

Full endpoint map:
    ── Saved profiles ──────────────────────────────────────────────────────
    POST /api/wishlists/saved/toggle/         ToggleSaveProfileView
    GET  /api/wishlists/saved/                SavedProfilesListView

    ── Profile views ────────────────────────────────────────────────────────
    GET  /api/wishlists/viewers/              ProfileViewersListView

    ── Block ────────────────────────────────────────────────────────────────
    POST /api/wishlists/block/toggle/         ToggleBlockProfileView
    GET  /api/wishlists/block/                BlockedProfilesListView

    ── Hide ─────────────────────────────────────────────────────────────────
    POST /api/wishlists/hide/toggle/          ToggleHideProfileView
    GET  /api/wishlists/hide/                 HiddenProfilesListView

    ── Report ───────────────────────────────────────────────────────────────
    POST /api/wishlists/report/               CreateReportView

    ── Admin ────────────────────────────────────────────────────────────────
    GET   /api/wishlists/admin/reports/                  AdminReportViewSet (list)
    GET   /api/wishlists/admin/reports/<pk>/             AdminReportViewSet (retrieve)
    PATCH /api/wishlists/admin/reports/<pk>/update-status/ AdminReportViewSet.update_status
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminReportViewSet,
    BlockedProfilesListView,
    CreateReportView,
    HiddenProfilesListView,
    ProfileViewersListView,
    SavedProfilesListView,
    ToggleBlockProfileView,
    ToggleHideProfileView,
    ToggleSaveProfileView,
)

router = DefaultRouter()
router.register(r"admin/reports", AdminReportViewSet, basename="admin-reports")

urlpatterns = [
    # ── Saved profiles ────────────────────────────────────────────────────────
    path("saved/toggle/", ToggleSaveProfileView.as_view(), name="saved-toggle"),
    path("saved/",        SavedProfilesListView.as_view(), name="saved-list"),

    # ── Profile views ─────────────────────────────────────────────────────────
    path("viewers/", ProfileViewersListView.as_view(), name="profile-viewers"),

    # ── Block ─────────────────────────────────────────────────────────────────
    path("block/toggle/", ToggleBlockProfileView.as_view(), name="block-toggle"),
    path("block/",        BlockedProfilesListView.as_view(), name="block-list"),

    # ── Hide ──────────────────────────────────────────────────────────────────
    path("hide/toggle/", ToggleHideProfileView.as_view(), name="hide-toggle"),
    path("hide/",        HiddenProfilesListView.as_view(), name="hide-list"),

    # ── Report ────────────────────────────────────────────────────────────────
    path("report/", CreateReportView.as_view(), name="report-create"),

    # ── Admin ─────────────────────────────────────────────────────────────────
    path("", include(router.urls)),
]
