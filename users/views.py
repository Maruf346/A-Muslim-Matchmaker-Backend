"""
users/views.py

Swagger tag strategy:
    Auth - Male         — male register / login
    Auth - Female       — female register / login
    Auth - Wali         — wali register / login
    Auth - Admin        — admin login (matchmaker + superadmin shared)
    Auth - Shared       — logout, password change, password reset (all roles)
    Auth - OAuth        — Google / Apple OAuth (male, female, wali)
    Profile - User      — own profile read/update, picture, deactivate (male/female/wali)
    Profile - Admin     — admin's own profile read/update
    Admin - Users       — admin viewing/managing platform users
    Admin - Matchmakers — superadmin CRUD on matchmaker accounts
"""

import logging

from django.contrib.auth import get_user_model
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from notifications.services import NotificationTemplates

from .models import UserRole
from .permissions import IsAdminUser, IsNormalUser, IsSuperAdmin
from .serializers import *
from .services import *

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _token_response(user, request=None) -> dict:
    """Standard login/register success payload."""
    refresh = RefreshToken.for_user(user)
    return {
        "access_token":  str(refresh.access_token),
        "refresh_token": str(refresh),
        "user":          UserProfileSerializer(user, context={"request": request}).data,
    }


def _handle_registration_complete(user, request=None) -> None:
    """Fire post-registration side effects — non-blocking."""
    try:
        from users.tasks import send_welcome_email
        send_welcome_email.delay(user.email, f"{user.first_name} {user.last_name}")
        NotificationTemplates.welcome(user)
        NotificationTemplates.new_user_joined(user)
    except Exception:
        logger.exception("Post-registration hooks failed for %s", user.email)


# Inline response schemas — reused across multiple Swagger docs
_otp_sent_response = inline_serializer(
    name="OTPSentResponse",
    fields={
        "message":            drf_serializers.CharField(),
        "email":              drf_serializers.EmailField(),
        "expires_in_seconds": drf_serializers.IntegerField(),
    },
)

_message_response = inline_serializer(
    name="MessageResponse",
    fields={"message": drf_serializers.CharField()},
)

_token_response_schema = inline_serializer(
    name="TokenResponse",
    fields={
        "message":       drf_serializers.CharField(),
        "access_token":  drf_serializers.CharField(),
        "refresh_token": drf_serializers.CharField(),
        "user":          UserProfileSerializer(),
    },
)

_admin_login_response_schema = inline_serializer(
    name="AdminLoginResponse",
    fields={
        "message":       drf_serializers.CharField(),
        "admin_type":    drf_serializers.CharField(),
        "access_token":  drf_serializers.CharField(),
        "refresh_token": drf_serializers.CharField(),
        "user":          AdminProfileSerializer(),
    },
)


