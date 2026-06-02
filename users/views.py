"""
user/views.py

Swagger tag strategy:
    Auth - Client          — client register / login / OAuth
    Auth - Artisan         — artisan register / login / OAuth
    Auth - Admin           — admin login
    Auth - Shared          — password reset, change password, logout (all roles)
    Profile - Client       — client profile & address management
    Profile - Artisan      — artisan profile & availability management
    Admin - Users          — admin user management endpoints
"""

import logging

from django.contrib.auth import get_user_model, logout
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView, RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from notifications.services import NotificationTemplates
from .models import *
from .permissions import *
from .serializers import *
from .services import *

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build token response
# ─────────────────────────────────────────────────────────────────────────────

def _token_response(user, request=None) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "tokens": {
            "refresh": str(refresh),
            "access":  str(refresh.access_token),
        },
        "user": UserProfileSerializer(user, context={"request": request}).data,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Auth - Client"])
class ClientInitiateRegistrationView(APIView):
    """
    **Step 1** — Send OTP to email.
    Accessible to: Unauthenticated.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        request=InitiateClientRegistrationSerializer,
        summary="Client — Initiate registration (send OTP)",
        description="Validates email uniqueness and sends a 6-digit OTP to the provided email. OTP expires in `OTP_EXPIRY_SECONDS`.",
        responses={200: OpenApiResponse(description="OTP sent successfully.")},
    )
    def post(self, request):
        serializer = InitiateClientRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = RegistrationService.initiate_registration(
                email=d["email"],
                password=d["password"],
                full_name=d["full_name"],
                phone=d.get("phone"),
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected error during client registration initiation.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Auth - Client"])
class ClientVerifyRegistrationView(APIView):
    """
    **Step 2** — Verify OTP → create account → return JWT tokens.
    Accessible to: Unauthenticated.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        request=VerifyRegistrationOTPSerializer,
        summary="Client — Verify OTP & complete registration",
        description="Validates the OTP, creates the client account, and returns JWT access + refresh tokens.",
        responses={201: UserProfileSerializer},
    )
    def post(self, request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = RegistrationService.verify_and_complete_registration(
                email=d["email"],
                otp=d["otp"],
                referral_code=d.get("referral_code"),
            )
            user = result["user"]

            # Post-registration side effects
            try:
                from users.tasks import send_welcome_email
                send_welcome_email.delay(user.email, user.full_name)
                NotificationTemplates.welcome(user)
                NotificationTemplates.new_user_joined(user)
            except Exception:
                logger.exception("Post-registration notifications failed for %s", user.email)

            return Response(
                {
                    "message":       "Registration successful! Welcome to FixGo.",
                    "access_token":  result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "user":          UserProfileSerializer(user, context={"request": request}).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected error during client OTP verification.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# ARTISAN REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Auth - Artisan"])
class ArtisanInitiateRegistrationView(APIView):
    """Step 1 — Artisan sends OTP to email."""
    permission_classes = [AllowAny]

    @extend_schema(
        request=InitiateArtisanRegistrationSerializer,
        summary="Artisan — Initiate registration (send OTP)",
        responses={200: OpenApiResponse(description="OTP sent.")},
    )
    def post(self, request):
        serializer = InitiateArtisanRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = ArtisanRegistrationService.initiate_registration(
                email=d["email"],
                password=d["password"],
                full_name=d["full_name"],
                phone=d.get("phone"),
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Artisan registration initiation failed.")
            return Response({"error": "Something went wrong."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Auth - Artisan"])
class ArtisanVerifyRegistrationView(APIView):
    """Step 2 — Verify OTP → create artisan account → return JWT tokens."""
    permission_classes = [AllowAny]

    @extend_schema(
        request=VerifyArtisanRegistrationOTPSerializer,
        summary="Artisan — Verify OTP & complete registration",
        responses={201: UserProfileSerializer},
    )
    def post(self, request):
        serializer = VerifyArtisanRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = ArtisanRegistrationService.verify_and_complete_registration(
                email=d["email"],
                otp=d["otp"],
            )
            user = result["user"]
            try:
                from users.tasks import send_welcome_email
                send_welcome_email.delay(user.email, user.full_name)
                NotificationTemplates.welcome(user)
                NotificationTemplates.new_artisan_registered(user)
            except Exception:
                logger.exception("Post-registration artisan notifications failed.")

            return Response(
                {
                    "message":       "Artisan account created! Welcome to FixGo.",
                    "access_token":  result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "user":          UserProfileSerializer(user, context={"request": request}).data,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Artisan OTP verification failed.")
            return Response({"error": "Something went wrong."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=["Auth - Client"],
    request=ClientLoginSerializer,
    summary="Client — Login",
    description="Authenticate a client user. Returns JWT access + refresh tokens.",
    responses={200: UserProfileSerializer},
)
class ClientLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ClientLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {"message": "Logged in successfully.", **_token_response(user, request)},
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ARTISAN LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=["Auth - Artisan"],
    request=ArtisanLoginSerializer,
    summary="Artisan — Login",
    description="Authenticate an artisan. Returns JWT access + refresh tokens.",
    responses={200: UserProfileSerializer},
)
class ArtisanLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ArtisanLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {"message": "Logged in successfully.", **_token_response(user, request)},
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=["Auth - Admin"],
    request=AdminLoginSerializer,
    summary="Admin — Dashboard login",
    responses={200: UserProfileSerializer},
)
class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {"message": f"Welcome back, {user.full_name}.", **_token_response(user, request)},
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED AUTH (all roles)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=["Auth - Shared"],
    summary="Logout",
    description="Blacklists the refresh token. Pass `refresh` in the request body.",
    responses={205: OpenApiResponse(description="Logged out.")},
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                RefreshToken(refresh_token).blacklist()
            logout(request)
            return Response({"message": "Logged out successfully."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Auth - Shared"],
    request=ChangePasswordSerializer,
    summary="Change password",
    description="Available to all authenticated users (client, artisan, admin).",
    responses={200: OpenApiResponse(description="Password changed.")},
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        NotificationTemplates.password_changed(user)
        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)


@extend_schema(tags=["Auth - Shared"])
class InitiatePasswordResetView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=InitiatePasswordResetSerializer,
        summary="Forgot password — send OTP",
        responses={200: OpenApiResponse(description="OTP sent (if email exists).")},
    )
    def post(self, request):
        serializer = InitiatePasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PasswordResetService.initiate_password_reset(
            email=serializer.validated_data["email"]
        )
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(tags=["Auth - Shared"])
class VerifyPasswordResetOTPView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=VerifyPasswordResetOTPSerializer,
        summary="Forgot password — verify OTP",
        description="Returns a one-time `reset_token` to use in the next step.",
        responses={200: OpenApiResponse(description="reset_token returned.")},
    )
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


@extend_schema(tags=["Auth - Shared"])
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=ResetPasswordSerializer,
        summary="Forgot password — set new password",
        responses={200: OpenApiResponse(description="Password reset successful.")},
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = PasswordResetService.reset_password(
                reset_token=serializer.validated_data["reset_token"],
                new_password=serializer.validated_data["new_password"],
            )
            user_id = result.get("user_id")
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    NotificationTemplates.password_changed(user)
                except User.DoesNotExist:
                    pass
            return Response({"message": result["message"]}, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ═══════════════════════════════════════════════════════════════════════════════
# OAUTH VIEWS (client + artisan)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=["Auth - Client", "Auth - Artisan"],
    request=GoogleOAuthSerializer,
    summary="Google — OAuth login / register",
    description="Pass the Firebase `id_token` and `role` ('client' or 'artisan'). Creates account on first call.",
    responses={200: OpenApiResponse(description="Tokens returned.")},
)
class GoogleOAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleOAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Auth - Client", "Auth - Artisan"],
    request=AppleOAuthSerializer,
    summary="Apple — OAuth login / register",
    description="Pass the Apple `id_token`, optional `user` dict, and `role`.",
    responses={200: OpenApiResponse(description="Tokens returned.")},
)
class AppleOAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AppleOAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)



@extend_schema(tags=["Profile - Admin"])
class AdminProfileView(RetrieveUpdateAPIView):
    """
    GET  — retrieve own profile.
    PATCH — update full_name, phone, profile_picture.
    Available to: **Admin**.
    """
    permission_classes = [IsAdmin]
    serializer_class   = AdminProfileSerializer
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user

    @extend_schema(summary="Admin — Get my profile")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Admin — Update my profile")
    def patch(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)