"""
subscriptions/models.py

StorePurchase — one row per verified App Store / Google Play purchase.

  • Apple subscriptions are keyed by original_transaction_id (stable across renewals).
  • Apple consumables are keyed by transaction_id.
  • Google purchases (subscriptions and consumables) are keyed by purchase token.

The unique (platform, store_key) constraint makes verification idempotent and
stops one store purchase being claimed by two app accounts.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class StorePlatform(models.TextChoices):
    APPLE  = "apple",  "Apple App Store"
    GOOGLE = "google", "Google Play"


class PurchaseStatus(models.TextChoices):
    ACTIVE   = "active",   "Active"
    EXPIRED  = "expired",  "Expired"
    REVOKED  = "revoked",  "Revoked / refunded"
    CONSUMED = "consumed", "Consumed (credits granted)"
    PENDING  = "pending",  "Pending payment"


class StorePurchase(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="store_purchases",
    )
    platform   = models.CharField(max_length=10, choices=StorePlatform.choices)
    product_id = models.CharField(max_length=100)
    kind       = models.CharField(max_length=20)  # "subscription" | "consumable"
    store_key  = models.CharField(
        max_length=512,
        help_text="Apple original_transaction_id / transaction_id, or Google purchase token.",
    )
    order_id   = models.CharField(max_length=255, blank=True, default="")
    status     = models.CharField(
        max_length=20, choices=PurchaseStatus.choices, default=PurchaseStatus.ACTIVE
    )
    started_at   = models.DateTimeField(null=True, blank=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    auto_renewing = models.BooleanField(default=False)
    credits_granted = models.PositiveIntegerField(default=0)

    # Apple: latest base64 receipt, kept so the server can re-validate renewals.
    latest_receipt = models.TextField(blank=True, default="")
    raw_response   = models.JSONField(default=dict, blank=True)

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
    last_verified_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "store_key"], name="unique_store_purchase"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "kind", "status"]),
        ]

    def __str__(self):
        return f"{self.user} · {self.platform} · {self.product_id} · {self.status}"

    @property
    def is_active_subscription(self) -> bool:
        return (
            self.kind == "subscription"
            and self.status == PurchaseStatus.ACTIVE
            and self.expires_at is not None
            and self.expires_at > timezone.now()
        )
