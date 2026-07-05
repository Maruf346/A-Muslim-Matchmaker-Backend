"""
questions/urls.py

Registered at: /api/questions/ (add to api/urls.py)

Full endpoint map:
    ── Choices (all roles) ───────────────────────────────────────────────────
    GET  /api/questions/choices/                    ChoicesView

    ── Male ─────────────────────────────────────────────────────────────────
    GET  /api/questions/male/basic-info/            MaleBasicInfoView
    PATCH /api/questions/male/basic-info/           MaleBasicInfoView
    GET  /api/questions/male/photos/                MalePhotosView
    POST /api/questions/male/photos/                MalePhotosView
    DELETE /api/questions/male/photos/<photo_id>/   MalePhotoDetailView
    PATCH  /api/questions/male/photos/<photo_id>/   MalePhotoDetailView

    ── Female ───────────────────────────────────────────────────────────────
    GET  /api/questions/female/basic-info/          FemaleBasicInfoView
    PATCH /api/questions/female/basic-info/         FemaleBasicInfoView
    GET  /api/questions/female/photos/              FemalePhotosView
    POST /api/questions/female/photos/              FemalePhotosView
    DELETE /api/questions/female/photos/<photo_id>/ FemalePhotoDetailView
    PATCH  /api/questions/female/photos/<photo_id>/ FemalePhotoDetailView

    ── Wali ─────────────────────────────────────────────────────────────────
    GET  /api/questions/wali/profile/               WaliProfileView  (Step 1)
    PATCH /api/questions/wali/profile/              WaliProfileView
    GET  /api/questions/wali/basic-info/            WaliBasicInfoView (Steps 2–4)
    PATCH /api/questions/wali/basic-info/           WaliBasicInfoView
    GET  /api/questions/wali/photos/                WaliPhotosView
    POST /api/questions/wali/photos/                WaliPhotosView
    DELETE /api/questions/wali/photos/<photo_id>/   WaliPhotoDetailView
    PATCH  /api/questions/wali/photos/<photo_id>/   WaliPhotoDetailView

    ── Admin ─────────────────────────────────────────────────────────────────
    GET  /api/questions/admin/users/<user_id>/      AdminUserBasicInfoView
    PATCH /api/questions/admin/users/<user_id>/     AdminUserBasicInfoView
"""

from django.urls import path

from .views import *

urlpatterns = [
    # ── Choices ───────────────────────────────────────────────────────────────
    path("choices/", ChoicesView.as_view(), name="questions-choices"),

    # ── Male ──────────────────────────────────────────────────────────────────
    path("male/basic-info/",          MaleBasicInfoView.as_view(),          name="male-basic-info"),
    path("male/photos/",              MalePhotosView.as_view(),              name="male-photos"),
    path("male/photos/<uuid:photo_id>/", MalePhotoDetailView.as_view(),     name="male-photo-detail"),

    # ── Female ────────────────────────────────────────────────────────────────
    path("female/basic-info/",           FemaleBasicInfoView.as_view(),        name="female-basic-info"),
    path("female/photos/",               FemalePhotosView.as_view(),           name="female-photos"),
    path("female/photos/<uuid:photo_id>/", FemalePhotoDetailView.as_view(),    name="female-photo-detail"),

    # ── Wali ──────────────────────────────────────────────────────────────────
    path("wali/profile/",             WaliProfileView.as_view(),             name="wali-profile"),
    path("wali/basic-info/",          WaliBasicInfoView.as_view(),           name="wali-basic-info"),
    path("wali/photos/",              WaliPhotosView.as_view(),              name="wali-photos"),
    path("wali/photos/<uuid:photo_id>/", WaliPhotoDetailView.as_view(),      name="wali-photo-detail"),

    # ── Admin ─────────────────────────────────────────────────────────────────
    path("admin/users/<uuid:user_id>/", AdminUserBasicInfoView.as_view(),   name="admin-user-basic-info"),
]
