from datetime import date

from django.test import override_settings
from django.urls import reverse
from questions.models import MaleBasicInfo
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from users.models import Gender, User, UserRole


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "users-tests",
        }
    }
)
class UserProfileCompletionTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="profile-user@example.com",
            password="testpass123",
            first_name="Profile",
            last_name="User",
            role=UserRole.MALE,
            gender=Gender.MALE,
            subscription_plan="monthly",
            is_active=True,
        )
        MaleBasicInfo.objects.create(
            user=self.user,
            how_found=["friend"],
            phone="1234567890",
            date_of_birth=date(1992, 1, 1),
            city="Dhaka",
            country="Bangladesh",
            pref_age_min=22,
            pref_age_max=30,
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse("user-profile")

    def test_user_profile_includes_profile_completion_percentage(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("profile_completion_percentage", response.data)
        self.assertEqual(
            response.data["profile_completion_percentage"],
            self.user.male_basic_info.completion_percentage,
        )
