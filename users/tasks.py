"""
users/tasks.py

Celery email tasks for AMM (A Muslim Matchmaker).
All tasks use exponential back-off retry (max 3 attempts, 60/120/240s delays).
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

PLATFORM_NAME = "A Muslim Matchmaker"
SUPPORT_EMAIL = getattr(settings, "SUPPORT_EMAIL", "support@amuslimmatrimony.com")


@shared_task(bind=True, max_retries=3, name="users.send_registration_otp_email")
def send_registration_otp_email(self, email: str, otp: str, first_name: str, last_name: str):
    """Send a 6-digit email verification OTP during registration step 1."""
    expiry_minutes = getattr(settings, "OTP_EXPIRY_SECONDS", 300) // 60
    subject = f"{PLATFORM_NAME} — Verify your email"
    message = (
        f"As-salamu alaykum {first_name} {last_name or 'there'},\n\n"
        f"Thank you for joining {PLATFORM_NAME}!\n\n"
        f"Your email verification code is:\n\n"
        f"    {otp}\n\n"
        f"This code expires in {expiry_minutes} minutes.\n\n"
        f"If you did not create an account with us, please ignore this email.\n\n"
        f"— The {PLATFORM_NAME} Team"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info("Registration OTP sent to %s", email)
    except Exception as exc:
        logger.error("Failed to send registration OTP to %s: %s", email, exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3, name="users.send_password_reset_otp_email")
def send_password_reset_otp_email(self, email: str, otp: str, first_name: str, last_name: str):
    """Send a 6-digit OTP for password reset step 1."""
    expiry_minutes = getattr(settings, "PASSWORD_RESET_OTP_EXPIRY_SECONDS", 600) // 60
    subject = f"{PLATFORM_NAME} — Password reset code"
    message = (
        f"As-salamu alaykum {first_name} {last_name or 'there'},\n\n"
        f"We received a request to reset your {PLATFORM_NAME} password.\n\n"
        f"Your reset code is:\n\n"
        f"    {otp}\n\n"
        f"This code expires in {expiry_minutes} minutes.\n\n"
        f"If you did not request this, please secure your account immediately "
        f"or contact us at {SUPPORT_EMAIL}.\n\n"
        f"— The {PLATFORM_NAME} Team"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info("Password reset OTP sent to %s", email)
    except Exception as exc:
        logger.error("Failed to send password reset OTP to %s: %s", email, exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(name="users.send_welcome_email")
def send_welcome_email(email: str, first_name: str, last_name: str):
    """Send a welcome email after successful registration."""
    subject = f"Welcome to {PLATFORM_NAME}! 🌙"
    message = (
        f"As-salamu alaykum {first_name} {last_name or 'there'},\n\n"
        f"Welcome to {PLATFORM_NAME} — a trusted matrimonial platform "
        f"for conservative Sunni Muslims.\n\n"
        f"Here's how to get started:\n"
        f"  • Complete your profile and basic info to appear in the directory\n"
        f"  • Browse profiles of potential matches\n"
        f"  • Send connection requests to those you are interested in\n"
        f"  • Upgrade to a Monthly or Annual plan to unlock full features\n\n"
        f"If you need any assistance, please reach out at {SUPPORT_EMAIL}.\n\n"
        f"May Allah bless your search.\n\n"
        f"— The {PLATFORM_NAME} Team"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )
        logger.info("Welcome email sent to %s", email)
    except Exception as exc:
        logger.error("Failed to send welcome email to %s: %s", email, exc)