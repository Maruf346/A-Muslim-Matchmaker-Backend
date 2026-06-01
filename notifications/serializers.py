from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):

    """
    Used by client, artisan, and admin REST endpoints.
    websocket_pushed / websocket_success are included so the admin
    frontend can surface delivery-status info if needed.
    """

    class Meta:
        model  = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "body",
            "data",
            "priority",
            "is_read",
            "read_at",
            "websocket_pushed",
            "websocket_success",
            "created_at",
        ]
        read_only_fields = fields