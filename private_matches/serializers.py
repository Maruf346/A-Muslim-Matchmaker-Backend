"""
private_matches/serializers.py
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from questions.models import FemaleBasicInfo, MaleBasicInfo, WaliBasicInfo
from users.models import UserRole
from .models import PrivateMatchSuggestion, SuggestionStatus


def _basic_info(user):
    if user.role == UserRole.MALE:
        return MaleBasicInfo.objects.filter(user=user).first()
    if user.role == UserRole.FEMALE:
        return FemaleBasicInfo.objects.filter(user=user).first()
    if user.role == UserRole.WALI:
        return WaliBasicInfo.objects.filter(user=user).first()
    return None


def _user_card(user, request) -> dict:
    info = _basic_info(user)
    return {
        "id":              str(user.id),
        "codename":        user.codename,
        "first_name":      user.first_name,
        "last_name":       user.last_name,
        "role":            user.role,
        "gender":          user.gender,
        "profile_picture": request.build_absolute_uri(user.profile_picture.url)
                           if user.profile_picture and request else None,
        "city":            getattr(info, "city", None),
        "country":         getattr(info, "country", None),
        "sect":            getattr(info, "sect", None),
        "age":             getattr(info, "age", None),
    }


class PrivateMatchUserCardSerializer(serializers.Serializer):
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
    age = serializers.IntegerField(allow_null=True)


class ReviewedBySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    codename = serializers.CharField()


# ── Client-side (private client sees their suggestions) ───────────────────────

class ClientSuggestionSerializer(serializers.ModelSerializer):
    """
    What the private client sees: prospect profile + status.
    Feedback field is write-only (sent when declining).
    """
    prospect = serializers.SerializerMethodField()

    class Meta:
        model  = PrivateMatchSuggestion
        fields = [
            "id", "prospect", "status",
            "client_responded_at", "prospect_responded_at",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(PrivateMatchUserCardSerializer)
    def get_prospect(self, obj) -> dict:
        return _user_card(obj.prospect, self.context.get("request"))


class ClientRespondSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()
    feedback = serializers.CharField(required=False, allow_blank=True,
        help_text="Only used when accepted=false.")


# ── Prospect-side (prospect sees their special match) ─────────────────────────

class ProspectSpecialMatchSerializer(serializers.ModelSerializer):
    """What the prospect sees when they receive a Special Match."""
    private_client = serializers.SerializerMethodField()

    class Meta:
        model  = PrivateMatchSuggestion
        fields = ["id", "private_client", "status", "created_at"]
        read_only_fields = fields

    @extend_schema_field(PrivateMatchUserCardSerializer)
    def get_private_client(self, obj) -> dict:
        return _user_card(obj.private_client, self.context.get("request"))


class ProspectRespondSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()


# ── Admin-side ────────────────────────────────────────────────────────────────

class CreateSuggestionSerializer(serializers.Serializer):
    private_client_id = serializers.UUIDField()
    prospect_id       = serializers.UUIDField()

    def validate(self, data):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        for field in ("private_client_id", "prospect_id"):
            try:
                User.objects.get(id=data[field])
            except User.DoesNotExist:
                raise serializers.ValidationError({field: "User not found."})
        return data


class AdminSuggestionListSerializer(serializers.ModelSerializer):
    private_client = serializers.SerializerMethodField()
    prospect       = serializers.SerializerMethodField()

    class Meta:
        model  = PrivateMatchSuggestion
        fields = [
            "id", "private_client", "prospect", "status",
            "client_feedback",
            "client_responded_at", "prospect_responded_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(PrivateMatchUserCardSerializer)
    def get_private_client(self, obj) -> dict:
        return _user_card(obj.private_client, self.context.get("request"))

    @extend_schema_field(PrivateMatchUserCardSerializer)
    def get_prospect(self, obj) -> dict:
        return _user_card(obj.prospect, self.context.get("request"))


class AdminProspectDirectorySerializer(serializers.Serializer):
    """
    Used when matchmaker is browsing to pick a prospect for a private client.
    Gender-filtered user list — reuses _user_card.
    """
    id              = serializers.UUIDField()
    codename        = serializers.CharField()
    first_name      = serializers.CharField()
    last_name       = serializers.CharField()
    role            = serializers.CharField()
    gender          = serializers.CharField(allow_null=True)
    profile_picture = serializers.CharField(allow_null=True)
    city            = serializers.CharField(allow_null=True)
    country         = serializers.CharField(allow_null=True)
    sect            = serializers.CharField(allow_null=True)
    age             = serializers.IntegerField(allow_null=True)
    is_private_matchmaking_client = serializers.BooleanField()
