# user/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import *

urlpatterns = [
    
    # ── Client registration ───────────────────────────────────────────────────
    path("client/register/initiate/", ClientInitiateRegistrationView.as_view(), name="client-register-initiate"),
    path("client/register/verify/",   ClientVerifyRegistrationView.as_view(),   name="client-register-verify"),
    path("client/login/",             ClientLoginView.as_view(),                name="client-login"),

    # ── Artisan registration ──────────────────────────────────────────────────
    path("artisan/register/initiate/", ArtisanInitiateRegistrationView.as_view(), name="artisan-register-initiate"),
    path("artisan/register/verify/",   ArtisanVerifyRegistrationView.as_view(),   name="artisan-register-verify"),
    path("artisan/login/",             ArtisanLoginView.as_view(),                name="artisan-login"),

    # ── Admin auth ────────────────────────────────────────────────────────────
    path("admin/login/",  AdminLoginView.as_view(),  name="admin-login"),
    path("admin/profile/", AdminProfileView.as_view(), name="admin-profile"),

    # ── Shared auth ───────────────────────────────────────────────────────────
    path("logout/",                  LogoutView.as_view(),                name="logout"),
    path("password/change/",         ChangePasswordView.as_view(),         name="password-change"),
    path("password-reset/initiate/", InitiatePasswordResetView.as_view(),  name="password-reset-initiate"),
    path("password-reset/verify/",   VerifyPasswordResetOTPView.as_view(), name="password-reset-verify"),
    path("password-reset/confirm/",  ResetPasswordView.as_view(),          name="password-reset-confirm"),

    # ── OAuth ─────────────────────────────────────────────────────────────────
    path("auth/google/", GoogleOAuthView.as_view(), name="google-oauth"),
    path("auth/apple/",  AppleOAuthView.as_view(),  name="apple-oauth"),
]