"""
users/serializers.py

Organized by concern:
    1. Registration (Male + Female + Wali) with OTP verification
    2. Authentication (login, logout, password change/reset)
    3. OAuth (Google, Apple)
    4. Profile (read + update)
"""

import logging

import jwt
import requests as req
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
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


# ═══════════════════════════════════════════════════════════════════
# Internal helper
# ═══════════════════════════════════════════════════════════════════

def _build_user_data(user: User) -> dict:
    return {
        "id":              str(user.id),
        "full_name":       user.full_name,
        "email":           user.email,
        "role":            user.role,
        "profile_picture": user.profile_picture.url if user.profile_picture else None,
    }
    

# ═══════════════════════════════════════════════════════════════════
# 1. Registration
# ═══════════════════════════════════════════════════════════════════

class InitiateClientRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=True)
    email     = serializers.EmailField(required=True)
    phone     = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password  = serializers.CharField(
        min_length=8, write_only=True, required=True,
        style={"input_type": "password"},
    )
    referral_code = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value


class VerifyRegistrationOTPSerializer(serializers.Serializer):
    email         = serializers.EmailField(required=True)
    otp           = serializers.CharField(min_length=6, max_length=6, required=True)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value


class InitiateArtisanRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=True)
    email     = serializers.EmailField(required=True)
    phone     = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password  = serializers.CharField(
        min_length=8, write_only=True, required=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value


class VerifyArtisanRegistrationOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp   = serializers.CharField(min_length=6, max_length=6, required=True)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value


# ═══════════════════════════════════════════════════════════════════
# 2. Authentication
# ═══════════════════════════════════════════════════════════════════

class ClientLoginSerializer(serializers.Serializer):
    email    = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})

    def validate(self, data):
        email    = data.get("email", "").lower().strip()
        password = data.get("password", "")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        if not user.check_password(password):
            raise serializers.ValidationError({"detail": "Invalid email or password."})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "Your account has been deactivated."})
        if not user.is_client:
            raise serializers.ValidationError({"detail": "Please use the artisan login."})

        data["user"] = user
        return data


class ArtisanLoginSerializer(serializers.Serializer):
    email    = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})

    def validate(self, data):
        email    = data.get("email", "").lower().strip()
        password = data.get("password", "")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "Invalid email or password."})

        if not user.check_password(password):
            raise serializers.ValidationError({"detail": "Invalid email or password."})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "Your account has been deactivated."})
        if not user.is_artisan:
            raise serializers.ValidationError({"detail": "Please use the client login."})

        data["user"] = user
        return data


class AdminLoginSerializer(serializers.Serializer):
    email    = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})

    def validate(self, data):
        from django.contrib.auth import authenticate
        user = authenticate(
            request=self.context.get("request"),
            email=data["email"].lower().strip(),
            password=data["password"],
        )
        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials."})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "Account deactivated."})
        if not user.is_admin:
            raise serializers.ValidationError({"detail": "Admin access required."})
        data["user"] = user
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password         = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    new_password         = serializers.CharField(write_only=True, min_length=8, required=True, style={"input_type": "password"})
    confirm_new_password = serializers.CharField(write_only=True, min_length=8, required=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, data):
        if data["new_password"] != data["confirm_new_password"]:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})
        if data["new_password"] == data["old_password"]:
            raise serializers.ValidationError({"new_password": "New password must differ from the current one."})
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
            raise serializers.ValidationError("OTP must contain only digits.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    reset_token          = serializers.CharField(required=True)
    new_password         = serializers.CharField(write_only=True, min_length=8, required=True, style={"input_type": "password"})
    confirm_new_password = serializers.CharField(write_only=True, min_length=8, required=True, style={"input_type": "password"})

    def validate(self, data):
        if data["new_password"] != data["confirm_new_password"]:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})
        try:
            validate_password(data["new_password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return data


# ═══════════════════════════════════════════════════════════════════
# 3. OAuth
# ═══════════════════════════════════════════════════════════════════

class GoogleOAuthSerializer(serializers.Serializer):
    """Accepts Firebase/Google ID token from the mobile app."""
    id_token  = serializers.CharField(required=True)
    role      = serializers.ChoiceField(choices=["client", "artisan"], default="client")

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

        is_staff     = role == "artisan"
        is_superuser = False

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name":    google_user.get("name", ""),
                "is_active":    True,
                "is_staff":     is_staff,
                "is_superuser": is_superuser,
                "provider":     AuthProvider.GOOGLE,
                "provider_id":  google_user.get("sub"),
            },
        )

        if created:
            user.set_unusable_password()
            picture = google_user.get("picture", "")
            if picture:
                try:
                    resp = req.get(picture, timeout=5)
                    resp.raise_for_status()
                    user.profile_picture.save(
                        f"{user.id}_google.jpg",
                        ContentFile(resp.content),
                        save=False,
                    )
                except Exception:
                    pass
            user.save()

            self._send_post_registration_notifications(user)

        if not created:
            if user.provider == AuthProvider.SELF:
                raise serializers.ValidationError(
                    "An account with this email already exists. Please log in with email and password."
                )
            if user.provider != AuthProvider.GOOGLE:
                raise serializers.ValidationError(
                    f"An account with this email exists via {user.provider}. Please use that login method."
                )

        refresh = RefreshToken.for_user(user)
        return {
            "user":   _build_user_data(user),
            "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
        }

    @staticmethod
    def _send_post_registration_notifications(user):
        try:
            from users.tasks import send_welcome_email
            send_welcome_email.delay(user.email, user.full_name)
            from notifications.services import NotificationTemplates
            NotificationTemplates.welcome(user)
            if user.is_client:
                NotificationTemplates.new_user_joined(user)
            else:
                NotificationTemplates.new_artisan_registered(user)
        except Exception as exc:
            logger.error("Post-registration notifications failed: %s", exc)


