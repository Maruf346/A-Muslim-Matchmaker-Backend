"""
users/serializers.py

Organized by concern:
    1. Registration  — Male, Female, Wali (2-step OTP flow each)
    2. Authentication — login per role, logout, password change/reset
    3. OAuth          — Google, Apple (shared across Male/Female/Wali)
    4. Profile        — read, update, profile picture
    5. Admin          — admin profile, matchmaker management
"""

import logging

import jwt
import requests as req
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jwt.algorithms import RSAAlgorithm
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import *

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_token_data(user) -> dict:
    """Build the standard token + user payload returned on login/register."""
    refresh = RefreshToken.for_user(user)
    return {
        "access_token":  str(refresh.access_token),
        "refresh_token": str(refresh),
        "user": {
            "id":               str(user.id),
            "codename":         user.codename,
            "first_name":        user.first_name,
            "last_name":         user.last_name,
            "email":            user.email,
            "role":             user.role,
            "subscription_plan": user.subscription_plan,
            "is_verified":      user.is_verified,
            "profile_picture":  user.profile_picture.url if user.profile_picture else None,
            "is_private_matchmaking_client":  user.is_private_matchmaking_client,
        },
    }


def _validate_email_unique(value: str) -> str:
    value = value.lower().strip()
    if User.objects.filter(email=value).exists():
        raise serializers.ValidationError("This email is already registered.")
    return value


def _validate_password_strength(value: str) -> str:
    try:
        validate_password(value)
    except DjangoValidationError as e:
        raise serializers.ValidationError(list(e.messages))
    return value


# ═══════════════════════════════════════════════════════════════════════════════
# 1. REGISTRATION SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════════════

# ── Step 1: Initiate (send OTP) ───────────────────────────────────────────────

class _BaseInitiateRegistrationSerializer(serializers.Serializer):
    """
    Shared fields for all initiate-registration serializers.
    confirm_password is validated here (step 1) so the user gets
    feedback before waiting for an OTP.
    """
    first_name = serializers.CharField(max_length=75)
    last_name  = serializers.CharField(max_length=75)
    email            = serializers.EmailField()
    password         = serializers.CharField(
        min_length=8, write_only=True, style={"input_type": "password"}
    )
    confirm_password = serializers.CharField(
        min_length=8, write_only=True, style={"input_type": "password"}
    )

    def validate_email(self, value):
        return _validate_email_unique(value)

    def validate_password(self, value):
        return _validate_password_strength(value)

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return data


class MaleInitiateRegistrationSerializer(_BaseInitiateRegistrationSerializer):
    """Step 1 payload for Male registration."""
    pass


class FemaleInitiateRegistrationSerializer(_BaseInitiateRegistrationSerializer):
    """Step 1 payload for Female registration."""
    pass


class WaliInitiateRegistrationSerializer(_BaseInitiateRegistrationSerializer):
    """Step 1 payload for Wali registration."""
    pass


# ── Step 2: Verify OTP ────────────────────────────────────────────────────────

class VerifyRegistrationOTPSerializer(serializers.Serializer):
    """
    Shared OTP verification serializer for all registration flows.
    The role is determined by which view calls the service, not this serializer.
    """
    email = serializers.EmailField()
    otp   = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain digits only.")
        return value


# ── Resend OTP ────────────────────────────────────────────────────────────────

class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. AUTHENTICATION SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════════════

class _BaseLoginSerializer(serializers.Serializer):
    """
    Shared login validation logic.
    Subclasses set `allowed_roles` to restrict which role can use the endpoint.
    """
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    # Override in subclasses
    allowed_roles: list = []
    blocked_message: str = "This account is not accessible from this login."

    def validate(self, data):
        email    = data.get("email", "").lower().strip()
        password = data.get("password", "")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        if not user.check_password(password):
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        # Role check
        if self.allowed_roles and user.role not in self.allowed_roles:
            raise serializers.ValidationError({"detail": self.blocked_message})

        # Account state checks
        if not user.is_active:
            if user.deactivated_by_user:
                raise serializers.ValidationError({
                    "detail": (
                        "Your account has been deactivated. "
                        "Please contact support to reactivate it."
                    )
                })
            raise serializers.ValidationError({
                "detail": (
                    "Your account has been blocked. "
                    "Please contact support for assistance."
                )
            })

        data["user"] = user
        return data