# ═══════════════════════════════════════════════════════════════════════════════
# MALE REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Auth - Male"])
class MaleInitiateRegistrationView(APIView):
    """
    **Step 1** — Validate fields, send OTP to email.
    Sets role=MALE and gender=MALE automatically. Accessible to: Unauthenticated.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Male — Initiate registration (send OTP)",
        description=(
            "Validates email uniqueness and password strength, then sends a 6-digit OTP. "
            "Role is set to **MALE** and gender set to **MALE** automatically by this endpoint. "
            "`confirm_password` is validated at this step."
        ),
        request=MaleInitiateRegistrationSerializer,
        responses={
            200: _otp_sent_response,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = MaleInitiateRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = RegistrationService.initiate_registration(
                role="male",
                email=d["email"],
                password=d["password"],
                first_name=d["first_name"],
                last_name=d["last_name"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Male registration initiation failed.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Auth - Male"])
class MaleVerifyRegistrationView(APIView):
    """
    **Step 2** — Verify OTP → create Male account → return JWT tokens.
    Accessible to: Unauthenticated.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Male — Verify OTP & complete registration",
        description=(
            "Validates the OTP submitted by the user. On success, creates the Male account, "
            "assigns a unique codename (e.g. MMK0042), and returns JWT tokens."
        ),
        request=VerifyRegistrationOTPSerializer,
        responses={
            201: _token_response_schema,
            400: OpenApiResponse(description="Invalid or expired OTP."),
        },
    )
    def post(self, request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = RegistrationService.verify_and_complete_registration(
                role="male", email=d["email"], otp=d["otp"],
            )
            user = result["user"]
            _handle_registration_complete(user, request)
            return Response(
                {
                    "message":       "Registration successful! Welcome to AMM.",
                    "access_token":  result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "user":          UserProfileSerializer(user, context={"request": request}).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Male OTP verification failed.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# FEMALE REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Auth - Female"])
class FemaleInitiateRegistrationView(APIView):
    """
    **Step 1** — Validate fields, send OTP to email.
    Sets role=FEMALE and gender=FEMALE automatically. Accessible to: Unauthenticated.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Female — Initiate registration (send OTP)",
        description=(
            "Validates email uniqueness and password strength, then sends a 6-digit OTP. "
            "Role is set to **FEMALE** and gender set to **FEMALE** automatically by this endpoint. "
            "`confirm_password` is validated at this step."
        ),
        request=FemaleInitiateRegistrationSerializer,
        responses={
            200: _otp_sent_response,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = FemaleInitiateRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = RegistrationService.initiate_registration(
                role="female",
                email=d["email"],
                password=d["password"],
                first_name=d["first_name"],
                last_name=d["last_name"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Female registration initiation failed.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Auth - Female"])
class FemaleVerifyRegistrationView(APIView):
    """
    **Step 2** — Verify OTP → create Female account → return JWT tokens.
    Accessible to: Unauthenticated.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Female — Verify OTP & complete registration",
        description=(
            "Validates the OTP. On success, creates the Female account, "
            "assigns a unique codename, and returns JWT tokens."
        ),
        request=VerifyRegistrationOTPSerializer,
        responses={
            201: _token_response_schema,
            400: OpenApiResponse(description="Invalid or expired OTP."),
        },
    )
    def post(self, request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = RegistrationService.verify_and_complete_registration(
                role="female", email=d["email"], otp=d["otp"],
            )
            user = result["user"]
            _handle_registration_complete(user, request)
            return Response(
                {
                    "message":       "Registration successful! Welcome to AMM.",
                    "access_token":  result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "user":          UserProfileSerializer(user, context={"request": request}).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Female OTP verification failed.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# WALI REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Auth - Wali"])
class WaliInitiateRegistrationView(APIView):
    """
    **Step 1** — Validate fields, send OTP to email.
    Sets role=WALI. Gender is NOT set at registration — Wali sets it during onboarding.
    Accessible to: Unauthenticated.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Wali — Initiate registration (send OTP)",
        description=(
            "Validates email uniqueness and password strength, then sends a 6-digit OTP. "
            "Role is set to **WALI**. Gender is left unset — Wali will select it during "
            "the onboarding/basic-info step. `confirm_password` is validated at this step."
        ),
        request=WaliInitiateRegistrationSerializer,
        responses={
            200: _otp_sent_response,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = WaliInitiateRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = RegistrationService.initiate_registration(
                role="wali",
                email=d["email"],
                password=d["password"],
                first_name=d["first_name"],
                last_name=d["last_name"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Wali registration initiation failed.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Auth - Wali"])
class WaliVerifyRegistrationView(APIView):
    """
    **Step 2** — Verify OTP → create Wali account → return JWT tokens.
    Accessible to: Unauthenticated.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Wali — Verify OTP & complete registration",
        description=(
            "Validates the OTP. On success, creates the Wali account, "
            "assigns a unique codename, and returns JWT tokens."
        ),
        request=VerifyRegistrationOTPSerializer,
        responses={
            201: _token_response_schema,
            400: OpenApiResponse(description="Invalid or expired OTP."),
        },
    )
    def post(self, request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = RegistrationService.verify_and_complete_registration(
                role="wali", email=d["email"], otp=d["otp"],
            )
            user = result["user"]
            _handle_registration_complete(user, request)
            return Response(
                {
                    "message":       "Registration successful! Welcome to AMM.",
                    "access_token":  result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "user":          UserProfileSerializer(user, context={"request": request}).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Wali OTP verification failed.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# RESEND OTP  (shared across all registration flows)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Auth - Shared"])
class ResendRegistrationOTPView(APIView):
    """
    Resend OTP during the registration flow.
    Requires step 1 to have already been called (session must exist in Redis).
    The `role` query param determines which registration session to refresh.
    Accessible to: Unauthenticated.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Resend registration OTP",
        description=(
            "Resends a fresh OTP for an in-progress registration session. "
            "Pass `role` as a query param: `male`, `female`, or `wali`. "
            "The registration session (from step 1) must still be active in Redis."
        ),
        request=ResendOTPSerializer,
        parameters=[
            OpenApiParameter(
                "role", str, required=True,
                description="Role of the registration session: `male`, `female`, or `wali`.",
            )
        ],
        responses={
            200: _otp_sent_response,
            400: OpenApiResponse(description="Session expired or invalid role."),
        },
    )
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = request.query_params.get("role", "").lower()
        if role not in ("male", "female", "wali"):
            return Response(
                {"error": "Invalid role. Must be one of: male, female, wali."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = RegistrationService.resend_otp(
                role=role,
                email=serializer.validated_data["email"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=["Auth - Male"],
    summary="Male — Login",
    description="Authenticate a Male user. Returns JWT access + refresh tokens.",
    request=MaleLoginSerializer,
    responses={
        200: _token_response_schema,
        400: OpenApiResponse(description="Invalid credentials or wrong role."),
    },
)
class MaleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = MaleLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {"message": "Logged in successfully.", **_token_response(user, request)},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Auth - Female"],
    summary="Female — Login",
    description="Authenticate a Female user. Returns JWT access + refresh tokens.",
    request=FemaleLoginSerializer,
    responses={
        200: _token_response_schema,
        400: OpenApiResponse(description="Invalid credentials or wrong role."),
    },
)
class FemaleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FemaleLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {"message": "Logged in successfully.", **_token_response(user, request)},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Auth - Wali"],
    summary="Wali — Login",
    description="Authenticate a Wali user. Returns JWT access + refresh tokens.",
    request=WaliLoginSerializer,
    responses={
        200: _token_response_schema,
        400: OpenApiResponse(description="Invalid credentials or wrong role."),
    },
)
class WaliLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = WaliLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {"message": "Logged in successfully.", **_token_response(user, request)},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Auth - Admin"],
    summary="Admin — Login (Matchmaker & Superadmin)",
    description=(
        "Shared login endpoint for both Matchmaker and Superadmin. "
        "Response includes `admin_type` field (`matchmaker` or `superadmin`) "
        "so the dashboard frontend can distinguish which admin is logged in."
    ),
    request=AdminLoginSerializer,
    responses={
        200: _admin_login_response_schema,
        400: OpenApiResponse(description="Invalid credentials or non-admin role."),
    },
)
class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user       = serializer.validated_data["user"]
        admin_type = serializer.validated_data["admin_type"]
        return Response(
            {
                "message":    f"Welcome back, {user.first_name} {user.last_name}.",
                "admin_type": admin_type,
                **_token_response(user, request),
            },
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# OAUTH  (Male / Female / Wali)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=["Auth - OAuth"],
    summary="Google — OAuth login / register",
    description=(
        "Pass a Google ID token (from Firebase or direct Google Sign-In) and the user's `role` "
        "(`male`, `female`, or `wali`). Creates the account on first call; logs in on subsequent calls. "
        "Admins cannot use OAuth registration."
    ),
    request=GoogleOAuthSerializer,
    responses={
        200: _token_response_schema,
        400: OpenApiResponse(description="Invalid token or email conflict."),
    },
)
class GoogleOAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleOAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Auth - OAuth"],
    summary="Apple — OAuth login / register",
    description=(
        "Pass an Apple ID token, optional `user` dict (Apple sends this only on first login), "
        "and the user's `role` (`male`, `female`, or `wali`). "
        "Admins cannot use OAuth registration."
    ),
    request=AppleOAuthSerializer,
    responses={
        200: _token_response_schema,
        400: OpenApiResponse(description="Invalid token or email conflict."),
    },
)
class AppleOAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AppleOAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED AUTH  (all roles)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=["Auth - Shared"],
    summary="Logout",
    description=(
        "Blacklists the refresh token, invalidating the session. "
        "Pass `refresh` token in the request body. Available to all authenticated roles."
    ),
    request=inline_serializer(
        name="LogoutRequest",
        fields={"refresh": drf_serializers.CharField()},
    ),
    responses={
        205: OpenApiResponse(description="Logged out successfully."),
        400: OpenApiResponse(description="Invalid or missing refresh token."),
    },
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                RefreshToken(refresh_token).blacklist()
            return Response({"message": "Logged out successfully."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Auth - Shared"],
    summary="Change password",
    description=(
        "Change password for the currently authenticated user. "
        "Available to all roles: Male, Female, Wali, Matchmaker, Superadmin."
    ),
    request=ChangePasswordSerializer,
    responses={
        200: _message_response,
        400: OpenApiResponse(description="Incorrect current password or validation error."),
    },
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        try:
            NotificationTemplates.password_changed(user)
        except Exception:
            logger.exception("Password changed notification failed for %s", user.email)
        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Auth - Shared"],
    summary="Forgot password — Step 1: Send OTP",
    description=(
        "Sends a password reset OTP to the email address if it is registered. "
        "Always returns the same response to prevent email enumeration."
    ),
    request=InitiatePasswordResetSerializer,
    responses={200: _otp_sent_response},
)
class InitiatePasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InitiatePasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PasswordResetService.initiate_password_reset(
            email=serializer.validated_data["email"]
        )
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Auth - Shared"],
    summary="Forgot password — Step 2: Verify OTP",
    description=(
        "Validates the OTP and returns a one-time `reset_token`. "
        "Pass this token to the confirm endpoint to set a new password."
    ),
    request=VerifyPasswordResetOTPSerializer,
    responses={
        200: inline_serializer(
            name="VerifyOTPResponse",
            fields={
                "reset_token":        drf_serializers.CharField(),
                "message":            drf_serializers.CharField(),
                "expires_in_seconds": drf_serializers.IntegerField(),
            },
        ),
        400: OpenApiResponse(description="Invalid or expired OTP."),
    },
)
class VerifyPasswordResetOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyPasswordResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = PasswordResetService.verify_reset_otp(
                email=serializer.validated_data["email"],
                otp=serializer.validated_data["otp"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Auth - Shared"],
    summary="Forgot password — Step 3: Set new password",
    description=(
        "Sets a new password using the `reset_token` returned from step 2. "
        "The token is single-use and expires after `PASSWORD_RESET_TOKEN_EXPIRY_SECONDS`."
    ),
    request=ResetPasswordSerializer,
    responses={
        200: _message_response,
        400: OpenApiResponse(description="Invalid/expired reset token or password mismatch."),
    },
)
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = PasswordResetService.reset_password(
                reset_token=serializer.validated_data["reset_token"],
                new_password=serializer.validated_data["new_password"],
            )
            user = result.get("user")
            if user:
                try:
                    NotificationTemplates.password_changed(user)
                except Exception:
                    logger.exception("Password reset notification failed for %s", user.email)
            return Response({"message": result["message"]}, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ═══════════════════════════════════════════════════════════════════════════════
# USER PROFILE  (Male / Female / Wali)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Profile - User"])
class UserProfileView(APIView):
    """
    GET  — Retrieve own full profile (owner only).
    PATCH — Update editable profile fields (first_name, last_name,device_token).
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        summary="Get my profile",
        description=(
            "Returns the full profile of the authenticated user including "
            "codename, subscription plan, and last active display. "
            "Available to Male, Female, and Wali."
        ),
        responses={200: UserProfileSerializer},
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update my profile",
        description=(
            "Update editable profile fields: `first_name`, `last_name`, `device_token`. "
            "To update profile picture use the dedicated `/profile/picture/` endpoint. "
            "Role, email, codename, and subscription are not editable here."
        ),
        request=UpdateProfileSerializer,
        responses={200: UserProfileSerializer},
    )
    def patch(self, request):
        serializer = UpdateProfileSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            UserProfileSerializer(request.user, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Profile - User"])
class UpdateProfilePictureView(APIView):
    """
    PATCH — Update profile picture only.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]
    parser_classes     = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Update profile picture",
        description="Upload a new profile picture. Accepts multipart/form-data.",
        request=UpdateProfilePictureSerializer,
        responses={200: UserProfileSerializer},
    )
    def patch(self, request):
        serializer = UpdateProfilePictureSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            UserProfileSerializer(request.user, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Profile - User"])
class DeactivateAccountView(APIView):
    """
    POST — Self-deactivate account.
    Sets is_active=False and deactivated_by_user=True.
    User can contact support to reactivate.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Deactivate my account",
        description=(
            "Self-deactivate the account. Requires password confirmation. "
            "Sets `is_active=False` and `deactivated_by_user=True`. "
            "The user will be blocked from logging in until reactivated by support. "
            "This is reversible — use the delete endpoint for permanent deletion."
        ),
        request=DeactivateAccountSerializer,
        responses={
            200: _message_response,
            400: OpenApiResponse(description="Incorrect password."),
        },
    )
    def post(self, request):
        serializer = DeactivateAccountSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.is_active           = False
        user.deactivated_by_user = True
        user.save(update_fields=["is_active", "deactivated_by_user"])
        return Response(
            {"message": "Your account has been deactivated. Contact support to reactivate."},
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Profile - Admin"])
class AdminProfileView(APIView):
    """
    GET  — Retrieve own admin profile.
    PATCH — Update first_name, last_name, profile_picture.
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        summary="Admin — Get my profile",
        description="Returns the authenticated admin's own profile with member_since info.",
        responses={200: AdminProfileSerializer},
    )
    def get(self, request):
        serializer = AdminProfileSerializer(request.user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Admin — Update my profile",
        description="Update `first_name`, `last_name`, and/or `profile_picture`. Email and role are not editable.",
        request=AdminProfileSerializer,
        responses={200: AdminProfileSerializer},
    )
    def patch(self, request):
        serializer = AdminProfileSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Admin - Users"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin — List all users",
        description=(
            "Returns a paginated list of all Male, Female, and Wali users. "
            "Filterable by `role`, `gender`, `subscription_plan`, `is_active`. "
            "Searchable by `first_name`, `last_name`, `email`, `codename`."
        ),
        parameters=[
            OpenApiParameter("role",              str,  description="Filter by role: `male`, `female`, `wali`."),
            OpenApiParameter("gender",            str,  description="Filter by gender: `male`, `female`."),
            OpenApiParameter("subscription_plan", str,  description="Filter by plan: `free`, `monthly`, `annual`."),
            OpenApiParameter("is_active",         bool, description="Filter by active status."),
            OpenApiParameter("search",            str,  description="Search by first_name, last_name, email, or codename."),
        ],
        responses={200: AdminUserListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Admin — Get user detail",
        description="Returns full details of a specific user by their UUID.",
        responses={200: AdminUserListSerializer},
    ),
)
class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin read access to all platform users (Male, Female, Wali).
    Block/unblock is a separate action endpoint.
    """
    permission_classes = [IsAdminUser]
    serializer_class   = AdminUserListSerializer
    filter_backends    = [SearchFilter, OrderingFilter]
    search_fields      = ["first_name", "last_name", "email", "codename"]
    ordering_fields    = ["created_at", "last_active", "first_name", "last_name"]
    ordering           = ["-created_at"]
    filterset_fields   = ["role", "gender", "subscription_plan", "is_active"]

    def get_queryset(self):
        return User.objects.filter(
            role__in=[UserRole.MALE, UserRole.FEMALE, UserRole.WALI]
        ).select_related("settings")

    @extend_schema(
        tags=["Admin - Users"],
        summary="Admin — Block or unblock a user",
        description=(
            "Set `is_active=false` to block a user or `is_active=true` to unblock. "
            "When blocking, optionally provide a `reason`. "
            "A notification is sent to the user when blocked. "
            "`deactivated_by_user` is reset to `false` on admin block/unblock."
        ),
        request=AdminBlockUserSerializer,
        responses={
            200: _message_response,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(detail=True, methods=["patch"], url_path="block")
    def block(self, request, pk=None):
        user       = self.get_object()
        serializer = AdminBlockUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_active = serializer.validated_data["is_active"]
        reason    = serializer.validated_data.get("reason", "")

        user.is_active           = is_active
        user.deactivated_by_user = False  # admin action overrides self-deactivation flag
        user.save(update_fields=["is_active", "deactivated_by_user"])

        if not is_active:
            try:
                NotificationTemplates.account_blocked(user, reason)
            except Exception:
                logger.exception("Account blocked notification failed for %s", user.email)
            msg = f"User {user.codename} has been blocked."
        else:
            msg = f"User {user.codename} has been unblocked."

        return Response({"message": msg}, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — MATCHMAKER MANAGEMENT  (Superadmin only)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Admin - Matchmakers"])
@extend_schema_view(
    list=extend_schema(
        summary="Superadmin — List all matchmakers",
        description="Returns all Matchmaker accounts. Superadmin only.",
        responses={200: MatchmakerDetailSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Superadmin — Get matchmaker detail",
        responses={200: MatchmakerDetailSerializer},
    ),
)
class MatchmakerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Superadmin CRUD on Matchmaker accounts.
    Create, role-change, and delete are separate action endpoints.
    """
    permission_classes = [IsSuperAdmin]
    serializer_class   = MatchmakerDetailSerializer

    def get_queryset(self):
        return User.objects.filter(
            role__in=[UserRole.MATCHMAKER, UserRole.SUPERADMIN]
        ).order_by("-created_at")

    @extend_schema(
        tags=["Admin - Matchmakers"],
        summary="Superadmin — Create matchmaker account",
        description=(
            "Create a new Matchmaker account. No OTP flow — superadmin sets the password directly. "
            "Matchmakers can log in via the shared admin login endpoint."
        ),
        request=CreateMatchmakerSerializer,
        responses={
            201: MatchmakerDetailSerializer,
            400: OpenApiResponse(description="Email already registered or validation error."),
        },
    )
    @action(detail=False, methods=["post"], url_path="create-matchmaker")
    def create_matchmaker(self, request):
        serializer = CreateMatchmakerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            user = MatchmakerService.create_matchmaker(
                email=d["email"],
                password=d["password"],
                first_name=d["first_name"],
                last_name=d["last_name"],
            )
            return Response(
                MatchmakerDetailSerializer(user, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["Admin - Matchmakers"],
        summary="Superadmin — Change admin role",
        description=(
            "Promote a Matchmaker to Superadmin, or demote a Superadmin to Matchmaker. "
            "Pass `role`: `matchmaker` or `superadmin`."
        ),
        request=ChangeMatchmakerRoleSerializer,
        responses={
            200: MatchmakerDetailSerializer,
            400: OpenApiResponse(description="Invalid role value."),
        },
    )
    @action(detail=True, methods=["patch"], url_path="change-role")
    def change_role(self, request, pk=None):
        user       = self.get_object()
        serializer = ChangeMatchmakerRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = MatchmakerService.change_role(user, serializer.validated_data["role"])
            return Response(
                MatchmakerDetailSerializer(updated, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["Admin - Matchmakers"],
        summary="Superadmin — Delete matchmaker account",
        description="Permanently deletes a Matchmaker or Superadmin account. Irreversible.",
        responses={
            204: OpenApiResponse(description="Account deleted."),
            403: OpenApiResponse(description="Cannot delete your own account."),
        },
    )
    @action(detail=True, methods=["delete"], url_path="delete")
    def delete_matchmaker(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return Response(
                {"error": "You cannot delete your own account."},
                status=status.HTTP_403_FORBIDDEN,
            )
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)