from django.urls import path

from .views import (
    AppleNotificationView,
    GoogleNotificationView,
    SubscriptionStatusView,
    VerifyPurchaseView,
)

urlpatterns = [
    path("verify/", VerifyPurchaseView.as_view(), name="iap-verify"),
    path("status/", SubscriptionStatusView.as_view(), name="iap-status"),
    path("apple/notifications/", AppleNotificationView.as_view(), name="iap-apple-notifications"),
    path("google/notifications/", GoogleNotificationView.as_view(), name="iap-google-notifications"),
]
