from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from matches.services import SubscriptionLimitService
from subscriptions.products import ANNUAL_PRODUCT_ID, MONTHLY_PRODUCT_ID, TOPUP_PRODUCT_ID
from subscriptions.services import EntitlementService
from subscriptions.stores import StoreVerificationError, VerifiedPurchase

User = get_user_model()
URL = "/api/subscriptions/verify/"


def _sub(product, key="orig-1", days=30, status="active"):
    now = timezone.now()
    return VerifiedPurchase(
        product_id=product, store_key=key, order_id="tx",
        status=status, started_at=now, expires_at=now + timedelta(days=days),
        auto_renewing=True, latest_receipt="receipt",
    )


class VerifyPurchaseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="a@example.com", password="pw-123456")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def post(self, product, platform="apple", tx=None):
        return self.client.post(URL, {
            "platform": platform, "product_id": product,
            "verification_data": "data", "transaction_id": tx,
        }, format="json")

    @mock.patch("subscriptions.stores.AppleStore.verify_subscription")
    def test_monthly_subscription_upgrades_user(self, verify):
        verify.return_value = _sub(MONTHLY_PRODUCT_ID)
        r = self.post(MONTHLY_PRODUCT_ID)
        self.assertEqual(r.status_code, 200, r.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription_plan, "monthly")
        self.assertTrue(r.data["auto_renewing"])

    @mock.patch("subscriptions.stores.GooglePlayStore.verify_subscription")
    def test_annual_beats_monthly(self, verify):
        verify.return_value = _sub(MONTHLY_PRODUCT_ID, key="tok-m")
        self.post(MONTHLY_PRODUCT_ID, platform="google")
        verify.return_value = _sub(ANNUAL_PRODUCT_ID, key="tok-a", days=365)
        self.post(ANNUAL_PRODUCT_ID, platform="google")
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription_plan, "annual")

    @mock.patch("subscriptions.stores.AppleStore.verify_subscription")
    def test_same_purchase_cannot_be_claimed_by_second_account(self, verify):
        verify.return_value = _sub(MONTHLY_PRODUCT_ID)
        self.post(MONTHLY_PRODUCT_ID)
        other = User.objects.create_user(email="b@example.com", password="pw-123456")
        self.client.force_authenticate(other)
        r = self.post(MONTHLY_PRODUCT_ID)
        self.assertEqual(r.status_code, 409)
        other.refresh_from_db()
        self.assertEqual(other.subscription_plan, "free")

    @mock.patch("subscriptions.stores.AppleStore.verify_consumable")
    def test_topup_grants_credits_once(self, verify):
        verify.return_value = VerifiedPurchase(product_id=TOPUP_PRODUCT_ID, store_key="tx-1", status="active")
        self.post(TOPUP_PRODUCT_ID, tx="tx-1")
        self.post(TOPUP_PRODUCT_ID, tx="tx-1")   # retried by the app
        self.user.refresh_from_db()
        self.assertEqual(self.user.bonus_requests, 3)

    @mock.patch("subscriptions.stores.AppleStore.verify_subscription")
    def test_store_rejection_is_400(self, verify):
        verify.side_effect = StoreVerificationError("bad receipt")
        r = self.post(MONTHLY_PRODUCT_ID)
        self.assertEqual(r.status_code, 400)

    @mock.patch("subscriptions.stores.AppleStore.verify_subscription")
    def test_expired_subscription_downgrades(self, verify):
        verify.return_value = _sub(MONTHLY_PRODUCT_ID)
        self.post(MONTHLY_PRODUCT_ID)
        verify.return_value = _sub(MONTHLY_PRODUCT_ID, days=-2, status="expired")
        purchase = self.user.store_purchases.get()
        from subscriptions.services import PurchaseService
        PurchaseService.revalidate(purchase)
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription_plan, "free")

    def test_admin_granted_plan_is_left_alone(self):
        self.user.subscription_plan = "annual"
        self.user.save()
        EntitlementService.sync_user(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.subscription_plan, "annual")


class BonusRequestLimitTests(TestCase):
    def test_bonus_only_used_after_plan_allowance(self):
        user = User.objects.create_user(email="c@example.com", password="pw-123456",
                                        subscription_plan="monthly", subscription_start=timezone.now())
        user.bonus_requests = 3
        user.save()
        with mock.patch.object(SubscriptionLimitService, "get_requests_sent_this_cycle", return_value=10):
            self.assertTrue(SubscriptionLimitService.can_send_request(user)[0])
            self.assertEqual(SubscriptionLimitService.get_remaining_requests(user), 3)
        with mock.patch.object(SubscriptionLimitService, "get_requests_sent_this_cycle", return_value=11):
            SubscriptionLimitService.record_request_sent(user)
        self.assertEqual(user.bonus_requests, 2)
        with mock.patch.object(SubscriptionLimitService, "get_requests_sent_this_cycle", return_value=5):
            SubscriptionLimitService.record_request_sent(user)
        self.assertEqual(user.bonus_requests, 2)
