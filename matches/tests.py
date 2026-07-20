import shutil
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from matches.models import Match, MatchStatus
from questions.models import FemaleBasicInfo, MaleBasicInfo, UserPhoto, WaliBasicInfo
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
        self.assertIn("/media/users/photos/", response.data[0]["photos"][0]["image"])
        self.assertTrue(response.data[0]["photo_blurred"])

    def test_suggested_matches_list_excludes_already_matched_profiles(self):
        Match.objects.create(
            male_user=self.user,
            other_user=self.candidate,
            initiated_by=self.user,
            status=MatchStatus.ACCEPTED,
            match_id="MT-TEST-1",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "matches-tests",
        }
    }
)
class MatchListRoutingAndWaliDisplayTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.male_user = User.objects.create_user(
            email="match-male@example.com",
            password="testpass123",
            first_name="Match",
            last_name="Brother",
            role=UserRole.MALE,
            gender=Gender.MALE,
            subscription_plan="monthly",
            is_active=True,
        )
        self.wali_user = User.objects.create_user(
            email="wali@example.com",
            password="testpass123",
            first_name="Guardian",
            last_name="User",
            role=UserRole.WALI,
            subscription_plan="free",
            is_active=True,
        )

        WaliBasicInfo.objects.create(
            user=self.wali_user,
            sister_first_name="Amina",
            sister_last_name="Rahman",
            date_of_birth=date(1997, 1, 1),
            city="Dhaka",
            country="Bangladesh",
        )
        Match.objects.create(
            male_user=self.male_user,
            other_user=self.wali_user,
            initiated_by=self.male_user,
            status=MatchStatus.ACCEPTED,
            match_id="MT-WALI-1",
        )

        self.client.force_authenticate(user=self.male_user)
        self.url = reverse("match-list")

    def test_matches_root_returns_match_list_instead_of_admin_router_root(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)

    def test_wali_match_returns_sister_display_name(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["other_user"]["display_name"], "Amina Rahman")
        self.assertEqual(response.data[0]["other_user"]["city"], "Dhaka")


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "matches-tests",
        }
    },
    MEDIA_ROOT=TEST_MEDIA_ROOT,
)
class MatchListPhotosTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.male_user = User.objects.create_user(
            email="photos-male@example.com",
            password="testpass123",
            first_name="Photo",
            last_name="Brother",
            role=UserRole.MALE,
            gender=Gender.MALE,
            subscription_plan="monthly",
            is_active=True,
        )
        self.female_user = User.objects.create_user(
            email="photos-female@example.com",
            password="testpass123",
            first_name="Photo",
            last_name="Sister",
            role=UserRole.FEMALE,
            gender=Gender.FEMALE,
            subscription_plan="monthly",
            is_active=True,
        )
        FemaleBasicInfo.objects.create(
            user=self.female_user,
            date_of_birth=date(1996, 1, 1),
            pref_age_min=28,
            pref_age_max=38,
        )
        MaleBasicInfo.objects.create(
            user=self.male_user,
            date_of_birth=date(1991, 1, 1),
            pref_age_min=24,
            pref_age_max=34,
        )
        UserPhoto.objects.create(
            user=self.male_user,
            image=SimpleUploadedFile(
                "match-photo.jpg",
                b"filecontent",
                content_type="image/jpeg",
            ),
            is_primary=True,
        )
        self.url = reverse("match-list")

    def test_match_list_includes_other_user_photos_array_when_visible(self):
        match = Match.objects.create(
            male_user=self.male_user,
            other_user=self.female_user,
            initiated_by=self.male_user,
            status=MatchStatus.ACCEPTED,
            match_id="MT-PHOTO-1",
            photos_currently_visible=True,
            photos_revealed_count=1,
        )

        self.client.force_authenticate(user=self.female_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["id"], str(match.id))
        self.assertIn("photos", response.data[0])
        self.assertEqual(len(response.data[0]["photos"]), 1)
        self.assertIn("photos", response.data[0]["other_user"])
        self.assertEqual(len(response.data[0]["other_user"]["photos"]), 1)
        self.assertFalse(response.data[0]["other_user"]["photo_blurred"])

    def test_female_user_can_see_photo_requested_by_other_user(self):
        Match.objects.create(
            male_user=self.male_user,
            other_user=self.female_user,
            initiated_by=self.male_user,
            status=MatchStatus.ACCEPTED,
            match_id="MT-PHOTO-2",
            photo_request_status="requested",
            photo_requested_by=self.male_user,
            photos_currently_visible=False,
        )

        self.client.force_authenticate(user=self.female_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["photo_request_status"], "requested")
        self.assertTrue(response.data[0]["photo_requested_by_other_user"])
        self.assertEqual(len(response.data[0]["photos"]), 1)
        self.assertEqual(len(response.data[0]["other_user"]["photos"]), 1)
        self.assertTrue(response.data[0]["other_user"]["photo_blurred"])


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "matches-tests",
        }
    }
)
class AdminMatchPaginationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="matchmaker@example.com",
            password="testpass123",
            first_name="Match",
            last_name="Maker",
            role=UserRole.MATCHMAKER,
            is_active=True,
        )
        self.groom = User.objects.create_user(
            email="admin-groom@example.com",
            password="testpass123",
            first_name="Admin",
            last_name="Groom",
            role=UserRole.MALE,
            gender=Gender.MALE,
            subscription_plan="monthly",
            is_active=True,
        )
        self.bride_one = self._create_bride("admin-bride-one@example.com", "Bride", "One")
        self.bride_two = self._create_bride("admin-bride-two@example.com", "Bride", "Two")
        self.bride_three = self._create_bride("admin-bride-three@example.com", "Bride", "Three")

        Match.objects.create(
            male_user=self.groom,
            other_user=self.bride_one,
            initiated_by=self.groom,
            status=MatchStatus.ACCEPTED,
            match_id="MT-ADMIN-1",
        )
        Match.objects.create(
            male_user=self.groom,
            other_user=self.bride_two,
            initiated_by=self.groom,
            status=MatchStatus.PENDING,
            match_id="MT-ADMIN-2",
        )
        Match.objects.create(
            male_user=self.groom,
            other_user=self.bride_three,
            initiated_by=self.groom,
            status=MatchStatus.DROPPED,
            match_id="MT-ADMIN-3",
        )

        self.client.force_authenticate(user=self.admin_user)
        self.url = reverse("admin-matches-list")

    def _create_bride(self, email, first_name, last_name):
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

    def test_admin_matches_list_returns_paginated_response(self):
        response = self.client.get(self.url, {"page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)
        self.assertEqual(response.data["count"], 3)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)
