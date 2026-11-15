"""
subscriptions/services.py

PurchaseService       — verify a purchase with the store and record it.
EntitlementService    — derive the user's plan / credits from their purchases.
"""

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from users.models import SubscriptionPlan, User

from .models import PurchaseStatus, StorePlatform, StorePurchase
from .products import KIND_CONSUMABLE, KIND_SUBSCRIPTION, PLAN_RANK, get_product
from .stores import AppleStore, GooglePlayStore, StoreVerificationError, VerifiedPurchase

logger = logging.getLogger(__name__)

# Extra time after expiry before we downgrade, so a renewal that Apple/Google
# hasn't reported yet doesn't flicker the user to Free.
EXPIRY_GRACE = timedelta(hours=6)


class PurchaseAlreadyClaimed(Exception):
    """The store purchase is already linked to a different app account."""


def _store_for(platform: str):
    if platform == StorePlatform.APPLE:
        return AppleStore
    if platform == StorePlatform.GOOGLE:
        return GooglePlayStore
    raise StoreVerificationError(f"Unknown platform '{platform}'.")


def _verify_with_store(platform, product_id, verification_data, transaction_id) -> VerifiedPurchase:
    product = get_product(product_id)
    if product is None:
        raise StoreVerificationError(f"Unknown product '{product_id}'.")
    store = _store_for(platform)
    if product["kind"] == KIND_SUBSCRIPTION:
        return store.verify_subscription(verification_data, product_id, transaction_id)
    return store.verify_consumable(verification_data, product_id, transaction_id)


class PurchaseService:

    @staticmethod
    @transaction.atomic
    def verify_and_apply(user, *, platform: str, product_id: str,
                         verification_data: str, transaction_id: str | None = None) -> StorePurchase:
        verified = _verify_with_store(platform, product_id, verification_data, transaction_id)
        product  = get_product(product_id)

        existing = (
            StorePurchase.objects.select_for_update()
            .filter(platform=platform, store_key=verified.store_key)
            .first()
        )
        if existing and existing.user_id != user.id:
            raise PurchaseAlreadyClaimed(
                "This purchase is already linked to another A Muslim Matchmaker account."
            )

        purchase = existing or StorePurchase(
            user=user, platform=platform, store_key=verified.store_key,
            product_id=product_id, kind=product["kind"],
        )
        PurchaseService._copy_verified(purchase, verified)

        if product["kind"] == KIND_CONSUMABLE:
            PurchaseService._grant_credits_once(purchase, product)

        try:
            purchase.save()
        except IntegrityError as exc:   # lost a race with a parallel verify call
            raise PurchaseAlreadyClaimed("This purchase was just processed. Please refresh.") from exc

        if product["kind"] == KIND_SUBSCRIPTION:
            EntitlementService.sync_user(user)
        return purchase

    @staticmethod
    def _copy_verified(purchase: StorePurchase, v: VerifiedPurchase):
        purchase.product_id = v.product_id
        purchase.order_id   = v.order_id or purchase.order_id
        purchase.started_at = v.started_at or purchase.started_at
        purchase.expires_at = v.expires_at
        purchase.auto_renewing = v.auto_renewing
        if v.latest_receipt:
            purchase.latest_receipt = v.latest_receipt
        purchase.raw_response = v.raw
        purchase.last_verified_at = timezone.now()
        if purchase.status != PurchaseStatus.CONSUMED or v.status == "revoked":
            purchase.status = v.status

    @staticmethod
    def _grant_credits_once(purchase: StorePurchase, product: dict):
        """Add top-up credits exactly once per store transaction."""
        if purchase.credits_granted or purchase.status != PurchaseStatus.ACTIVE:
            return
        credits = product["credits"]
        User.objects.filter(pk=purchase.user_id).update(bonus_requests=F("bonus_requests") + credits)
        purchase.credits_granted = credits
        purchase.status = PurchaseStatus.CONSUMED

    @staticmethod
    def revalidate(purchase: StorePurchase) -> StorePurchase:
        """Re-check a stored subscription with the store (renewals, refunds, expiry)."""
        if purchase.kind != KIND_SUBSCRIPTION:
            return purchase
        data = purchase.latest_receipt if purchase.platform == StorePlatform.APPLE else purchase.store_key
        if not data:
            return purchase
        verified = _verify_with_store(purchase.platform, purchase.product_id, data, None)
        PurchaseService._copy_verified(purchase, verified)
        purchase.save()
        EntitlementService.sync_user(purchase.user)
        return purchase


class EntitlementService:

    @staticmethod
    def sync_user(user):
        """
        Set subscription_plan / start / end from the user's active store
        subscriptions. Users with no store subscriptions at all (e.g. plans
        granted by an admin) are left untouched.
        """
        subs = list(StorePurchase.objects.filter(user=user, kind=KIND_SUBSCRIPTION))
        if not subs:
            return

        now = timezone.now()
        active = [
            p for p in subs
            if p.status == PurchaseStatus.ACTIVE and p.expires_at and p.expires_at + EXPIRY_GRACE > now
        ]

        user.refresh_from_db(fields=["subscription_plan", "subscription_start", "subscription_end"])
        old_plan = user.subscription_plan

        if active:
            best = max(
                active,
                key=lambda p: (PLAN_RANK[get_product(p.product_id)["plan"]], p.expires_at),
            )
            new_plan = get_product(best.product_id)["plan"]
            user.subscription_plan = new_plan
            user.subscription_end  = best.expires_at
            if old_plan != new_plan or user.subscription_start is None:
                user.subscription_start = best.started_at or now
        else:
            user.subscription_plan = SubscriptionPlan.FREE
            last = max((p.expires_at for p in subs if p.expires_at), default=None)
            user.subscription_end = last

        user.save(update_fields=["subscription_plan", "subscription_start", "subscription_end"])
        if old_plan != user.subscription_plan:
            logger.info("User %s plan %s → %s", user.pk, old_plan, user.subscription_plan)

    @staticmethod
    def expire_lapsed_users() -> int:
        """
        Periodic job: re-check store subscriptions for users whose paid plan
        has run out, then downgrade any that really lapsed.
        """
        cutoff = timezone.now() - EXPIRY_GRACE
        users = User.objects.filter(
            subscription_plan__in=[SubscriptionPlan.MONTHLY, SubscriptionPlan.ANNUAL],
            subscription_end__lt=cutoff,
            store_purchases__kind=KIND_SUBSCRIPTION,
        ).distinct()

        changed = 0
        for user in users:
            for purchase in user.store_purchases.filter(kind=KIND_SUBSCRIPTION, status=PurchaseStatus.ACTIVE):
                try:
                    PurchaseService.revalidate(purchase)
                except StoreVerificationError as exc:
                    logger.warning("Revalidate failed for purchase %s: %s", purchase.pk, exc)
            before = user.subscription_plan
            EntitlementService.sync_user(user)
            if user.subscription_plan != before:
                changed += 1
        return changed
