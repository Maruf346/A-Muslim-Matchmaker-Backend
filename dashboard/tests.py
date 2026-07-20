from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from dashboard.models import ActivityType, RecentActivity
from users.models import User, UserRole


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "dashboard-tests",
        }
    }
)
class RecentActivityPaginationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="dashboard-admin@example.com",
            password="testpass123",
            first_name="Dashboard",
            last_name="Admin",
            role=UserRole.MATCHMAKER,
            is_active=True,
        )
        self.primary_user = User.objects.create_user(
            email="activity-user@example.com",
            password="testpass123",
            first_name="Activity",
            last_name="User",
            role=UserRole.MALE,
            is_active=True,
        )
        for idx in range(3):
            RecentActivity.objects.create(
                activity_type=ActivityType.USER_REGISTERED,
                title=f"Activity {idx + 1}",
                description="Recent dashboard activity.",
                primary_user=self.primary_user,
                primary_user_name=self.primary_user.full_name,
            )

        self.client.force_authenticate(user=self.admin_user)
        self.url = reverse("dashboard-recent-activities")

    def test_recent_activity_list_returns_paginated_response(self):
        response = self.client.get(self.url, {"page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)
        self.assertEqual(response.data["count"], 3)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)
