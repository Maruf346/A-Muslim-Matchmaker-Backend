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


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "admin-users-tests",
        }
    }
)
class AdminUserListTests(APITestCase):
    """Regression: the admin Users page returned 500 when a user had photos
    (the serializer ordered UserPhoto by a non-existent `order` field)."""

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from questions.models import UserPhoto

        self.admin = User.objects.create_user(
            email="admin-list@example.com", password="pw-123456", role=UserRole.SUPERADMIN,
        )
        self.member = User.objects.create_user(
            email="member@example.com", password="pw-123456", role=UserRole.MALE, gender=Gender.MALE,
        )
        gif = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
               b"\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        UserPhoto.objects.create(user=self.member, image=SimpleUploadedFile("a.gif", gif, "image/gif"))
        self.primary = UserPhoto.objects.create(
            user=self.member, is_primary=True, image=SimpleUploadedFile("b.gif", gif, "image/gif"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_admin_user_list_with_photos(self):
        response = self.client.get("/api/user/admin/users/?page=1&page_size=8")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content[:300])
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        member = next(r for r in rows if r["email"] == "member@example.com")
        self.assertEqual(len(member["photos"]), 2)
        self.assertEqual(str(member["photos"][0]["id"]), str(self.primary.id))
        self.assertIn("b", member["profile_picture"].rsplit("/", 1)[-1])
