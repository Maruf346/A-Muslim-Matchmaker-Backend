"""
subscriptions/products.py

Single source of truth for the store product catalogue.

The same product IDs are configured in App Store Connect and Google Play
Console, and hard-coded in the Flutter app (lib/core/constants/iap_products.dart).
Change all three together.
"""

from users.models import SubscriptionPlan

MONTHLY_PRODUCT_ID = "amm_premium_monthly"
ANNUAL_PRODUCT_ID  = "amm_premium_annual"
TOPUP_PRODUCT_ID   = "amm_topup_3_connections"

# How many extra connection requests one top-up purchase grants.
TOPUP_REQUEST_CREDITS = 3

KIND_SUBSCRIPTION = "subscription"
KIND_CONSUMABLE   = "consumable"

PRODUCTS = {
    MONTHLY_PRODUCT_ID: {"kind": KIND_SUBSCRIPTION, "plan": SubscriptionPlan.MONTHLY},
    ANNUAL_PRODUCT_ID:  {"kind": KIND_SUBSCRIPTION, "plan": SubscriptionPlan.ANNUAL},
    TOPUP_PRODUCT_ID:   {"kind": KIND_CONSUMABLE,   "credits": TOPUP_REQUEST_CREDITS},
}

# Higher rank wins when a user somehow holds two active subscriptions.
PLAN_RANK = {
    SubscriptionPlan.FREE:    0,
    SubscriptionPlan.MONTHLY: 1,
    SubscriptionPlan.ANNUAL:  2,
}


def get_product(product_id: str) -> dict | None:
    return PRODUCTS.get(product_id)
