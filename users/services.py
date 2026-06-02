"""
user/services.py

Service layer — keeps views thin and business logic testable.

Classes:
    OTPService              — generate / store / verify OTPs via Redis
    RegistrationService     — client & artisan OTP-based registration
    PasswordResetService    — OTP + token password reset flow
    ReferralService         — apply referral codes on signup
"""

import logging
import random
import secrets
import string
from datetime import date

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
# Registration Service  (client)
# ─────────────────────────────────────────────────────────────────────────────

class RegistrationService:
    """Handles OTP-gated client registration flow."""

    @staticmethod
    def initiate_registration(email: str, password: str, full_name: str, phone: str = None) -> dict:
        from django.contrib.auth.hashers import make_password
        from users.models import User

        if User.objects.filter(email=email).exists():
            raise ValueError("This email is already registered.")

        otp = OTPService.generate_otp()
        cache_key = f"registration_otp:{email}"
        payload = {
            "email":     email,
            "full_name": full_name,
            "phone":     phone,
            "password":  make_password(password),
            "otp":       otp,
        }
        cache.set(cache_key, payload, settings.OTP_EXPIRY_SECONDS)

        try:
            from users.tasks import send_registration_otp_email
            send_registration_otp_email.delay(email, otp, full_name)
        except Exception as exc:
            logger.error("Failed to queue registration OTP email: %s", exc)

        return {
            "message":           "OTP sent to your email. Please verify to complete registration.",
            "email":             email,
            "expires_in_seconds": settings.OTP_EXPIRY_SECONDS,
        }

    @staticmethod
    def verify_and_complete_registration(email: str, otp: str, referral_code: str = None) -> dict:
        from users.models import AuthProvider, User

        cache_key = f"registration_otp:{email}"
        payload = cache.get(cache_key)
        if not payload:
            raise ValueError("OTP expired. Please restart registration.")
        if payload["otp"] != otp:
            raise ValueError("Invalid OTP.")

        user = User.objects.create(
            email=email,
            full_name=payload["full_name"],
            phone=payload.get("phone") or "",
            password=payload["password"],
            is_active=True,
            is_staff=False,
            is_superuser=False,
            provider=AuthProvider.SELF,
        )
        cache.delete(cache_key)

        # Handle referral
        if referral_code:
            ReferralService.apply_referral(referral_code=referral_code, new_user=user)

        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return {
            "user":          user,
            "refresh_token": str(refresh),
            "access_token":  str(refresh.access_token),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Artisan Registration Service
# ─────────────────────────────────────────────────────────────────────────────

class ArtisanRegistrationService:
    """Handles OTP-gated artisan registration flow."""

    @staticmethod
    def initiate_registration(email: str, password: str, full_name: str, phone: str = None) -> dict:
        from django.contrib.auth.hashers import make_password
        from users.models import User

        if User.objects.filter(email=email).exists():
            raise ValueError("This email is already registered.")

        otp = OTPService.generate_otp()
        cache_key = f"artisan_registration_otp:{email}"
        payload = {
            "email":     email,
            "full_name": full_name,
            "phone":     phone,
            "password":  make_password(password),
            "otp":       otp,
        }
        cache.set(cache_key, payload, settings.OTP_EXPIRY_SECONDS)

        try:
            from users.tasks import send_registration_otp_email
            send_registration_otp_email.delay(email, otp, full_name)
        except Exception as exc:
            logger.error("Failed to queue artisan OTP email: %s", exc)

        return {
            "message":           "OTP sent. Please verify to complete artisan registration.",
            "email":             email,
            "expires_in_seconds": settings.OTP_EXPIRY_SECONDS,
        }

    @staticmethod
    def verify_and_complete_registration(email: str, otp: str) -> dict:
        from users.models import AuthProvider, User

        cache_key = f"artisan_registration_otp:{email}"
        payload = cache.get(cache_key)
        if not payload:
            raise ValueError("OTP expired. Please restart registration.")
        if payload["otp"] != otp:
            raise ValueError("Invalid OTP.")

        user = User.objects.create(
            email=email,
            full_name=payload["full_name"],
            phone=payload.get("phone") or "",
            password=payload["password"],
            is_active=True,
            is_staff=True,        # artisan
            is_superuser=False,
            provider=AuthProvider.SELF,
        )
        cache.delete(cache_key)

        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return {
            "user":          user,
            "refresh_token": str(refresh),
            "access_token":  str(refresh.access_token),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Service
# ─────────────────────────────────────────────────────────────────────────────

class PasswordResetService:
    @staticmethod
    def initiate_password_reset(email: str) -> dict:
        from users.models import User

        # Never reveal if email exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return {
                "message":           "If this email is registered, an OTP has been sent.",
                "expires_in_seconds": settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
            }

        otp = OTPService.generate_otp()
        cache.set(f"password_reset_otp:{email}", otp, settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS)

        try:
            from users.tasks import send_password_reset_otp_email
            send_password_reset_otp_email.delay(email, otp, user.full_name or email)
        except Exception as exc:
            logger.error("Failed to queue password reset OTP email: %s", exc)

        return {
            "message":           "If this email is registered, an OTP has been sent.",
            "expires_in_seconds": settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
        }

    @staticmethod
    def verify_reset_otp(email: str, otp: str) -> dict:
        key = f"password_reset_otp:{email}"
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

        return {
            "message": "Password reset successful. Please log in with your new password.",
            "user_id": str(user.id),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Referral Service
# ─────────────────────────────────────────────────────────────────────────────

class ReferralService:
    @staticmethod
    def generate_code(user) -> str:
        """Generate and persist a unique referral code for a user."""
        import hashlib
        code = hashlib.sha256(str(user.id).encode()).hexdigest()[:8].upper()
        # Persist in cache; when a proper referral_code field is added to User, store there
        cache.set(f"referral_code:{code}", str(user.id), timeout=None)
        return code

    @staticmethod
    def apply_referral(referral_code: str, new_user) -> bool:
        from users.models import Referral, User

        referrer_id = cache.get(f"referral_code:{referral_code.upper()}")
        if not referrer_id:
            return False
        try:
            referrer = User.objects.get(id=referrer_id)
        except User.DoesNotExist:
            return False

        if referrer == new_user:
            return False   # Can't refer yourself

        Referral.objects.get_or_create(referrer=referrer, referred=new_user)

        bonus = getattr(settings, "REFERRAL_BONUS_AMOUNT", 5.00)
        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.referral_bonus(referrer, bonus)
        except Exception as exc:
            logger.error("Failed to send referral bonus notification: %s", exc)

        return True