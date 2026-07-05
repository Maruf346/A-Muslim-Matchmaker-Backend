"""
private_matches/urls.py

Registered at: /api/private-matches/ (add to api/urls.py)

Full endpoint map:
    ── Client ────────────────────────────────────────────────────────────────
    GET  /api/private-matches/my-suggestions/
    POST /api/private-matches/my-suggestions/<suggestion_id>/respond/

    ── Prospect ──────────────────────────────────────────────────────────────
    GET  /api/private-matches/my-special-matches/
    POST /api/private-matches/my-special-matches/<suggestion_id>/respond/

    ── Admin ─────────────────────────────────────────────────────────────────
    POST /api/private-matches/admin/suggestions/create/
    GET  /api/private-matches/admin/suggestions/
    GET  /api/private-matches/admin/suggestions/<pk>/
    GET  /api/private-matches/admin/prospects/
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import *


router = DefaultRouter()
router.register(r"admin/suggestions", AdminSuggestionViewSet, basename="admin-pm-suggestions")

urlpatterns = [
    # ── Client ────────────────────────────────────────────────────────────────
    path("my-suggestions/", MySuggestionsView.as_view(), name="pm-my-suggestions"),
    path(
        "my-suggestions/<uuid:suggestion_id>/respond/",
        ClientRespondView.as_view(),
        name="pm-client-respond",
    ),

    # ── Prospect ──────────────────────────────────────────────────────────────
    path("my-special-matches/", MySpecialMatchesView.as_view(), name="pm-special-matches"),
    path(
        "my-special-matches/<uuid:suggestion_id>/respond/",
        ProspectRespondView.as_view(),
        name="pm-prospect-respond",
    ),

    # ── Admin ─────────────────────────────────────────────────────────────────
    path("admin/suggestions/create/", AdminCreateSuggestionView.as_view(), name="pm-admin-create"),
    path("admin/prospects/",          AdminProspectDirectoryView.as_view(), name="pm-admin-prospects"),

    # ── Admin viewset (list/detail) ───────────────────────────────────────────
    path("", include(router.urls)),
]
