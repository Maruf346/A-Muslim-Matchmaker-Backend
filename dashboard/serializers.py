from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import RecentActivity


class ActivityUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(allow_null=True)
    codename = serializers.CharField(allow_null=True)
    full_name = serializers.CharField(allow_blank=True)


class RecentActivitySerializer(serializers.ModelSerializer):
    primary_user = serializers.SerializerMethodField()
    secondary_user = serializers.SerializerMethodField()
    actor_user = serializers.SerializerMethodField()
    activity_time_display = serializers.SerializerMethodField()

    class Meta:
        model = RecentActivity
        fields = [
            "id",
            "activity_type",
            "title",
            "description",
            "primary_user",
            "secondary_user",
            "actor_user",
            "metadata",
            "created_at",
            "activity_time_display",
        ]
        read_only_fields = fields

    @extend_schema_field(ActivityUserSerializer)
    def get_primary_user(self, obj) -> dict | None:
        return self._user_payload(obj.primary_user, obj.primary_user_name)

    @extend_schema_field(ActivityUserSerializer)
    def get_secondary_user(self, obj) -> dict | None:
        return self._user_payload(obj.secondary_user, obj.secondary_user_name)

    @extend_schema_field(ActivityUserSerializer)
    def get_actor_user(self, obj) -> dict | None:
        return self._user_payload(obj.actor_user, obj.actor_user_name)

    @staticmethod
    def _user_payload(user, snapshot_name: str) -> dict | None:
        if not user and not snapshot_name:
            return None
        return {
            "id": str(user.id) if user else None,
            "codename": getattr(user, "codename", None) if user else None,
            "full_name": snapshot_name or "",
        }

    def get_activity_time_display(self, obj) -> str:
        from django.utils import timezone

        delta = timezone.now() - obj.created_at
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} min{'s' if minutes != 1 else ''} ago"
        if seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"


class MatchesOverTimeItemSerializer(serializers.Serializer):
    month = serializers.CharField()
    matches = serializers.IntegerField()


class DashboardStatsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    total_matches = serializers.IntegerField()
    pending_matchmaking_requests = serializers.IntegerField()
    total_married_count = serializers.IntegerField()
    matches_over_time = MatchesOverTimeItemSerializer(many=True)


class DashboardAnalyticsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_matches = serializers.IntegerField()
    success_rate = serializers.FloatField()
    conversion_rate = serializers.FloatField()


class UserGrowthItemSerializer(serializers.Serializer):
    month = serializers.CharField()
    users = serializers.IntegerField()


class UserGrowthSerializer(serializers.Serializer):
    user_over_time = UserGrowthItemSerializer(many=True)


class OutcomesSerializer(serializers.Serializer):
    successful = serializers.FloatField()
    in_progress = serializers.FloatField()
    dropped = serializers.FloatField()
    cancelled = serializers.FloatField()


class FunnelItemSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()


class FunnelSerializer(serializers.Serializer):
    funnel = FunnelItemSerializer(many=True)


class DashboardSummarySerializer(serializers.Serializer):
    active_matches = serializers.IntegerField()
    avg_time_to_match = serializers.CharField(allow_blank=True)
    avg_time_to_marriage = serializers.CharField(allow_blank=True)
    most_successful_month = serializers.CharField(allow_blank=True)
