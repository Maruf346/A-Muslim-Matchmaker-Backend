"""
matchmaking/serializers.py
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import PrivateMatchmakingRequest, RequestStatus


class AdminRequestUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    codename = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()
    gender = serializers.CharField(allow_null=True)
    profile_picture = serializers.CharField(allow_null=True)
    city = serializers.CharField(allow_null=True)
    country = serializers.CharField(allow_null=True)
    sect = serializers.CharField(allow_null=True)
    marital_status = serializers.CharField(allow_null=True)


class AdminRequestReviewerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    codename = serializers.CharField()


class SubmitRequestSerializer(serializers.Serializer):
    """No fields needed — user just taps 'Request Private Matchmaking'."""
    pass


class PrivateMatchmakingRequestSerializer(serializers.ModelSerializer):
    """User-facing view of their own request."""
    user_codename = serializers.CharField(source="user.codename", read_only=True)

    class Meta:
        model  = PrivateMatchmakingRequest
        fields = [
            "id", "request_id", "user_codename", "status",
            "admin_notes", "created_at", "updated_at",
        ]
        read_only_fields = fields


class AdminRequestListSerializer(serializers.ModelSerializer):
    """Admin inbox — compact list."""
    user = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()
    approved_count = serializers.SerializerMethodField()
    declined_count = serializers.SerializerMethodField()

    class Meta:
        model  = PrivateMatchmakingRequest
        fields = [
            "id", "request_id", "user", "status",
            "pending_count", "approved_count", "declined_count",
            "reviewed_at", "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(AdminRequestUserSerializer)
    def get_user(self, obj) -> dict:
        u = obj.user
        info = self._get_basic_info(u)
        request = self.context.get("request")
        return {
            "id":              str(u.id),
            "codename":        u.codename,
            "first_name":      u.first_name,
            "last_name":       u.last_name,
            "role":            u.role,
            "gender":          u.gender,
            "profile_picture": request.build_absolute_uri(u.profile_picture.url)
                               if u.profile_picture and request else None,
            "city":            getattr(info, "city", None),
            "country":         getattr(info, "country", None),
            "sect":            getattr(info, "sect", None),
            "marital_status":  getattr(info, "marital_status", None),
        }

    def _counters(self) -> dict:
        return self.context.get("request_counters", {})

    def get_pending_count(self, obj) -> int:
        return self._counters().get("pending_count", 0)

    def get_approved_count(self, obj) -> int:
        return self._counters().get("approved_count", 0)

    def get_declined_count(self, obj) -> int:
        return self._counters().get("declined_count", 0)

    @staticmethod
    def _get_basic_info(user):
        from users.models import UserRole
        from questions.models import MaleBasicInfo, FemaleBasicInfo, WaliBasicInfo
        if user.role == UserRole.MALE:
            return MaleBasicInfo.objects.filter(user=user).first()
        if user.role == UserRole.FEMALE:
            return FemaleBasicInfo.objects.filter(user=user).first()
        if user.role == UserRole.WALI:
            return WaliBasicInfo.objects.filter(user=user).first()
        return None


class AdminRequestDetailSerializer(AdminRequestListSerializer):
    """Admin detail — same as list but includes admin_notes and reviewer info."""
    reviewed_by = serializers.SerializerMethodField()

    class Meta(AdminRequestListSerializer.Meta):
        fields = AdminRequestListSerializer.Meta.fields + [
            "admin_notes", "reviewed_by", "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(AdminRequestReviewerSerializer)
    def get_reviewed_by(self, obj) -> dict | None:
        if not obj.reviewed_by:
            return None
        return {"id": str(obj.reviewed_by.id), "codename": obj.reviewed_by.codename}


class AdminReviewSerializer(serializers.Serializer):
    """Admin approves or declines a request."""
    action     = serializers.ChoiceField(choices=["approve", "decline"])
    admin_notes = serializers.CharField(required=False, allow_blank=True)
