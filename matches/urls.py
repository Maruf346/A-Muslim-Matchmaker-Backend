"""
matches/urls.py

Registered at: /api/matches/ (add to api/urls.py)

Full endpoint map:
    ── Directory ────────────────────────────────────────────────────────────
    GET  /api/matches/directory/                          DirectoryListView

    ── Connection requests ─────────────────────────────────────────────────
    POST   /api/matches/requests/send/                    SendConnectionRequestView
    POST   /api/matches/requests/resend/                  ResendRequestView
    GET    /api/matches/requests/sent/                    SentRequestsListView
    GET    /api/matches/requests/received/                ReceivedRequestsListView
    PATCH  /api/matches/requests/<pk>/respond/?action=    RespondToRequestView
    DELETE /api/matches/requests/<pk>/cancel/             CancelPendingRequestView

    ── Matches ──────────────────────────────────────────────────────────────
    GET  /api/matches/                                    MatchListView
    GET  /api/matches/<pk>/                               MatchDetailView
    POST /api/matches/<pk>/cancel/                        CancelMatchView
    POST /api/matches/<pk>/mark-married/                  MarkMarriedView
    POST /api/matches/<pk>/unlock/                        UnlockMatchView

    ── Photos ───────────────────────────────────────────────────────────────
    POST  /api/matches/<pk>/photos/request/               RequestPhotoViewView
    PATCH /api/matches/<pk>/photos/respond/?action=       RespondToPhotoRequestView
    POST  /api/matches/<pk>/photos/mark-viewed/           MarkPhotosViewedView

    ── Wali ─────────────────────────────────────────────────────────────────
    POST  /api/matches/<pk>/wali/request/                 SendWaliRequestView
    PATCH /api/matches/<pk>/wali/respond/?action=         RespondToWaliRequestView

    ── Subscription usage ──────────────────────────────────────────────────
    GET  /api/matches/usage/                              ConnectionUsageView

    ── Admin ────────────────────────────────────────────────────────────────
    GET   /api/matches/admin/matches/                     AdminMatchViewSet (list)
    GET   /api/matches/admin/matches/<pk>/                AdminMatchViewSet (retrieve)
    PATCH /api/matches/admin/matches/<pk>/override-status/ AdminMatchViewSet.override_status
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import *

router = DefaultRouter()
router.register(r"admin/matches", AdminMatchViewSet, basename="admin-matches")

urlpatterns = [
    # ── Directory ────────────────────────────────────────────────────────────
    path("directory/", DirectoryListView.as_view(), name="directory-list"),

    # ── Connection requests ──────────────────────────────────────────────────
    path("requests/send/",              SendConnectionRequestView.as_view(), name="request-send"),
    path("requests/resend/",            ResendRequestView.as_view(),         name="request-resend"),
    path("requests/sent/",              SentRequestsListView.as_view(),      name="request-sent"),
    path("requests/received/",          ReceivedRequestsListView.as_view(),  name="request-received"),
    path("requests/<uuid:pk>/respond/", RespondToRequestView.as_view(),      name="request-respond"),
    path("requests/<uuid:pk>/cancel/",  CancelPendingRequestView.as_view(),  name="request-cancel"),

    # ── Subscription usage ───────────────────────────────────────────────────
    path("usage/", ConnectionUsageView.as_view(), name="connection-usage"),

    # ── Matches ───────────────────────────────────────────────────────────────
    path("<uuid:pk>/cancel/",        CancelMatchView.as_view(),   name="match-cancel"),
    path("<uuid:pk>/mark-married/",  MarkMarriedView.as_view(),   name="match-mark-married"),
    path("<uuid:pk>/unlock/",        UnlockMatchView.as_view(),   name="match-unlock"),

    # ── Photos ────────────────────────────────────────────────────────────────
    path("<uuid:pk>/photos/request/",     RequestPhotoViewView.as_view(),     name="match-photo-request"),
    path("<uuid:pk>/photos/respond/",     RespondToPhotoRequestView.as_view(),name="match-photo-respond"),
    path("<uuid:pk>/photos/mark-viewed/", MarkPhotosViewedView.as_view(),     name="match-photo-mark-viewed"),

    # ── Wali ──────────────────────────────────────────────────────────────────
    path("<uuid:pk>/wali/request/", SendWaliRequestView.as_view(),       name="match-wali-request"),
    path("<uuid:pk>/wali/respond/", RespondToWaliRequestView.as_view(),  name="match-wali-respond"),

    # ── Admin (router) ────────────────────────────────────────────────────────
    path("", include(router.urls)),

    # ── Match list/detail (must come after specific paths to avoid conflicts) ──
    path("", MatchListView.as_view(), name="match-list"),
    path("<uuid:pk>/", MatchDetailView.as_view(), name="match-detail"),
]