class MaleLoginSerializer(_BaseLoginSerializer):
    allowed_roles   = [UserRole.MALE]
    blocked_message = "Please use the Female or Wali login."


class FemaleLoginSerializer(_BaseLoginSerializer):
    allowed_roles   = [UserRole.FEMALE]
    blocked_message = "Please use the Male or Wali login."


class WaliLoginSerializer(_BaseLoginSerializer):
    allowed_roles   = [UserRole.WALI]
    blocked_message = "Please use the Male or Female login."


class UserLoginSerializer(_BaseLoginSerializer):
    """Unified login serializer for all user roles (Male, Female, Wali)."""
    allowed_roles   = [UserRole.MALE, UserRole.FEMALE, UserRole.WALI]
    blocked_message = "Account not found or not accessible."


class AdminLoginInitiateSerializer(serializers.Serializer):
    """Step 1: email + password to kick off admin OTP login."""
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value):
        return value.lower().strip()


class AdminLoginVerifyOTPSerializer(serializers.Serializer):
    """Step 2: 6-digit OTP to complete admin login and receive JWT tokens."""
    email = serializers.EmailField()
    otp   = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain digits only.")
        return value


class AdminResendLoginOTPSerializer(serializers.Serializer):
    """Resend admin login OTP (subject to 60-second cooldown)."""
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


# ── Password management ───────────────────────────────────────────────────────

