"""
notifications/push.py

Firebase Cloud Messaging (HTTP v1) delivery for the mobile apps.

Credentials — no service-account key file:
    The production EC2 instance has the IAM role `amm-ec2-fcm`. Google
    Workload Identity Federation trusts that role (pool `amm-aws-backend`,
    provider `amm-aws`) and lets it impersonate the Firebase Admin SDK
    service account. The role's temporary credentials are read from the EC2
    instance metadata service (IMDSv2).

    Important: the containers also carry AWS_ACCESS_KEY_ID/SECRET for the S3
    IAM user. google-auth would prefer those env vars over IMDS, and Google
    rejects that identity, so we always read the instance role explicitly via
    InstanceRoleSupplier.

    For local testing, GOOGLE_APPLICATION_CREDENTIALS may point at a service
    account JSON instead (FCM_CREDENTIALS_MODE=file).

Settings (core/settings.py):
    FCM_ENABLED, FCM_PROJECT_ID, FCM_CREDENTIALS_MODE,
    FCM_WIF_AUDIENCE, FCM_SERVICE_ACCOUNT
"""

import json
import logging
import threading
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_IMDS = "http://169.254.169.254/latest"

# FCM error codes meaning the token will never work again.
_DEAD_TOKEN_CODES = {"UNREGISTERED", "INVALID_ARGUMENT", "SENDER_ID_MISMATCH"}


class PushNotConfigured(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Credentials
# ─────────────────────────────────────────────────────────────────────────────

def _imds_token() -> str:
    req = urllib.request.Request(
        f"{_IMDS}/api/token",
        method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "300"},
    )
    return urllib.request.urlopen(req, timeout=3).read().decode()


def _imds_get(path: str, token: str) -> str:
    req = urllib.request.Request(
        f"{_IMDS}/{path}", headers={"X-aws-ec2-metadata-token": token}
    )
    return urllib.request.urlopen(req, timeout=3).read().decode()


def _build_wif_credentials():
    from google.auth import aws

    class InstanceRoleSupplier(aws.AwsSecurityCredentialsSupplier):
        """EC2 instance-role credentials from IMDSv2, ignoring AWS_* env vars."""

        def get_aws_security_credentials(self, context, request):
            token = _imds_token()
            role = _imds_get("meta-data/iam/security-credentials/", token).strip()
            data = json.loads(
                _imds_get(f"meta-data/iam/security-credentials/{role}", token)
            )
            return aws.AwsSecurityCredentials(
                data["AccessKeyId"], data["SecretAccessKey"], data["Token"]
            )

        def get_aws_region(self, context, request):
            return _imds_get("meta-data/placement/region", _imds_token()).strip()

    return aws.Credentials(
        audience=settings.FCM_WIF_AUDIENCE,
        subject_token_type="urn:ietf:params:aws:token-type:aws4_request",
        aws_security_credentials_supplier=InstanceRoleSupplier(),
        service_account_impersonation_url=(
            "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
            f"{settings.FCM_SERVICE_ACCOUNT}:generateAccessToken"
        ),
        scopes=[FCM_SCOPE],
    )


def _build_credentials():
    mode = settings.FCM_CREDENTIALS_MODE
    if mode == "wif":
        return _build_wif_credentials()
    if mode == "file":
        import google.auth

        creds, _ = google.auth.default(scopes=[FCM_SCOPE])
        return creds
    raise PushNotConfigured(f"Unknown FCM_CREDENTIALS_MODE {mode!r}")


_session = None
_session_lock = threading.Lock()


def _get_session():
    """One AuthorizedSession per process; it refreshes the token itself."""
    global _session
    with _session_lock:
        if _session is None:
            from google.auth.transport.requests import AuthorizedSession

            _session = AuthorizedSession(_build_credentials())
        return _session


# ─────────────────────────────────────────────────────────────────────────────
# Sending
# ─────────────────────────────────────────────────────────────────────────────

def build_message(token: str, title: str, body: str, data: dict) -> dict:
    """FCM v1 message. `data` values must be strings for FCM."""
    str_data = {str(k): "" if v is None else str(v) for k, v in (data or {}).items()}
    return {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": str_data,
            "android": {
                "priority": "high",
                "notification": {"sound": "default"},
            },
            "apns": {
                "headers": {"apns-priority": "10"},
                "payload": {"aps": {"sound": "default"}},
            },
        }
    }


def send_to_token(token: str, title: str, body: str, data: dict) -> str:
    """
    Send one message. Returns "ok", "dead" (token should be deleted) or
    "error" (temporary failure; keep the token).
    """
    url = (
        f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}"
        "/messages:send"
    )
    resp = _get_session().post(
        url, json=build_message(token, title, body, data), timeout=10
    )
    if resp.status_code == 200:
        return "ok"

    code = ""
    try:
        err = resp.json().get("error", {})
        for detail in err.get("details", []):
            code = detail.get("errorCode") or code
        code = code or err.get("status", "")
    except ValueError:
        pass

    if resp.status_code == 404 or code in _DEAD_TOKEN_CODES:
        return "dead"
    logger.warning("FCM send failed (%s %s): %s", resp.status_code, code, resp.text[:300])
    return "error"


def send_to_user(user, title: str, body: str, data: dict) -> int:
    """Send to every registered device of `user`. Returns devices reached."""
    from .models import DeviceToken

    sent = 0
    for device in DeviceToken.objects.filter(user=user):
        try:
            result = send_to_token(device.token, title, body, data)
        except Exception:
            logger.exception("FCM send crashed for device %s", device.pk)
            continue
        if result == "ok":
            sent += 1
        elif result == "dead":
            logger.info("Removing dead FCM token for %s", user.email)
            device.delete()
    return sent
