from rest_framework import serializers

from .models import StorePlatform
from .products import PRODUCTS


class VerifyPurchaseSerializer(serializers.Serializer):
    platform          = serializers.ChoiceField(choices=StorePlatform.choices)
    product_id        = serializers.ChoiceField(choices=sorted(PRODUCTS.keys()))
    verification_data = serializers.CharField(
        help_text="iOS: base64 app receipt (serverVerificationData). Android: purchase token."
    )
    transaction_id    = serializers.CharField(
        required=False, allow_blank=True, allow_null=True,
        help_text="Store transaction / purchase ID (required for iOS one-time purchases).",
    )


class SubscriptionStatusSerializer(serializers.Serializer):
    subscription_plan  = serializers.CharField()
    subscription_start = serializers.DateTimeField(allow_null=True)
    subscription_end   = serializers.DateTimeField(allow_null=True)
    auto_renewing      = serializers.BooleanField()
    store_platform     = serializers.CharField(allow_null=True)
    product_id         = serializers.CharField(allow_null=True)
    bonus_requests     = serializers.IntegerField()