class ChangePasswordSerializer(serializers.Serializer):
    old_password         = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password         = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})
    confirm_new_password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, data):
        if data["new_password"] != data["confirm_new_password"]:
            raise serializers.ValidationError(
                {"confirm_new_password": "Passwords do not match."}
            )
        if data["new_password"] == data["old_password"]:
            raise serializers.ValidationError(
                {"new_password": "New password must differ from the current one."}
            )
        try:
            validate_password(data["new_password"], self.context["request"].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return data


class InitiatePasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return value.lower().strip()


class VerifyPasswordResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp   = serializers.CharField(min_length=6, max_length=6, required=True)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain digits only.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    reset_token          = serializers.CharField(required=True)
    new_password         = serializers.CharField(write_only=True, min_length=8, required=True, style={"input_type": "password"})
    confirm_new_password = serializers.CharField(write_only=True, min_length=8, required=True, style={"input_type": "password"})

    def validate(self, data):
        if data["new_password"] != data["confirm_new_password"]:
            raise serializers.ValidationError(
                {"confirm_new_password": "Passwords do not match."}
            )
        try:
            validate_password(data["new_password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return data


# ═══════════════════════════════════════════════════════════════════════════════
# 3. OAUTH SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════════════

class _BaseOAuthSerializer(serializers.Serializer):
    """
    Shared OAuth logic.
    `role` must be one of: male, female, wali.
    Admins cannot register via OAuth.
    """
    id_token = serializers.CharField()
    role     = serializers.ChoiceField(
        choices=[UserRole.MALE, UserRole.FEMALE, UserRole.WALI],
        default=UserRole.MALE,
    )

    def _get_or_create_user(self, email: str, first_name: str, last_name: str, provider: str, provider_id: str, role: str):
        """
        Get existing user or create a new one via OAuth.
        Raises ValidationError if email is registered via a different provider.
        """
        # Determine gender from role
        gender_map = {
            UserRole.MALE:   Gender.MALE,
            UserRole.FEMALE: Gender.FEMALE,
            UserRole.WALI:   None,  # Wali sets gender during onboarding
        }

        existing = User.objects.filter(email=email).first()
        if existing:
            if existing.provider == AuthProvider.SELF:
                raise serializers.ValidationError(
                    "An account with this email exists. Please log in with email and password."
                )
            if existing.provider != provider:
                raise serializers.ValidationError(
                    f"An account with this email exists via {existing.provider}. Please use that login."
                )
            return existing, False

        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            gender=gender_map.get(role),
            is_active=True,
            provider=provider,
            provider_id=provider_id,
        )
        user.set_unusable_password()
        user.codename = self._assign_codename(user)
        user.save(update_fields=["codename"])
        UserSettings.objects.create(user=user)
        from dashboard.services import RecentActivityService
        RecentActivityService.user_registered(user)
        return user, True

    @staticmethod
    def _assign_codename(user) -> str:
        from .models import generate_codename
        return generate_codename(role=user.role)

    def _post_registration_hooks(self, user):
        try:
            from users.tasks import send_welcome_email
            send_welcome_email.delay(user.email, user.first_name, user.last_name)
            from notifications.services import NotificationTemplates
            NotificationTemplates.welcome(user)
            NotificationTemplates.new_user_joined(user)
        except Exception as exc:
            logger.error("OAuth post-registration hooks failed for %s: %s", user.email, exc)


class GoogleOAuthSerializer(_BaseOAuthSerializer):
    """
    Accepts a Google ID token from the mobile app (Firebase or direct Google Sign-In).
    Creates the account on first call; logs in on subsequent calls.
    """

    def validate(self, attrs):
        token = attrs["id_token"]
        role  = attrs["role"]

        try:
            google_user = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_WEB_CLIENT_ID,
            )
        except Exception:
            raise serializers.ValidationError("Invalid or expired Google token.")

        email = google_user.get("email")
        if not email:
            raise serializers.ValidationError("Google account has no associated email.")

        user, created = self._get_or_create_user(
            email=email,
            first_name=google_user.get("given_name", ""),
            last_name=google_user.get("family_name", ""),
            provider=AuthProvider.GOOGLE,
            provider_id=google_user.get("sub", ""),
            role=role,
        )

        if created:
            # Attempt to download Google profile picture
            picture_url = google_user.get("picture", "")
            if picture_url:
                try:
                    resp = req.get(picture_url, timeout=5)
                    resp.raise_for_status()
                    user.profile_picture.save(
                        f"{user.id}_google.jpg",
                        ContentFile(resp.content),
                        save=True,
                    )
                except Exception:
                    pass
            self._post_registration_hooks(user)

        return {"message": "Login successful.", **_build_token_data(user)}


class AppleOAuthSerializer(_BaseOAuthSerializer):
    """
    Accepts an Apple ID token from the mobile app.
    `user` dict is optional — Apple only sends it on the very first login.
    """
    user = serializers.JSONField(required=False)

    def validate(self, attrs):
        id_token_value = attrs["id_token"]
        user_data      = attrs.get("user", {})
        role           = attrs["role"]

        try:
            apple_keys = req.get("https://appleid.apple.com/auth/keys", timeout=10).json()
            header     = jwt.get_unverified_header(id_token_value)
            key        = next(k for k in apple_keys["keys"] if k["kid"] == header["kid"])
            public_key = RSAAlgorithm.from_jwk(key)

            payload = jwt.decode(
                id_token_value,
                public_key,
                algorithms=["RS256"],
                audience=settings.APPLE_CLIENT_ID,
            )
        except StopIteration:
            raise serializers.ValidationError("Apple public key not found.")
        except Exception:
            raise serializers.ValidationError("Invalid or expired Apple token.")

        email       = payload.get("email")
        provider_id = payload.get("sub")
        first_name = (
            user_data.get("name", {}).get("firstName", "")
            if isinstance(user_data.get("name"), dict)
            else (email or "").split("@")[0]
        )
        last_name = (
            user_data.get("name", {}).get("lastName", "")
            if isinstance(user_data.get("name"), dict)
            else ""
        )

        if not email:
            raise serializers.ValidationError("Apple account has no associated email.")

        user, created = self._get_or_create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            provider=AuthProvider.APPLE,
            provider_id=provider_id,
            role=role,
        )

        if created:
            self._post_registration_hooks(user)

        return {"message": "Login successful.", **_build_token_data(user)}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PROFILE SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════════════

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Full profile for the authenticated user (Male, Female, or Wali).

    Hidden fields (first_name, last_name, profile_picture) are visible to the owner.
    When viewed by others, the matches app serializer controls visibility
    based on mutual interest — this serializer is owner-only.
    """
    last_active_display = serializers.SerializerMethodField()
    profile_completion_percentage = serializers.SerializerMethodField()
    is_profile_locked = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            "id",
            "codename",
            "first_name",
            "last_name",
            "email",
            "role",
            "gender",
            "profile_picture",
            "subscription_plan",
            "subscription_start",
            "subscription_end",
            "provider",
            "is_active",
            "is_verified",
            "is_profile_locked",
            "is_private_matchmaking_client",
            "last_active",
            "last_active_display",
            "profile_completion_percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "codename", "email", "role", "gender",
            "subscription_plan", "subscription_start", "subscription_end",
            "provider", "is_active", "is_verified", "is_profile_locked", "is_private_matchmaking_client", "last_active", "last_active_display",
            "profile_completion_percentage",
            "created_at", "updated_at",
        ]

    def get_is_profile_locked(self, obj) -> bool:
        from matches.services import MatchService
        return MatchService.is_user_locked(obj)

    def _get_basic_info(self, obj):
        try:
            if obj.role == UserRole.MALE:
                return obj.male_basic_info
            if obj.role == UserRole.FEMALE:
                return obj.female_basic_info
            if obj.role == UserRole.WALI:
                return obj.wali_basic_info
        except ObjectDoesNotExist:
            return None
        return None

    def get_profile_completion_percentage(self, obj):
        info = self._get_basic_info(obj)
        return getattr(info, "completion_percentage", None) if info else None

    def get_last_active_display(self, obj) -> str | None:
        """Returns human-readable last active string."""
        from core.utils import format_last_active_display
        return format_last_active_display(obj)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get("request")
        if instance.profile_picture and request:
            rep["profile_picture"] = request.build_absolute_uri(instance.profile_picture.url)
        return rep


class UpdateProfileSerializer(serializers.ModelSerializer):
    """
    Writable fields a user can update on their own profile.
    Role, email, codename, and subscription are not user-editable here.
    """
    class Meta:
        model  = User
        fields = ["first_name", "last_name", "device_token"]


class UpdateProfilePictureSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ["profile_picture"]


class PublicUserProfileSerializer(serializers.ModelSerializer):
    """
    Profile representation shown to OTHER users browsing the directory.
    Sensitive fields (first_name, last_name, profile_picture, email) are conditionally
    hidden — resolved by the view based on mutual interest status.

    The view should call `set_visibility(has_mutual_interest=True/False)`
    before returning, or pass `mutual_interest` in serializer context.
    """
    display_name        = serializers.SerializerMethodField()
    display_picture     = serializers.SerializerMethodField()
    last_active_display = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            "id",
            "codename",
            "display_name",
            "display_picture",
            "role",
            "gender",
            "subscription_plan",
            "is_verified",
            "last_active",
            "last_active_display",
        ]

    def _has_mutual_interest(self) -> bool:
        return self.context.get("mutual_interest", False)

    def get_display_name(self, obj) -> str:
        """Returns first_name and last_name only after mutual interest; codename otherwise."""
        if self._has_mutual_interest():
            return f"{obj.first_name} {obj.last_name}"
        return obj.codename

    def get_display_picture(self, obj) -> str | None:
        """
        Returns the profile picture URL after mutual interest.
        Before mutual interest, returns None — frontend handles blur effect.
        """
        if not self._has_mutual_interest():
            return None
        if obj.profile_picture:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None

    def get_last_active_display(self, obj) -> str | None:
        from core.utils import format_last_active_display
        return format_last_active_display(obj)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ADMIN SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════════════

class AdminProfileSerializer(serializers.ModelSerializer):
    """Admin's own profile — read/update."""
    member_since = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model  = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "role",
            "profile_picture",
            "member_since",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "email", "role", "member_since", "created_at", "updated_at"]

    def to_representation(self, instance):
        rep     = super().to_representation(instance)
        request = self.context.get("request")
        if instance.profile_picture and request:
            rep["profile_picture"] = request.build_absolute_uri(instance.profile_picture.url)
        return rep


