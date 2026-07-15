from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from users.models import Gender, User, UserRole


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "matches-tests",
        }
    }
)
class FreePlanConnectionRequestTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.male_user = User.objects.create_user(
            email="free-male@example.com",
            password="testpass123",
            first_name="Free",
            last_name="Male",
            role=UserRole.MALE,
            gender=Gender.MALE,
            subscription_plan="free",
            is_active=True,
        )
        self.target_one = self._create_female_user("target-one@example.com", "Target", "One")
        self.target_two = self._create_female_user("target-two@example.com", "Target", "Two")
        self.target_three = self._create_female_user("target-three@example.com", "Target", "Three")

        self.send_url = reverse("request-send")
        self.usage_url = reverse("connection-usage")
        self.client.force_authenticate(user=self.male_user)

    def _create_female_user(self, email, first_name, last_name):
        return User.objects.create_user(
            email=email,
            password="testpass123",
            first_name=first_name,
            last_name=last_name,
            role=UserRole.FEMALE,
            gender=Gender.FEMALE,
            subscription_plan="free",
            is_active=True,
        )

    def test_free_user_can_send_two_connection_requests(self):
        first_response = self.client.post(self.send_url, {"target_user_id": str(self.target_one.id)}, format="json")
        second_response = self.client.post(self.send_url, {"target_user_id": str(self.target_two.id)}, format="json")
        usage_response = self.client.get(self.usage_url)

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(usage_response.status_code, status.HTTP_200_OK)
        self.assertEqual(usage_response.data["subscription_plan"], "free")
        self.assertEqual(usage_response.data["requests_sent"], 2)
        self.assertEqual(usage_response.data["requests_remaining"], 0)
        self.assertEqual(usage_response.data["monthly_limit"], 2)

    def test_free_user_cannot_send_a_third_connection_request(self):
        self.client.post(self.send_url, {"target_user_id": str(self.target_one.id)}, format="json")
        self.client.post(self.send_url, {"target_user_id": str(self.target_two.id)}, format="json")

        third_response = self.client.post(
            self.send_url,
            {"target_user_id": str(self.target_three.id)},
            format="json",
        )

        self.assertEqual(third_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Free users can send up to 2 connection requests", third_response.data["error"])
