"""
user/tasks.py

Celery email tasks — FixGo branded.
All tasks use exponential back-off retry (max 3 attempts).
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

PLATFORM_NAME  = "FixGo"
SUPPORT_EMAIL  = getattr(settings, "SUPPORT_EMAIL", "support@fixgo.com")


@shared_task(bind=True, max_retries=3, name="user.send_registration_otp_email")
def send_registration_otp_email(self, email: str, otp: str, full_name: str):
    subject = f"{PLATFORM_NAME} — Verify your email"
    message = f"""Hi {full_name or "there"},

Thank you for joining {PLATFORM_NAME}!

Your email verification code is:

    {otp}

This code expires in {getattr(settings, 'OTP_EXPIRY_SECONDS', 300) // 60} minutes.

If you didn't create a {PLATFORM_NAME} account, please ignore this email.

— The {PLATFORM_NAME} Team
"""
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


@shared_task(bind=True, max_retries=3, name="user.send_password_reset_otp_email")
def send_password_reset_otp_email(self, email: str, otp: str, full_name: str):
    subject = f"{PLATFORM_NAME} — Password reset code"
    message = f"""Hi {full_name or "there"},

We received a request to reset your {PLATFORM_NAME} password.

Your reset code is:

    {otp}

This code expires in {getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_SECONDS', 600) // 60} minutes.

If you didn't request this, please secure your account immediately.

— The {PLATFORM_NAME} Team
"""
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


@shared_task(name="user.send_welcome_email")
def send_welcome_email(email: str, full_name: str):
    subject = f"Welcome to {PLATFORM_NAME}! 🎉"
    message = f"""Hi {full_name or "there"},

Welcome to {PLATFORM_NAME} — your on-demand home services platform!

Here's what you can do:
  • Browse services and book a skilled artisan in minutes
  • Track your artisan in real time
  • Pay securely through the app
  • Rate and review after every job

If you need any help, just reach out at {SUPPORT_EMAIL}.

— The {PLATFORM_NAME} Team
"""
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