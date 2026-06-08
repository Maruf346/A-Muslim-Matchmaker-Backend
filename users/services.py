"""
users/services.py

Service layer — keeps views thin and business logic testable.

Classes:
    OTPService              — generate / store / verify OTPs via Redis
    RegistrationService     — OTP-gated registration for Male, Female, Wali
    PasswordResetService    — OTP + token password reset flow
"""

import logging
import random
import secrets
import string

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# OTP Service
# ─────────────────────────────────────────────────────────────────────────────

class OTPService:
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        return "".join(random.choices(string.digits, k=length))

    @staticmethod
    def store_otp(cache_key: str, otp: str, expiry_seconds: int) -> None:
        cache.set(cache_key, otp, expiry_seconds)

    @staticmethod
    def verify_otp(cache_key: str, provided_otp: str) -> tuple[bool, str]:
        stored = cache.get(cache_key)
        if not stored:
            return False, "OTP expired or not found."
        if stored != provided_otp:
            return False, "Invalid OTP."
        cache.delete(cache_key)
        return True, "OTP verified."


# ─────────────────────────────────────────────────────────────────────────────
# Registration Service
# ─────────────────────────────────────────────────────────────────────────────

class RegistrationService:
    """
    Handles OTP-gated 2-step registration for Male, Female, and Wali users.

    Flow:
        Step 1 — initiate_registration(role, ...) → stores payload in Redis, sends OTP email
        Step 2 — verify_and_complete_registration(role, email, otp) → creates User, returns tokens

    The `role` parameter drives:
        - Which Redis cache key namespace is used
        - Which gender is assigned (male→MALE, female→FEMALE, wali→None)
        - Whether is_staff/is_superuser flags are set (all False for normal users)
    """

    # Cache key prefix per role — prevents cross-role OTP confusion
    _CACHE_PREFIX = {
        "male":   "registration_otp:male:",
        "female": "registration_otp:female:",
        "wali":   "registration_otp:wali:",
    }

    # Gender assigned at registration per role
    _GENDER_MAP = {
        "male":   "male",
        "female": "female",
        "wali":   None,  # Wali sets gender during onboarding (questions app)
    }

    @classmethod
    def initiate_registration(
        cls,
        role: str,
        email: str,
        password: str,        # already validated (confirm_pass checked in serializer)
        first_name : str,
        last_name  : str,
    ) -> dict:
        """
        Step 1: Validate uniqueness, store OTP payload in Redis, send OTP email.

        Args:
            role: "male", "female", or "wali"
            email: normalized email
            password: raw password (will be hashed before storing)
            first_name: user's first name
            last_name: user's last name

        Returns:
            dict with message and expiry info.
        """
        from django.contrib.auth.hashers import make_password
        from users.models import User

        if User.objects.filter(email=email).exists():
            raise ValueError("This email is already registered.")

        if role not in cls._CACHE_PREFIX:
            raise ValueError(f"Invalid role: {role}. Must be male, female, or wali.")

        otp       = OTPService.generate_otp()
        cache_key = cls._CACHE_PREFIX[role] + email

        payload = {
            "email":     email,
            "first_name": first_name,
            "last_name":  last_name,
            "phone":     None,  # optional, can be set during onboarding
            "password":  make_password(password),
            "role":      role,
            "otp":       otp,
        }
        cache.set(cache_key, payload, settings.OTP_EXPIRY_SECONDS)

        try:
            from users.tasks import send_registration_otp_email
            send_registration_otp_email.delay(email, otp, f"{first_name} {last_name}")
        except Exception as exc:
            logger.error("Failed to queue registration OTP email for %s: %s", email, exc)

        return {
            "message":            "OTP sent to your email. Please verify to complete registration.",
            "email":              email,
            "expires_in_seconds": settings.OTP_EXPIRY_SECONDS,
        }

    @classmethod
    def verify_and_complete_registration(cls, role: str, email: str, otp: str) -> dict:
        """
        Step 2: Verify OTP, create User, assign codename, return tokens.

        Args:
            role:  "male", "female", or "wali"
            email: normalized email
            otp:   6-digit OTP submitted by user

        Returns:
            dict with user object and JWT tokens.

        Raises:
            ValueError on OTP mismatch/expiry.
        """
        from users.models import AuthProvider, Gender, User, UserRole, UserSettings, generate_codename

        if role not in cls._CACHE_PREFIX:
            raise ValueError(f"Invalid role: {role}.")

        cache_key = cls._CACHE_PREFIX[role] + email
        payload   = cache.get(cache_key)

        if not payload:
            raise ValueError("OTP expired or not found. Please restart registration.")
        if payload["otp"] != otp:
            raise ValueError("Invalid OTP.")

        # Map role string to UserRole choice
        role_map = {
            "male":   UserRole.MALE,
            "female": UserRole.FEMALE,
            "wali":   UserRole.WALI,
        }

        gender = cls._GENDER_MAP.get(role)

        user = User.objects.create(
            email=email,
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            password=payload["password"],   # already hashed
            role=role_map[role],
            gender=gender,
            is_active=True,
            is_staff=False,
            is_superuser=False,
            provider=AuthProvider.SELF,
        )

        # Assign unique codename
        codename = generate_codename()
        while User.objects.filter(codename=codename).exclude(pk=user.pk).exists():
            codename = f"MMK{User.objects.count():04d}"
        user.codename = codename
        user.save(update_fields=["codename"])

        # Create default settings
        UserSettings.objects.create(user=user)

        # Clear OTP cache
        cache.delete(cache_key)

        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return {
            "user":          user,
            "access_token":  str(refresh.access_token),
            "refresh_token": str(refresh),
        }

    @classmethod
    def resend_otp(cls, role: str, email: str) -> dict:
        """
        Resend OTP for an existing pending registration.
        Requires that step 1 was already called (payload must be in cache).
        """
        if role not in cls._CACHE_PREFIX:
            raise ValueError(f"Invalid role: {role}.")

        cache_key = cls._CACHE_PREFIX[role] + email
        payload   = cache.get(cache_key)

        if not payload:
            raise ValueError("Registration session expired. Please restart registration.")

        new_otp = OTPService.generate_otp()
        payload["otp"] = new_otp
        cache.set(cache_key, payload, settings.OTP_EXPIRY_SECONDS)

        try:
            from users.tasks import send_registration_otp_email
            send_registration_otp_email.delay(email, new_otp, f"{payload.get('first_name', '')} {payload.get('last_name', '')}")
        except Exception as exc:
            logger.error("Failed to resend OTP for %s: %s", email, exc)

        return {
            "message":            "A new OTP has been sent to your email.",
            "email":              email,
            "expires_in_seconds": settings.OTP_EXPIRY_SECONDS,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Service
# ─────────────────────────────────────────────────────────────────────────────

class PasswordResetService:
    """
    3-step flow:
        1. initiate_password_reset(email) → sends OTP
        2. verify_reset_otp(email, otp)   → returns one-time reset_token
        3. reset_password(reset_token, new_password) → updates password

    Timing constants (from settings):
        OTP:         PASSWORD_RESET_OTP_EXPIRY_SECONDS   (default 600 = 10 min)
        reset_token: PASSWORD_RESET_TOKEN_EXPIRY_SECONDS  (default 900 = 15 min)
    """

    @staticmethod
    def initiate_password_reset(email: str) -> dict:
        from users.models import User

        # Never reveal whether the email is registered
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return {
                "message":            "If this email is registered, an OTP has been sent.",
                "expires_in_seconds": settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
            }

        otp = OTPService.generate_otp()
        cache.set(
            f"password_reset_otp:{email}",
            otp,
            settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
        )

        try:
            from users.tasks import send_password_reset_otp_email
            send_password_reset_otp_email.delay(email, otp, f"{user.first_name} {user.last_name}")
        except Exception as exc:
            logger.error("Failed to queue password reset OTP for %s: %s", email, exc)

        return {
            "message":            "If this email is registered, an OTP has been sent.",
            "expires_in_seconds": settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
        }

    @staticmethod
    def verify_reset_otp(email: str, otp: str) -> dict:
        key    = f"password_reset_otp:{email}"
        stored = cache.get(key)

        if not stored:
            raise ValueError("OTP expired or not found.")
        if stored != otp:
            raise ValueError("Invalid OTP.")

        reset_token = secrets.token_urlsafe(32)
        cache.set(
            f"password_reset_token:{reset_token}",
            email,
            settings.PASSWORD_RESET_TOKEN_EXPIRY_SECONDS,
        )
        cache.delete(key)

        return {
            "reset_token":        reset_token,
            "message":            "OTP verified. You can now set a new password.",
            "expires_in_seconds": settings.PASSWORD_RESET_TOKEN_EXPIRY_SECONDS,
        }

    @staticmethod
    def reset_password(reset_token: str, new_password: str) -> dict:
        from users.models import User

        email = cache.get(f"password_reset_token:{reset_token}")
        if not email:
            raise ValueError("Invalid or expired reset token.")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValueError("User not found.")

        user.set_password(new_password)
        user.save(update_fields=["password"])
        cache.delete(f"password_reset_token:{reset_token}")

        return {"message": "Password reset successful. Please log in.", "user": user}


# ─────────────────────────────────────────────────────────────────────────────
# Matchmaker Management Service  (superadmin only)
# ─────────────────────────────────────────────────────────────────────────────

class MatchmakerService:
    """
    Superadmin-only operations on Matchmaker accounts.
    Matchmakers cannot self-register — only superadmin can create them.
    """

    @staticmethod
    def create_matchmaker(email: str, password: str, first_name: str, last_name: str):
        """Create a new Matchmaker account. No OTP — admin sets password directly."""
        from users.models import AuthProvider, User, UserRole, UserSettings

        if User.objects.filter(email=email).exists():
            raise ValueError("This email is already registered.")

        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.MATCHMAKER,
            is_active=True,
            is_staff=True,
            is_superuser=False,
            provider=AuthProvider.SELF,
        )
        user.set_password(password)
        user.save(update_fields=["password"])
        UserSettings.objects.create(user=user)
        return user

    @staticmethod
    def change_role(user, new_role: str):
        """Promote matchmaker to superadmin or demote superadmin to matchmaker."""
        from users.models import UserRole

        if new_role not in (UserRole.MATCHMAKER, UserRole.SUPERADMIN):
            raise ValueError("Role must be 'matchmaker' or 'superadmin'.")

        user.role        = new_role
        user.is_staff    = True
        user.is_superuser = (new_role == UserRole.SUPERADMIN)
        user.save(update_fields=["role", "is_staff", "is_superuser"])
        return user