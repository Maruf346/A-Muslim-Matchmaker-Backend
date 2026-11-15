"""
subscriptions/views.py

  POST /api/subscriptions/verify/                — app sends a store purchase to verify
  GET  /api/subscriptions/status/                — current plan + top-up credits
  POST /api/subscriptions/apple/notifications/   — App Store Server Notifications V2
  POST /api/subscriptions/google/notifications/  — Google Play RTDN (Pub/Sub push)

The two notification endpoints never trust the payload: they only use it to
find which stored purchase changed, then re-check that purchase with the store.
"""

import base64
import json
import logging

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PurchaseStatus, StorePlatform, StorePurchase
from .serializers import SubscriptionStatusSerializer, VerifyPurchaseSerializer
from .services import PurchaseAlreadyClaimed, PurchaseService
from .stores import StoreNotConfigured, StoreVerificationError

logger = logging.getLogger(__name__)


def _status_payload(user):
    user.refresh_from_db(fields=["subscription_plan", "subscription_start", "subscription_end", "bonus_requests"])
    current = (
        StorePurchase.objects.filter(user=user, kind="subscription", status=PurchaseStatus.ACTIVE)
        .order_by("-expires_at")
        .first()
    )
    return SubscriptionStatusSerializer({
        "subscription_plan":  user.subscription_plan,
        "subscription_start": user.subscription_start,
        "subscription_end":   user.subscription_end,
        "auto_renewing":      bool(current and current.auto_renewing),
        "store_platform":     current.platform if current else None,
        "product_id":         current.product_id if current else None,
        "bonus_requests":     user.bonus_requests,
    }).data


@extend_schema(tags=["Subscriptions"])
class VerifyPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Verify an in-app purchase and apply it",
        request=VerifyPurchaseSerializer,
        responses={
            200: SubscriptionStatusSerializer,
            400: OpenApiResponse(description="Store rejected the purchase."),
            409: OpenApiResponse(description="Purchase belongs to another account."),
            503: OpenApiResponse(description="Store credentials not configured on the server."),
        },
    )
    def post(self, request):
        ser = VerifyPurchaseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            PurchaseService.verify_and_apply(
                request.user,
                platform=d["platform"],
                product_id=d["product_id"],
                verification_data=d["verification_data"],
                transaction_id=d.get("transaction_id") or None,
            )
        except PurchaseAlreadyClaimed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except StoreNotConfigured as exc:
            logger.error("IAP verify not configured: %s", exc)
            return Response(
                {"detail": "Purchases are temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except StoreVerificationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_status_payload(request.user), status=status.HTTP_200_OK)


@extend_schema(tags=["Subscriptions"])
class SubscriptionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get my subscription status", responses={200: SubscriptionStatusSerializer})
    def get(self, request):
        return Response(_status_payload(request.user))


def _b64url_json(segment: str) -> dict:
    segment += "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment))


def _jws_payload(jws: str) -> dict:
    return _b64url_json(jws.split(".")[1])


def _revalidate_quietly(purchase: StorePurchase):
    try:
        PurchaseService.revalidate(purchase)
    except StoreVerificationError as exc:
        logger.warning("Revalidation after notification failed for %s: %s", purchase.pk, exc)


@extend_schema(exclude=True)
@method_decorator(csrf_exempt, name="dispatch")
class AppleNotificationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            payload = _jws_payload(request.data["signedPayload"])
            tx = _jws_payload(payload["data"]["signedTransactionInfo"])
            original_id = tx["originalTransactionId"]
        except (KeyError, ValueError, IndexError, TypeError):
            return Response(status=status.HTTP_200_OK)   # not ours / test ping

        purchase = StorePurchase.objects.filter(
            platform=StorePlatform.APPLE, store_key=original_id
        ).first()
        if purchase:
            _revalidate_quietly(purchase)
        logger.info("Apple notification %s for %s", payload.get("notificationType"), original_id)
        return Response(status=status.HTTP_200_OK)


@extend_schema(exclude=True)
@method_decorator(csrf_exempt, name="dispatch")
class GoogleNotificationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        expected = getattr(settings, "GOOGLE_RTDN_TOKEN", "")
        if expected and request.query_params.get("token") != expected:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            data = json.loads(base64.b64decode(request.data["message"]["data"]))
        except (KeyError, ValueError, TypeError):
            return Response(status=status.HTTP_200_OK)

        token = (
            (data.get("subscriptionNotification") or {}).get("purchaseToken")
            or (data.get("voidedPurchaseNotification") or {}).get("purchaseToken")
        )
        if token:
            purchase = StorePurchase.objects.filter(platform=StorePlatform.GOOGLE, store_key=token).first()
            if purchase:
                if data.get("voidedPurchaseNotification"):
                    purchase.status = PurchaseStatus.REVOKED
                    purchase.save(update_fields=["status", "updated_at"])
                    from .services import EntitlementService
                    EntitlementService.sync_user(purchase.user)
                else:
                    _revalidate_quietly(purchase)
        return Response(status=status.HTTP_200_OK)