class AppleOAuthSerializer(serializers.Serializer):
    id_token  = serializers.CharField(required=True)
    user      = serializers.JSONField(required=False)
    role      = serializers.ChoiceField(choices=["client", "artisan"], default="client")

    def validate(self, attrs):
        id_token_value = attrs["id_token"]
        user_data      = attrs.get("user", {})
        role           = attrs["role"]

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

        email       = payload.get("email")
        provider_id = payload.get("sub")
        full_name   = user_data.get("name") if user_data else (email or "").split("@")[0]

        if not email:
            raise serializers.ValidationError("Apple account has no associated email.")

        is_staff = role == "artisan"

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name":    full_name,
                "is_active":    True,
                "is_staff":     is_staff,
                "is_superuser": False,
                "provider":     AuthProvider.APPLE,
                "provider_id":  provider_id,
            },
        )

        if created:
            user.set_unusable_password()
            user.save()
            try:
                from users.tasks import send_welcome_email
                send_welcome_email.delay(user.email, user.full_name)
                from notifications.services import NotificationTemplates
                NotificationTemplates.welcome(user)
                if user.is_client:
                    NotificationTemplates.new_user_joined(user)
                else:
                    NotificationTemplates.new_artisan_registered(user)
            except Exception as exc:
                logger.error("Apple OAuth post-registration failed: %s", exc)

        if not created:
            if user.provider == AuthProvider.SELF:
                raise serializers.ValidationError(
                    "An account with this email exists. Please log in with email and password."
                )
            if user.provider != AuthProvider.APPLE:
                raise serializers.ValidationError(
                    f"Please log in with {user.provider}."
                )

        refresh = RefreshToken.for_user(user)
        return {
            "user":   _build_user_data(user),
            "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
        }


# ═══════════════════════════════════════════════════════════════════
# 4. Profile serializers
# ═══════════════════════════════════════════════════════════════════

class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal public-safe representation used in nested contexts."""
    class Meta:
        model  = User
        fields = ["id", "full_name", "email", "profile_picture", "role"]


class UserProfileSerializer(serializers.ModelSerializer):
    """Full profile — role determines which nested profile is included."""
    role            = serializers.CharField(read_only=True)

    class Meta:
        model  = User
        fields = [
            "id", "full_name", "email", "phone", "profile_picture",
            "birth_date", "role", "provider",
            "created_at",
        ]
        read_only_fields = ["id", "role", "provider", "created_at"]




class AdminProfileSerializer(serializers.ModelSerializer):

    profile_picture = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "profile_picture",
            "phone",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "email",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        request = self.context.get("request")

        if instance.profile_picture and request:
            representation["profile_picture"] = request.build_absolute_uri(
                instance.profile_picture.url
            )

        return representation