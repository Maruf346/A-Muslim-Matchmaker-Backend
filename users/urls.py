"""
users/urls.py

URL configuration for the users app.

Registered at: /api/user/ (from api/urls.py)

Full endpoint map:
    ── Male registration ────────────────────────────────────────────
    POST /api/user/male/register/initiate/      MaleInitiateRegistrationView
    POST /api/user/male/register/verify/        MaleVerifyRegistrationView
    POST /api/user/male/login/                  MaleLoginView

    ── Female registration ───────────────────────────────────────────
    POST /api/user/female/register/initiate/    FemaleInitiateRegistrationView
    POST /api/user/female/register/verify/      FemaleVerifyRegistrationView
    POST /api/user/female/login/                FemaleLoginView

    ── Wali registration ─────────────────────────────────────────────
    POST /api/user/wali/register/initiate/      WaliInitiateRegistrationView
    POST /api/user/wali/register/verify/        WaliVerifyRegistrationView
    POST /api/user/wali/login/                  WaliLoginView

    ── Admin auth ────────────────────────────────────────────────────
    POST /api/user/admin/login/                 AdminLoginView          (Step 1: submit credentials, sends OTP)
    POST /api/user/admin/login/verify/          AdminLoginVerifyOTPView (Step 2: submit OTP, receive JWT tokens)
    POST /api/user/admin/login/resend-otp/      AdminLoginResendOTPView (Resend OTP, 60s cooldown)
    GET  /api/user/admin/profile/               AdminProfileView
    PATCH /api/user/admin/profile/              AdminProfileView

    ── Admin — user management ───────────────────────────────────────
    GET  /api/user/admin/users/                 AdminUserViewSet (list)
    GET  /api/user/admin/users/{id}/            AdminUserViewSet (retrieve)
    PATCH /api/user/admin/users/{id}/block/     AdminUserViewSet.block
    PATCH /api/user/admin/users/{id}/verification/ AdminUserViewSet.verification
    DELETE /api/user/admin/users/{id}/delete/   AdminUserViewSet.delete_user

    ── Admin — why leaving ───────────────────────────────────────
    GET  /api/user/admin/why-leavings/          WhyLeavingViewSet (list)
    GET  /api/user/admin/why-leavings/{id}/     WhyLeavingViewSet (retrieve)
    POST /api/user/admin/why-leavings/          WhyLeavingViewSet (create)
    PATCH /api/user/admin/why-leavings/{id}/    WhyLeavingViewSet (partial update)
    PUT  /api/user/admin/why-leavings/{id}/     WhyLeavingViewSet (update)
    DELETE /api/user/admin/why-leavings/{id}/   WhyLeavingViewSet (destroy)

    ── Admin — matchmaker management (superadmin only) ──────────────
    GET  /api/user/admin/matchmakers/                       MatchmakerViewSet (list)
    GET  /api/user/admin/matchmakers/{id}/                  MatchmakerViewSet (retrieve)
    POST /api/user/admin/matchmakers/create-matchmaker/     MatchmakerViewSet.create_matchmaker
    PATCH /api/user/admin/matchmakers/{id}/change-role/     MatchmakerViewSet.change_role
    DELETE /api/user/admin/matchmakers/{id}/delete/         MatchmakerViewSet.delete_matchmaker

    ── Shared auth (all roles) ───────────────────────────────────────
    POST /api/user/logout/                      LogoutView
    POST /api/user/password/change/             ChangePasswordView
    POST /api/user/password-reset/initiate/     InitiatePasswordResetView
    POST /api/user/password-reset/verify/       VerifyPasswordResetOTPView
    POST /api/user/password-reset/confirm/      ResetPasswordView
    POST /api/user/register/resend-otp/         ResendRegistrationOTPView

    ── OAuth ─────────────────────────────────────────────────────────
    POST /api/user/auth/google/                 GoogleOAuthView
    POST /api/user/auth/apple/                  AppleOAuthView

    ── User profile (male / female / wali) ──────────────────────────
    GET  /api/user/profile/                     UserProfileView
    PATCH /api/user/profile/                    UserProfileView
    DELETE /api/user/profile/                   UserProfileView
    PATCH /api/user/profile/picture/            UpdateProfilePictureView
    POST /api/user/profile/deactivate/          DeactivateAccountView
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import *

# ViewSet routers
router = DefaultRouter()
router.register(r"admin/users",        AdminUserViewSet,   basename="admin-users")
router.register(r"admin/why-leavings", WhyLeavingViewSet, basename="admin-why-leavings")
router.register(r"admin/matchmakers",  MatchmakerViewSet,  basename="admin-matchmakers")

urlpatterns = [
    # ── Unified Login ─────────────────────────────────────────────────────────
    path("login/",                  UserLoginView.as_view(),                name="user-login"),

    # ── Male ──────────────────────────────────────────────────────────────────
    path("male/register/initiate/", MaleInitiateRegistrationView.as_view(), name="male-register-initiate"),
    path("male/register/verify/",   MaleVerifyRegistrationView.as_view(),   name="male-register-verify"),
    path("male/login/",             MaleLoginView.as_view(),                name="male-login"),

    # ── Female ────────────────────────────────────────────────────────────────
    path("female/register/initiate/", FemaleInitiateRegistrationView.as_view(), name="female-register-initiate"),
    path("female/register/verify/",   FemaleVerifyRegistrationView.as_view(),   name="female-register-verify"),
    path("female/login/",             FemaleLoginView.as_view(),                name="female-login"),

    # ── Wali ──────────────────────────────────────────────────────────────────
    path("wali/register/initiate/", WaliInitiateRegistrationView.as_view(), name="wali-register-initiate"),
    path("wali/register/verify/",   WaliVerifyRegistrationView.as_view(),   name="wali-register-verify"),
    path("wali/login/",             WaliLoginView.as_view(),                name="wali-login"),

    # ── Admin auth ────────────────────────────────────────────────────────────
    path("admin/login/",            AdminLoginView.as_view(),            name="admin-login"),
    path("admin/login/verify/",     AdminLoginVerifyOTPView.as_view(),   name="admin-login-verify"),
    path("admin/login/resend-otp/", AdminLoginResendOTPView.as_view(),   name="admin-login-resend-otp"),
    path("admin/profile/",          AdminProfileView.as_view(),          name="admin-profile"),

    # ── Shared auth ───────────────────────────────────────────────────────────
    path("logout/",                  LogoutView.as_view(),                name="logout"),
    path("password/change/",         ChangePasswordView.as_view(),        name="password-change"),
    path("password-reset/initiate/", InitiatePasswordResetView.as_view(), name="password-reset-initiate"),
    path("password-reset/verify/",   VerifyPasswordResetOTPView.as_view(),name="password-reset-verify"),
    path("password-reset/confirm/",  ResetPasswordView.as_view(),         name="password-reset-confirm"),
    path("register/resend-otp/",     ResendRegistrationOTPView.as_view(), name="register-resend-otp"),

    # ── OAuth ─────────────────────────────────────────────────────────────────
    path("auth/google/", GoogleOAuthView.as_view(), name="google-oauth"),
    path("auth/apple/",  AppleOAuthView.as_view(),  name="apple-oauth"),

    # ── User profile ──────────────────────────────────────────────────────────
    path("profile/",          UserProfileView.as_view(),         name="user-profile"),
    path("profile/picture/",  UpdateProfilePictureView.as_view(),name="user-profile-picture"),
    path("profile/deactivate/",DeactivateAccountView.as_view(), name="user-deactivate"),
    path("why-leaving/",      WhyLeavingView.as_view(),         name="why-leaving"),

    # ── ViewSet routes (admin/users, admin/matchmakers) ───────────────────────
    path("", include(router.urls)),
]
