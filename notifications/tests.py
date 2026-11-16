from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import DeviceToken, NotificationType
from .push import build_message, send_to_user
from .services import NotificationService

User = get_user_model()

DEVICES_URL = "/api/notification/devices/"
LOCMEM_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM_CACHE)
class DeviceTokenApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="a@example.com", password="pw-123456", role="male")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_register_and_update_token(self):
        r = self.client.post(DEVICES_URL, {"token": "tok-1", "platform": "ios"}, format="json")
        self.assertEqual(r.status_code, 200)
        r = self.client.post(DEVICES_URL, {"token": "tok-1", "platform": "android"}, format="json")
        self.assertEqual(r.status_code, 200)
        device = DeviceToken.objects.get(token="tok-1")
        self.assertEqual(device.user, self.user)
        self.assertEqual(device.platform, "android")
        self.assertEqual(DeviceToken.objects.count(), 1)

    def test_register_requires_platform(self):
        r = self.client.post(DEVICES_URL, {"token": "tok-1"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_token_moves_to_new_login_on_same_phone(self):
        self.client.post(DEVICES_URL, {"token": "shared", "platform": "ios"}, format="json")
        other = User.objects.create_user(email="b@example.com", password="pw-123456", role="female")
        self.client.force_authenticate(other)
        self.client.post(DEVICES_URL, {"token": "shared", "platform": "ios"}, format="json")
        self.assertEqual(DeviceToken.objects.get(token="shared").user, other)

    def test_delete_only_removes_own_token(self):
        other = User.objects.create_user(email="b@example.com", password="pw-123456", role="female")
        DeviceToken.objects.create(user=other, token="theirs", platform="ios")
        DeviceToken.objects.create(user=self.user, token="mine", platform="ios")
        self.client.delete(DEVICES_URL, {"token": "theirs"}, format="json")
        self.client.delete(DEVICES_URL, {"token": "mine"}, format="json")
        self.assertTrue(DeviceToken.objects.filter(token="theirs").exists())
        self.assertFalse(DeviceToken.objects.filter(token="mine").exists())

    def test_requires_login(self):
        r = APIClient().post(DEVICES_URL, {"token": "x", "platform": "ios"}, format="json")
        self.assertEqual(r.status_code, 401)


class PushQueueTests(TestCase):
    def _send(self, user):
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.MATCH_CREATED,
            title="t",
            body="b",
            data={"match_id": "m1"},
        )

    @override_settings(FCM_ENABLED=True)
    def test_app_user_notification_queues_push(self):
        user = User.objects.create_user(email="a@example.com", password="pw", role="male")
        with mock.patch("notifications.tasks.send_push.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                notification = self._send(user)
        delay.assert_called_once_with(str(notification.id))

    @override_settings(FCM_ENABLED=False)
    def test_no_push_when_disabled(self):
        user = User.objects.create_user(email="a@example.com", password="pw", role="male")
        with mock.patch("notifications.tasks.send_push.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                self._send(user)
        delay.assert_not_called()

    @override_settings(FCM_ENABLED=True)
    def test_admin_gets_no_mobile_push(self):
        admin = User.objects.create_user(email="m@example.com", password="pw", role="matchmaker")
        with mock.patch("notifications.tasks.send_push.delay") as delay, \
             mock.patch("notifications.services.NotificationService._push_websocket", return_value=True):
            with self.captureOnCommitCallbacks(execute=True):
                self._send(admin)
        delay.assert_not_called()


class PushSendTests(TestCase):
    def test_message_data_values_are_strings(self):
        msg = build_message("tok", "Title", "Body", {"match_id": 5, "x": None})["message"]
        self.assertEqual(msg["data"], {"match_id": "5", "x": ""})
        self.assertEqual(msg["token"], "tok")
        self.assertEqual(msg["notification"], {"title": "Title", "body": "Body"})

    def test_dead_tokens_are_deleted(self):
        user = User.objects.create_user(email="a@example.com", password="pw", role="male")
        DeviceToken.objects.create(user=user, token="good", platform="ios")
        DeviceToken.objects.create(user=user, token="dead", platform="android")
        results = {"good": "ok", "dead": "dead"}
        with mock.patch("notifications.push.send_to_token", side_effect=lambda t, *a: results[t]):
            sent = send_to_user(user, "t", "b", {})
        self.assertEqual(sent, 1)
        self.assertEqual(list(DeviceToken.objects.values_list("token", flat=True)), ["good"])
