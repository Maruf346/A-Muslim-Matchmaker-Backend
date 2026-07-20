import shutil
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from questions.models import FemaleBasicInfo, MaleBasicInfo, UserPhoto
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from users.models import Gender, User, UserRole

TEST_MEDIA_ROOT = tempfile.mkdtemp()


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


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "matches-tests",
        }
    },
    MEDIA_ROOT=TEST_MEDIA_ROOT,
)
class SuggestedMatchesPhotosTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="monthly-male@example.com",
            password="testpass123",
            first_name="Monthly",
            last_name="Brother",
            role=UserRole.MALE,
            gender=Gender.MALE,
            subscription_plan="monthly",
            is_active=True,
        )
        self.candidate = User.objects.create_user(
            email="candidate@example.com",
            password="testpass123",
            first_name="Candidate",
            last_name="Sister",
            role=UserRole.FEMALE,
            gender=Gender.FEMALE,
            subscription_plan="free",
            is_active=True,
        )

        MaleBasicInfo.objects.create(
            user=self.user,
            date_of_birth=date(1992, 1, 1),
            pref_age_min=25,
            pref_age_max=35,
        )
        FemaleBasicInfo.objects.create(
            user=self.candidate,
            date_of_birth=date(1995, 1, 1),
            pref_age_min=30,
            pref_age_max=40,
        )
        UserPhoto.objects.create(
            user=self.candidate,
            image=SimpleUploadedFile(
                "candidate.jpg",
                b"filecontent",
                content_type="image/jpeg",
            ),
            is_primary=True,
        )

        self.client.force_authenticate(user=self.user)
        self.url = reverse("suggestions-list")

    def test_suggested_matches_list_includes_photos_array(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIn("photos", response.data[0])
        self.assertEqual(len(response.data[0]["photos"]), 1)
        self.assertTrue(response.data[0]["photos"][0]["image"].endswith("candidate.jpg"))
        self.assertTrue(response.data[0]["photo_blurred"])
