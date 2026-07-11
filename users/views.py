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
from django.db.models import Q
from django_filters import rest_framework as filters
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
from django_filters.rest_framework import DjangoFilterBackend

from notifications.services import NotificationTemplates

from .models import *
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
        send_welcome_email.delay(user.email, user.first_name, user.last_name)
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

_admin_otp_sent_response = inline_serializer(
    name="AdminOTPSentResponse",
    fields={
        "message":            drf_serializers.CharField(),
        "email":              drf_serializers.EmailField(),
        "expires_in_seconds": drf_serializers.IntegerField(),
    },
)


class AdminUserFilterSet(filters.FilterSet):
    role = filters.ChoiceFilter(field_name="role", choices=UserRole.choices)
    gender = filters.CharFilter(method="filter_gender")
    subscription_plan = filters.ChoiceFilter(
        field_name="subscription_plan",
        choices=SubscriptionPlan.choices,
    )
    is_active = filters.BooleanFilter(field_name="is_active")
    is_verified = filters.BooleanFilter(field_name="is_verified")
    date_of_birth = filters.DateFilter(method="filter_date_of_birth")
    age = filters.NumberFilter(method="filter_age")
    sect = filters.CharFilter(method="filter_basic_info_choice")
    city = filters.CharFilter(method="filter_basic_info_text")
    country = filters.CharFilter(method="filter_basic_info_text")
    marital_status = filters.CharFilter(method="filter_basic_info_choice")
    ethnicity = filters.CharFilter(method="filter_basic_info_json")
    nationality = filters.CharFilter(method="filter_basic_info_json")
    has_children = filters.BooleanFilter(method="filter_basic_info_boolean")
    children_count = filters.CharFilter(method="filter_basic_info_choice")
    height = filters.CharFilter(method="filter_basic_info_choice")
    weight = filters.CharFilter(method="filter_basic_info_choice")
    pray_5x = filters.CharFilter(method="filter_basic_info_choice")
    open_to_relocate = filters.CharFilter(method="filter_basic_info_choice")
    how_found = filters.CharFilter(method="filter_how_found")
    employment = filters.CharFilter(method="filter_basic_info_text")
    education = filters.CharFilter(method="filter_basic_info_choice")
    income = filters.CharFilter(method="filter_basic_info_choice")
    frame = filters.CharFilter(method="filter_basic_info_choice")
    languages_spoken = filters.CharFilter(method="filter_basic_info_json")
    pref_age_min = filters.NumberFilter(method="filter_basic_info_number")
    pref_age_max = filters.NumberFilter(method="filter_basic_info_number")
    pref_marital_status = filters.CharFilter(method="filter_basic_info_json")
    pref_ethnicity = filters.CharFilter(method="filter_basic_info_json")
    pref_country_of_residence = filters.CharFilter(method="filter_basic_info_json")
    relationship_with_islam = filters.CharFilter(method="filter_basic_info_text")
    role_as_spouse = filters.CharFilter(method="filter_basic_info_text")
    about_yourself = filters.CharFilter(method="filter_basic_info_text")
    envision_spouse = filters.CharFilter(method="filter_basic_info_text")
    envision_marriage = filters.CharFilter(method="filter_basic_info_text")
    spouse_religious_status_pref = filters.CharFilter(method="filter_basic_info_text")
    open_to_relocate_details = filters.CharFilter(method="filter_basic_info_text")
    health_concerns = filters.CharFilter(method="filter_basic_info_text")
    other_preferences = filters.CharFilter(method="filter_basic_info_text")
    wali_profile_how_found = filters.CharFilter(method="filter_wali_profile_json")
    wali_profile_gender = filters.CharFilter(method="filter_wali_profile_choice")
    wali_profile_relation_to_sister = filters.CharFilter(method="filter_wali_profile_choice")
    wali_profile_phone = filters.CharFilter(method="filter_wali_profile_text")

    class Meta:
        model = User
        fields = [
            "role",
            "gender",
            "subscription_plan",
            "is_active",
            "is_verified",
            "date_of_birth",
            "age",
            "sect",
            "city",
            "country",
            "marital_status",
            "ethnicity",
            "nationality",
            "has_children",
            "children_count",
            "height",
            "weight",
            "pray_5x",
            "open_to_relocate",
            "how_found",
            "employment",
            "education",
            "income",
            "frame",
            "languages_spoken",
            "pref_age_min",
            "pref_age_max",
            "pref_marital_status",
            "pref_ethnicity",
            "pref_country_of_residence",
            "relationship_with_islam",
            "role_as_spouse",
            "about_yourself",
            "envision_spouse",
            "envision_marriage",
            "spouse_religious_status_pref",
            "open_to_relocate_details",
            "health_concerns",
            "other_preferences",
            "wali_profile_how_found",
            "wali_profile_gender",
            "wali_profile_relation_to_sister",
            "wali_profile_phone",
        ]

    @staticmethod
    def _basic_info_relations():
        return ("male_basic_info", "female_basic_info", "wali_basic_info")

    @staticmethod
    def _wali_profile_relation():
        return ("wali_profile",)

    @staticmethod
    def _or_filter(queryset, relations, field, value, lookup="icontains"):
        query = Q()
        for relation in relations:
            query |= Q(**{f"{relation}__{field}__{lookup}": value})
        return queryset.filter(query)

    def filter_gender(self, queryset, name, value):
        value = (value or "").strip().lower()
        if value == "female":
            return queryset.filter(Q(gender="female") | Q(role=UserRole.WALI))
        if value == "male":
            return queryset.filter(gender="male")
        return queryset.filter(gender=value)

    def filter_date_of_birth(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), "date_of_birth", value, lookup="exact")

    def filter_age(self, queryset, name, value):
        from datetime import timedelta
        from django.utils import timezone

        try:
            age = int(value)
        except (TypeError, ValueError):
            return queryset

        today = timezone.now().date()

        def _shift_years(base_date, years):
            try:
                return base_date.replace(year=base_date.year - years)
            except ValueError:
                # Handles Feb 29 -> Feb 28 in non-leap years.
                return base_date.replace(month=2, day=28, year=base_date.year - years)

        start = _shift_years(today, age + 1) + timedelta(days=1)
        end = _shift_years(today, age)
        query = Q()
        for relation in self._basic_info_relations():
            query |= Q(**{f"{relation}__date_of_birth__range": (start, end)})
        return queryset.filter(query)

    def filter_basic_info_text(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), name, value, lookup="icontains")

    def filter_basic_info_choice(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), name, value, lookup="iexact")

    def filter_basic_info_number(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), name, value, lookup="exact")

    def filter_basic_info_boolean(self, queryset, name, value):
        query = Q()
        for relation in self._basic_info_relations():
            query |= Q(**{f"{relation}__{name}": value})
        return queryset.filter(query)

    def filter_basic_info_json(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), name, value, lookup="icontains")

    def filter_how_found(self, queryset, name, value):
        relations = self._basic_info_relations() + self._wali_profile_relation()
        return self._or_filter(queryset, relations, "how_found", value, lookup="icontains")

    def filter_wali_profile_text(self, queryset, name, value):
        return self._or_filter(queryset, self._wali_profile_relation(), name.replace("wali_profile_", ""), value, lookup="icontains")

    def filter_wali_profile_choice(self, queryset, name, value):
        field = name.replace("wali_profile_", "")
        return self._or_filter(queryset, self._wali_profile_relation(), field, value, lookup="iexact")

    def filter_wali_profile_json(self, queryset, name, value):
        field = name.replace("wali_profile_", "")
        return self._or_filter(queryset, self._wali_profile_relation(), field, value, lookup="icontains")


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
    summary="Admin — Login Step 1: Submit credentials (Matchmaker & Superadmin)",
    description=(
        "Step 1 of the admin login flow. Validates email and password. "
        "On success, sends a 6-digit OTP to the admin's email address. "
        "Submit the OTP to `/admin/login/verify/` to receive JWT tokens."
    ),
    request=AdminLoginInitiateSerializer,
    responses={
        200: _admin_otp_sent_response,
        400: OpenApiResponse(description="Invalid credentials or non-admin role."),
    },
)
class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = AdminLoginOTPService.initiate_login(
                email=d["email"],
                password=d["password"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Admin login initiation failed.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Auth - Admin"],
    summary="Admin — Login Step 2: Verify OTP (Matchmaker & Superadmin)",
    description=(
        "Step 2 of the admin login flow. Submit the 6-digit OTP sent to the admin's email. "
        "On success, returns JWT access + refresh tokens. "
        "Response includes `admin_type` field (`matchmaker` or `superadmin`) "
        "so the dashboard frontend can distinguish which admin is logged in."
    ),
    request=AdminLoginVerifyOTPSerializer,
    responses={
        200: _admin_login_response_schema,
        400: OpenApiResponse(description="Invalid or expired OTP."),
    },
)
class AdminLoginVerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = AdminLoginOTPService.verify_otp_and_login(
                email=d["email"],
                otp=d["otp"],
            )
            user       = result["user"]
            admin_type = result["admin_type"]
            return Response(
                {
                    "message":       f"Welcome back, {user.first_name} {user.last_name}.",
                    "admin_type":    admin_type,
                    "access_token":  result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "user":          AdminProfileSerializer(user, context={"request": request}).data,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Admin OTP verification failed.")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Auth - Admin"],
    summary="Admin — Resend login OTP",
    description=(
        "Resend the admin login OTP. Can only be called after Step 1. "
        "Enforces a 60-second cooldown between resend requests."
    ),
    request=AdminResendLoginOTPSerializer,
    responses={
        200: _admin_otp_sent_response,
        400: OpenApiResponse(description="Session not found, cooldown active, or invalid email."),
    },
)
class AdminLoginResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminResendLoginOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = AdminLoginOTPService.resend_otp(
                email=serializer.validated_data["email"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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

    @extend_schema(
        summary="Delete my profile",
        description=(
            "Permanently deletes the authenticated user's own profile and account. "
            "This action is irreversible."
        ),
        responses={204: OpenApiResponse(description="Profile deleted.")},
    )
    def delete(self, request):
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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


@extend_schema(tags=["Profile - User"])
class WhyLeavingView(APIView):
    """
    POST — Capture why a user is leaving the platform.
    Available to: Male, Female, Wali.
    """
    permission_classes = [IsNormalUser]

    @extend_schema(
        summary="Submit why I am leaving",
        description=(
            "Stores a comma-separated list of reasons and an optional free-form "
            "comment. This endpoint is intended for users before they delete or "
            "deactivate their account."
        ),
        request=WhyLeavingUserSerializer,
        responses={
            201: WhyLeavingAdminSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = WhyLeavingUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leaving = serializer.save()
        return Response(
            WhyLeavingAdminSerializer(leaving, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
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
            OpenApiParameter(
                "gender",
                str,
                description="Filter by gender: `male`, `female` (female also includes wali profiles).",
            ),
            OpenApiParameter("subscription_plan", str,  description="Filter by plan: `free`, `monthly`, `annual`."),
            OpenApiParameter("is_active",         bool, description="Filter by active status."),
            OpenApiParameter("is_verified",       bool, description="Filter by verification status."),
            OpenApiParameter("date_of_birth",     str,  description="Filter by exact date of birth (`YYYY-MM-DD`)."),
            OpenApiParameter("age",               int,  description="Filter by age in years."),
            OpenApiParameter("how_found",         str,  description="Filter by how the user found AMM."),
            OpenApiParameter("sect",              str,  description="Filter by sect."),
            OpenApiParameter("city",              str,  description="Filter by city."),
            OpenApiParameter("country",           str,  description="Filter by country."),
            OpenApiParameter("marital_status",    str,  description="Filter by marital status."),
            OpenApiParameter("ethnicity",         str,  description="Filter by ethnicity."),
            OpenApiParameter("nationality",       str,  description="Filter by nationality."),
            OpenApiParameter("has_children",      bool, description="Filter by whether the user has children."),
            OpenApiParameter("children_count",    str,  description="Filter by number of children."),
            OpenApiParameter("height",            str,  description="Filter by height choice."),
            OpenApiParameter("weight",            str,  description="Filter by weight choice."),
            OpenApiParameter("pray_5x",           str,  description="Filter by prayer consistency."),
            OpenApiParameter("open_to_relocate",   str,  description="Filter by relocation choice."),
            OpenApiParameter("employment",        str,  description="Filter by employment."),
            OpenApiParameter("education",         str,  description="Filter by education choice."),
            OpenApiParameter("income",            str,  description="Filter by income choice."),
            OpenApiParameter("frame",             str,  description="Filter by body frame choice."),
            OpenApiParameter("languages_spoken",  str,  description="Filter by spoken language."),
            OpenApiParameter("pref_age_min",      int,  description="Filter by preferred minimum age."),
            OpenApiParameter("pref_age_max",      int,  description="Filter by preferred maximum age."),
            OpenApiParameter("pref_marital_status", str, description="Filter by preferred marital status."),
            OpenApiParameter("pref_ethnicity",      str, description="Filter by preferred ethnicity."),
            OpenApiParameter("pref_country_of_residence", str, description="Filter by preferred country of residence."),
            OpenApiParameter("relationship_with_islam", str, description="Filter by relationship with Islam."),
            OpenApiParameter("role_as_spouse",     str,  description="Filter by role as spouse."),
            OpenApiParameter("about_yourself",     str,  description="Filter by about yourself."),
            OpenApiParameter("envision_spouse",    str,  description="Filter by envision spouse."),
            OpenApiParameter("envision_marriage",  str,  description="Filter by envision marriage."),
            OpenApiParameter("spouse_religious_status_pref", str, description="Filter by spouse religious status preference."),
            OpenApiParameter("open_to_relocate_details", str, description="Filter by relocation details."),
            OpenApiParameter("health_concerns",    str,  description="Filter by health concerns."),
            OpenApiParameter("other_preferences",   str,  description="Filter by other preferences."),
            OpenApiParameter("wali_profile_how_found", str, description="Filter Wali profile by how found."),
            OpenApiParameter("wali_profile_gender", str, description="Filter Wali profile gender."),
            OpenApiParameter("wali_profile_relation_to_sister", str, description="Filter Wali relation to sister."),
            OpenApiParameter("wali_profile_phone", str, description="Filter Wali profile phone."),
            OpenApiParameter("search",            str,  description="Search by first_name, last_name, or codename."),
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
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields      = ["first_name", "last_name", "email", "codename"]
    ordering_fields    = ["created_at", "last_active", "first_name", "last_name"]
    ordering           = ["-created_at"]
    filterset_class    = AdminUserFilterSet

    def get_queryset(self):
        return User.objects.filter(
            role__in=[UserRole.MALE, UserRole.FEMALE, UserRole.WALI]
        ).select_related(
            "settings",
            "male_basic_info",
            "female_basic_info",
            "wali_profile",
            "wali_basic_info",
        )

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

    @extend_schema(
        tags=["Admin - Users"],
        summary="Admin - Verify or unverify a user",
        description=(
            "Set `is_verified=true` to mark a user as verified, or `is_verified=false` "
            "to remove verification. Intended for admin dashboard management."
        ),
        request=AdminToggleVerificationSerializer,
        responses={
            200: _message_response,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    @action(detail=True, methods=["patch"], url_path="verification")
    def verification(self, request, pk=None):
        user = self.get_object()
        serializer = AdminToggleVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user.is_verified = serializer.validated_data["is_verified"]
        user.save(update_fields=["is_verified"])

        msg = (
            f"User {user.codename} has been marked as verified."
            if user.is_verified
            else f"Verification removed for user {user.codename}."
        )
        return Response({"message": msg}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Admin - Users"],
        summary="Admin - Update a user's profile fields",
        description=(
            "Update editable User model fields for any user: "
            "`first_name`, `last_name`, `profile_picture`. "
            "This does NOT update BasicInfo fields — use the questions app endpoint for that."
        ),
        request=UpdateProfileSerializer,
        responses={200: AdminUserListSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="update-profile",
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def update_profile(self, request, pk=None):
        user = self.get_object()
        from users.serializers import UpdateProfileSerializer
        serializer = UpdateProfileSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            AdminUserListSerializer(user, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Admin - Users"],
        summary="Admin - Delete a user",
        description=(
            "Permanently deletes any user account. "
            "Use the profile endpoint to delete your own account."
        ),
        responses={
            204: OpenApiResponse(description="User deleted."),
            403: OpenApiResponse(description="Cannot delete your own account here."),
        },
    )
    @action(detail=True, methods=["delete"], url_path="delete")
    def delete_user(self, request, pk=None):
        user = self.get_object()
        if user.id == request.user.id:
            return Response(
                {"error": "Use the profile endpoint to delete your own account."},
                status=status.HTTP_403_FORBIDDEN,
            )
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Admin - Why Leaving"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin — List why-leaving records",
        responses={200: WhyLeavingAdminSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Admin — Get why-leaving detail",
        responses={200: WhyLeavingAdminSerializer},
    ),
    create=extend_schema(
        summary="Admin — Create why-leaving record",
        request=WhyLeavingAdminSerializer,
        responses={201: WhyLeavingAdminSerializer},
    ),
    update=extend_schema(
        summary="Admin — Update why-leaving record",
        request=WhyLeavingAdminSerializer,
        responses={200: WhyLeavingAdminSerializer},
    ),
    partial_update=extend_schema(
        summary="Admin — Partially update why-leaving record",
        request=WhyLeavingAdminSerializer,
        responses={200: WhyLeavingAdminSerializer},
    ),
    destroy=extend_schema(
        summary="Admin — Delete why-leaving record",
        responses={204: OpenApiResponse(description="Record deleted.")},
    ),
)
class WhyLeavingViewSet(viewsets.ModelViewSet):
    """
    Admin full CRUD for why-leaving records.
    """
    permission_classes = [IsAdminUser]
    serializer_class = WhyLeavingAdminSerializer
    queryset = WhyLeaving.objects.all().order_by("-id")


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
    parser_classes     = [MultiPartParser, FormParser, JSONParser]
    filterset_fields   = ["role", "is_active"]
    search_fields      = ["first_name", "last_name", "email"]

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
                profile_picture=d.get("profile_picture"),
            )
            return Response(
                MatchmakerDetailSerializer(user, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["Admin - Matchmakers"],
        summary="Superadmin — Update matchmaker basic info",
        description="Update a matchmaker's first name, last name, and profile picture.",
        request=UpdateMatchmakerSerializer,
        responses={200: MatchmakerDetailSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="update-info")
    def update_info(self, request, pk=None):
        user = self.get_object()
        serializer = UpdateMatchmakerSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_user = MatchmakerService.update_matchmaker(
            user, **serializer.validated_data
        )

        return Response(
            MatchmakerDetailSerializer(updated_user, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

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
        summary="Superadmin — Block or unblock a matchmaker",
        description=(
            "Set `is_active=false` to block a matchmaker or `is_active=true` to unblock. "
            "A superadmin cannot block their own account."
        ),
        request=AdminBlockUserSerializer,
        responses={
            200: _message_response,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Cannot block your own account."),
        },
    )
    @action(detail=True, methods=["patch"], url_path="set-active")
    def set_active(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return Response(
                {"error": "You cannot block or unblock your own account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AdminBlockUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user.is_active = serializer.validated_data["is_active"]
        user.deactivated_by_user = False
        user.save(update_fields=["is_active", "deactivated_by_user"])

        action_verb = "unblocked" if user.is_active else "blocked"
        return Response({"message": f"Matchmaker {user.email} has been {action_verb}."}, status=status.HTTP_200_OK)

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
