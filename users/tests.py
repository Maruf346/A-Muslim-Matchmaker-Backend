from datetime import date

from django.test import override_settings
from django.urls import reverse
from questions.models import MaleBasicInfo
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from users.models import Gender, User, UserRole
from users.serializers import _build_token_data


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

    def test_user_profile_and_token_include_is_verified(self):
        initial_response = self.client.get(self.url)
        self.assertEqual(initial_response.status_code, status.HTTP_200_OK)
        self.assertIs(initial_response.data["is_verified"], False)
        self.assertIs(_build_token_data(self.user)["user"]["is_verified"], False)

        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])

        verified_response = self.client.get(self.url)
        self.assertEqual(verified_response.status_code, status.HTTP_200_OK)
        self.assertIs(verified_response.data["is_verified"], True)
        self.assertIs(_build_token_data(self.user)["user"]["is_verified"], True)