class CreateMatchmakerSerializer(serializers.Serializer):
    """Used by Superadmin to create a new Matchmaker account."""
    first_name = serializers.CharField(max_length=75)
    last_name  = serializers.CharField(max_length=75)
    email     = serializers.EmailField()
    password  = serializers.CharField(min_length=8, write_only=True, style={"input_type": "password"})
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    def validate_email(self, value):
        return _validate_email_unique(value)

    def validate_password(self, value):
        return _validate_password_strength(value)


class UpdateMatchmakerSerializer(serializers.ModelSerializer):
    """Used by Superadmin to update basic info of a Matchmaker."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "profile_picture"]


class MatchmakerDetailSerializer(serializers.ModelSerializer):
    """Read representation of a Matchmaker account."""
    class Meta:
        model  = User
        fields = [
            "id", "first_name", "last_name", "email", "role",
            "profile_picture", "is_active", "created_at",
        ]
        read_only_fields = fields


class ChangeMatchmakerRoleSerializer(serializers.Serializer):
    """Superadmin can promote/demote between matchmaker and superadmin."""
    role = serializers.ChoiceField(choices=[UserRole.MATCHMAKER, UserRole.SUPERADMIN])


class AdminUserListSerializer(serializers.ModelSerializer):
    """
    Compact user representation for admin user list view.
    Used in admin dashboard to list/search/filter all users.
    """
    last_active_display = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    date_of_birth = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    sect = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    profile_completion_percentage = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            "id",
            "codename",
            "first_name",
            "last_name",
            "email",
            "role",
            "gender",
            "profile_picture",
            "photos",
            "subscription_plan",
            "is_verified",
            "date_of_birth",
            "age",
            "sect",
            "city",
            "country",
            "profile_completion_percentage",
            "is_active",
            "deactivated_by_user",
            "is_private_matchmaking_client",
            "last_active",
            "last_active_display",
            "created_at",
        ]
        read_only_fields = fields

    def get_last_active_display(self, obj) -> str | None:
        if not obj.last_active:
            return None
        from django.utils import timezone
        delta   = timezone.now() - obj.last_active
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "Active now"
        if seconds < 3600:
            return f"Active {seconds // 60} min(s) ago"
        if seconds < 86400:
            return f"Active {seconds // 3600} hr(s) ago"
        return f"Active {seconds // 86400} day(s) ago"

    def _is_retrieve(self) -> bool:
        """Returns True if the current request is for a detail (retrieve) view."""
        view = self.context.get("view")
        return getattr(view, "action", None) == "retrieve"

    def get_first_name(self, obj) -> str | None:
        from users.models import UserRole
        if obj.role == UserRole.WALI and not self._is_retrieve():
            wali_info = getattr(obj, "wali_basic_info", None)
            if wali_info is None:
                from questions.models import WaliBasicInfo
                wali_info = WaliBasicInfo.objects.filter(user=obj).first()
            return getattr(wali_info, "sister_first_name", None) or obj.first_name
        return obj.first_name

    def get_last_name(self, obj) -> str | None:
        from users.models import UserRole
        if obj.role == UserRole.WALI and not self._is_retrieve():
            wali_info = getattr(obj, "wali_basic_info", None)
            if wali_info is None:
                from questions.models import WaliBasicInfo
                wali_info = WaliBasicInfo.objects.filter(user=obj).first()
            return getattr(wali_info, "sister_last_name", None) or obj.last_name
        return obj.last_name

    def get_gender(self, obj) -> str | None:
        from users.models import UserRole
        if obj.role == UserRole.WALI and not self._is_retrieve():
            return "female"
        return obj.gender

    def _get_basic_info(self, obj):
        """
        Return the role-appropriate basic info object for the admin list.
        Wali uses the sister-facing basic info record because that is where the
        profile completion / DOB / location fields live.
        """
        try:
            if obj.role == UserRole.MALE:
                return obj.male_basic_info
            if obj.role == UserRole.FEMALE:
                return obj.female_basic_info
            if obj.role == UserRole.WALI:
                return obj.wali_basic_info
        except ObjectDoesNotExist:
            return None
        return None

    def get_date_of_birth(self, obj):
        info = self._get_basic_info(obj)
        return getattr(info, "date_of_birth", None) if info else None

    def get_age(self, obj):
        info = self._get_basic_info(obj)
        return getattr(info, "age", None) if info else None

    def get_sect(self, obj):
        info = self._get_basic_info(obj)
        return getattr(info, "sect", None) if info else None

    def get_city(self, obj):
        info = self._get_basic_info(obj)
        return getattr(info, "city", None) if info else None

    def get_country(self, obj):
        info = self._get_basic_info(obj)
        return getattr(info, "country", None) if info else None

    def get_profile_completion_percentage(self, obj):
        info = self._get_basic_info(obj)
        return getattr(info, "completion_percentage", None) if info else None

    def _build_file_url(self, file_field) -> str | None:
        if not file_field:
            return None
        try:
            url = file_field.url
        except Exception:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_profile_picture(self, obj) -> str | None:
        direct_url = self._build_file_url(getattr(obj, "profile_picture", None))
        if direct_url:
            return direct_url
        from questions.models import UserPhoto
        primary_photo = UserPhoto.objects.filter(user=obj).order_by("order", "created_at").first()
        return self._build_file_url(getattr(primary_photo, "image", None)) if primary_photo else None

    def get_photos(self, obj) -> list:
        from questions.models import UserPhoto
        from questions.serializers import UserPhotoSerializer
        photos = UserPhoto.objects.filter(user=obj).order_by("order", "created_at")
        return UserPhotoSerializer(photos, many=True, context=self.context).data


class AdminBlockUserSerializer(serializers.Serializer):
    """Payload for admin blocking/unblocking a user."""
    is_active = serializers.BooleanField()
    reason    = serializers.CharField(required=False, allow_blank=True)


class AdminToggleVerificationSerializer(serializers.Serializer):
    """Payload for admin verifying/unverifying a user."""
    is_verified = serializers.BooleanField()


class DeactivateAccountSerializer(serializers.Serializer):
    """User self-deactivation."""
    password = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_password(self, value):
        if not value:
            return value
        user = self.context["request"].user
        if user.has_usable_password() and not user.check_password(value):
            raise serializers.ValidationError("Incorrect password.")
        return value


class WhyLeavingUserSerializer(serializers.ModelSerializer):
    """
    User-facing serializer for submitting why they are leaving.
    Used only for POST requests.
    """

    class Meta:
        model = WhyLeaving
        fields = ["reasons", "tell_us_more"]
        extra_kwargs = {
            "reasons": {
                "required": False,
                "allow_blank": True,
                "allow_null": True,
            },
            "tell_us_more": {
                "required": False,
                "allow_blank": True,
                "allow_null": True,
            },
        }


class WhyLeavingAdminSerializer(serializers.ModelSerializer):
    """Full CRUD serializer for admin management of why-leaving records."""

    class Meta:
        model = WhyLeaving
        fields = ["id", "reasons", "tell_us_more"]
        read_only_fields = ["id"]
