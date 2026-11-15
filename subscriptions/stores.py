"""
subscriptions/stores.py

Talks to Apple and Google to verify purchases. Nothing here trusts data sent
by the app: every purchase is confirmed directly with the store.

Apple  — /verifyReceipt with the app-specific shared secret
         (env APPLE_SHARED_SECRET). Production first, then sandbox on 21007,
         which is how TestFlight and App Review purchases are verified.
Google — Android Publisher API v3 with a service account that has been
         invited in Play Console (env GOOGLE_PLAY_SERVICE_ACCOUNT_FILE or
         GOOGLE_PLAY_SERVICE_ACCOUNT_JSON).
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class StoreVerificationError(Exception):
    """The store rejected the purchase, or we could not reach it."""


class StoreNotConfigured(StoreVerificationError):
    """Server-side credentials for this store are missing."""


@dataclass
class VerifiedPurchase:
    product_id: str
    store_key: str
    order_id: str = ""
    status: str = "active"            # active | expired | revoked | pending
    started_at: datetime | None = None
    expires_at: datetime | None = None
    auto_renewing: bool = False
    latest_receipt: str = ""
    raw: dict = field(default_factory=dict)


def _ms_to_dt(value) -> datetime | None:
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=dt_timezone.utc)


def _rfc3339_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ─────────────────────────────────────────────────────────────────────────────
# Apple
# ─────────────────────────────────────────────────────────────────────────────

APPLE_PRODUCTION_URL = "https://buy.itunes.apple.com/verifyReceipt"
APPLE_SANDBOX_URL    = "https://sandbox.itunes.apple.com/verifyReceipt"


class AppleStore:

    @staticmethod
    def _post_receipt(receipt: str) -> dict:
        secret = getattr(settings, "APPLE_SHARED_SECRET", "")
        if not secret:
            raise StoreNotConfigured("APPLE_SHARED_SECRET is not set on the server.")

        payload = {
            "receipt-data": receipt,
            "password": secret,
            "exclude-old-transactions": True,
        }
        try:
            resp = requests.post(APPLE_PRODUCTION_URL, json=payload, timeout=20)
            data = resp.json()
            if data.get("status") == 21007:   # sandbox receipt sent to production
                resp = requests.post(APPLE_SANDBOX_URL, json=payload, timeout=20)
                data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise StoreVerificationError(f"Could not reach Apple: {exc}") from exc

        status = data.get("status")
        if status != 0:
            raise StoreVerificationError(f"Apple rejected the receipt (status {status}).")

        bundle_id = data.get("receipt", {}).get("bundle_id")
        expected = getattr(settings, "APPLE_BUNDLE_ID", "")
        if expected and bundle_id != expected:
            raise StoreVerificationError("Receipt belongs to a different app.")
        return data

    @classmethod
    def verify_subscription(cls, receipt: str, product_id: str,
                            transaction_id: str | None = None) -> VerifiedPurchase:
        data = cls._post_receipt(receipt)
        items = [
            i for i in (data.get("latest_receipt_info") or [])
            if i.get("product_id") == product_id
        ]
        if not items:
            raise StoreVerificationError("This subscription is not in the receipt.")

        latest = max(items, key=lambda i: int(i.get("expires_date_ms") or 0))
        original_id = latest["original_transaction_id"]

        renewal = next(
            (r for r in (data.get("pending_renewal_info") or [])
             if r.get("original_transaction_id") == original_id),
            {},
        )

        expires_at = _ms_to_dt(latest.get("expires_date_ms"))
        if latest.get("cancellation_date_ms"):
            status = "revoked"
        elif expires_at and expires_at > datetime.now(tz=dt_timezone.utc):
            status = "active"
        else:
            status = "expired"

        first = min(items, key=lambda i: int(i.get("original_purchase_date_ms") or i.get("purchase_date_ms") or 0))
        return VerifiedPurchase(
            product_id=product_id,
            store_key=original_id,
            order_id=latest.get("transaction_id", ""),
            status=status,
            started_at=_ms_to_dt(first.get("original_purchase_date_ms") or first.get("purchase_date_ms")),
            expires_at=expires_at,
            auto_renewing=renewal.get("auto_renew_status") == "1",
            latest_receipt=data.get("latest_receipt") or receipt,
            raw={"latest": latest, "renewal": renewal, "environment": data.get("environment")},
        )

    @classmethod
    def verify_consumable(cls, receipt: str, product_id: str,
                          transaction_id: str | None) -> VerifiedPurchase:
        if not transaction_id:
            raise StoreVerificationError("transaction_id is required for one-time purchases.")
        data = cls._post_receipt(receipt)
        in_app = data.get("receipt", {}).get("in_app") or []
        item = next(
            (i for i in in_app
             if i.get("transaction_id") == transaction_id and i.get("product_id") == product_id),
            None,
        )
        if item is None:
            raise StoreVerificationError("This purchase is not in the receipt.")
        return VerifiedPurchase(
            product_id=product_id,
            store_key=item["transaction_id"],
            order_id=item["transaction_id"],
            status="revoked" if item.get("cancellation_date_ms") else "active",
            started_at=_ms_to_dt(item.get("purchase_date_ms")),
            raw={"item": item, "environment": data.get("environment")},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Google
# ─────────────────────────────────────────────────────────────────────────────

GOOGLE_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
GOOGLE_API   = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"


class GooglePlayStore:
    _session = None

    @classmethod
    def _authed_session(cls):
        if cls._session is not None:
            return cls._session

        import google.auth
        import google.auth.exceptions
        from google.auth.transport.requests import AuthorizedSession

        # Accepts a service-account key OR a Workload Identity Federation
        # (external_account) config, so keyless setups work too.
        raw_json = getattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")
        path     = getattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE", "")
        try:
            if raw_json:
                creds, _ = google.auth.load_credentials_from_dict(json.loads(raw_json), scopes=[GOOGLE_SCOPE])
            elif path:
                creds, _ = google.auth.load_credentials_from_file(path, scopes=[GOOGLE_SCOPE])
            else:
                raise StoreNotConfigured("Google Play service account is not configured on the server.")
        except (OSError, ValueError, google.auth.exceptions.GoogleAuthError) as exc:
            raise StoreNotConfigured(f"Google Play credentials could not be loaded: {exc}") from exc

        cls._session = AuthorizedSession(creds)
        return cls._session

    @classmethod
    def _package(cls) -> str:
        pkg = getattr(settings, "GOOGLE_PLAY_PACKAGE_NAME", "")
        if not pkg:
            raise StoreNotConfigured("GOOGLE_PLAY_PACKAGE_NAME is not set on the server.")
        return pkg

    @classmethod
    def _request(cls, method: str, url: str, **kwargs) -> dict:
        try:
            resp = cls._authed_session().request(method, url, timeout=20, **kwargs)
        except requests.RequestException as exc:
            raise StoreVerificationError(f"Could not reach Google Play: {exc}") from exc
        if resp.status_code >= 400:
            logger.warning("Google Play API %s %s → %s %s", method, url, resp.status_code, resp.text[:500])
            raise StoreVerificationError(f"Google Play rejected the purchase ({resp.status_code}).")
        return resp.json() if resp.content else {}

    @classmethod
    def verify_subscription(cls, purchase_token: str, product_id: str,
                            transaction_id: str | None = None) -> VerifiedPurchase:
        pkg = cls._package()
        data = cls._request("GET", f"{GOOGLE_API}/{pkg}/purchases/subscriptionsv2/tokens/{purchase_token}")

        line = next((li for li in data.get("lineItems", []) if li.get("productId") == product_id), None)
        if line is None:
            raise StoreVerificationError("This token is not for the requested subscription.")

        state = data.get("subscriptionState", "")
        status = {
            "SUBSCRIPTION_STATE_ACTIVE":           "active",
            "SUBSCRIPTION_STATE_IN_GRACE_PERIOD":  "active",
            "SUBSCRIPTION_STATE_CANCELED":         "active",   # cancelled = won't renew, still paid up
            "SUBSCRIPTION_STATE_PENDING":          "pending",
            "SUBSCRIPTION_STATE_ON_HOLD":          "expired",
            "SUBSCRIPTION_STATE_PAUSED":           "expired",
            "SUBSCRIPTION_STATE_EXPIRED":          "expired",
        }.get(state, "expired")

        expires_at = _rfc3339_to_dt(line.get("expiryTime"))
        if status == "active" and expires_at and expires_at <= datetime.now(tz=dt_timezone.utc):
            status = "expired"

        if data.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_PENDING" and status == "active":
            try:
                cls._request(
                    "POST",
                    f"{GOOGLE_API}/{pkg}/purchases/subscriptions/{product_id}/tokens/{purchase_token}:acknowledge",
                    json={},
                )
            except StoreVerificationError:
                logger.warning("Could not acknowledge Google subscription; the app will acknowledge it.")

        return VerifiedPurchase(
            product_id=product_id,
            store_key=purchase_token,
            order_id=data.get("latestOrderId", ""),
            status=status,
            started_at=_rfc3339_to_dt(data.get("startTime")),
            expires_at=expires_at,
            auto_renewing=bool(line.get("autoRenewingPlan", {}).get("autoRenewEnabled")),
            raw=data,
        )

    @classmethod
    def verify_consumable(cls, purchase_token: str, product_id: str,
                          transaction_id: str | None = None) -> VerifiedPurchase:
        pkg = cls._package()
        data = cls._request("GET", f"{GOOGLE_API}/{pkg}/purchases/products/{product_id}/tokens/{purchase_token}")
        purchase_state = data.get("purchaseState")   # 0 purchased, 1 cancelled, 2 pending
        status = {0: "active", 1: "revoked", 2: "pending"}.get(purchase_state, "revoked")
        return VerifiedPurchase(
            product_id=product_id,
            store_key=purchase_token,
            order_id=data.get("orderId", ""),
            status=status,
            started_at=_ms_to_dt(data.get("purchaseTimeMillis")),
            raw=data,
        )
