"""
matches/serializers.py

Organized by concern:
    1. Directory / browse — public-safe profile listing (opposite gender)
    2. Connection requests — send, list sent/received, respond
    3. Matches — list/detail with visibility-aware nested profile
    4. Photo request actions
    5. Wali request actions
    6. Admin — match list/detail, status override
"""

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field

from questions.models import FemaleBasicInfo, MaleBasicInfo, UserPhoto, WaliBasicInfo
from questions.serializers import (
    FemaleBasicInfoSerializer,
    MaleBasicInfoSerializer,
    UserPhotoSerializer,
    WaliBasicInfoSerializer,
)
from users.models import UserRole

from .models import *
from .services import SubscriptionLimitService


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _last_active_display(user) -> str | None:
    if not user.last_active:
        return None
    from django.utils import timezone
    delta   = timezone.now() - user.last_active
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "Active now"
    if seconds < 3600:
        return f"Active {seconds // 60} min(s) ago"
    if seconds < 86400:
        return f"Active {seconds // 3600} hr(s) ago"
    return f"Active {seconds // 86400} day(s) ago"


def _get_basic_info(user):
    """Return the relevant basic info object for a user, or None."""
    try:
        if user.role == UserRole.MALE:
            return getattr(user, "male_basic_info", None) or MaleBasicInfo.objects.filter(user=user).first()
        if user.role == UserRole.FEMALE:
            return getattr(user, "female_basic_info", None) or FemaleBasicInfo.objects.filter(user=user).first()
        if user.role == UserRole.WALI:
            return getattr(user, "wali_basic_info", None) or WaliBasicInfo.objects.filter(user=user).first()
    except ObjectDoesNotExist:
        return None
    return None


def _get_basic_info_serializer(instance, context):
    if isinstance(instance, MaleBasicInfo):
        return MaleBasicInfoSerializer(instance, context=context)
    if isinstance(instance, FemaleBasicInfo):
        return FemaleBasicInfoSerializer(instance, context=context)
    if isinstance(instance, WaliBasicInfo):
        return WaliBasicInfoSerializer(instance, context=context)
    return None


def _get_directory_first_name(user) -> str | None:
    info = _get_basic_info(user)
    if user.role == UserRole.WALI and info:
        return getattr(info, "sister_first_name", None) or user.first_name
    return user.first_name


def _get_directory_last_name(user) -> str | None:
    info = _get_basic_info(user)
    if user.role == UserRole.WALI and info:
        return getattr(info, "sister_last_name", None) or user.last_name
    return user.last_name


def _get_display_name(user, has_mutual_interest: bool) -> str:
    """
    Returns the display name for a user.
    Before mutual interest: codename.
    After mutual interest: full_name (or sister's name for Wali-managed profiles).
    """
    if not has_mutual_interest:
        return user.codename

    if user.role == UserRole.WALI:
        info = WaliBasicInfo.objects.filter(user=user).first()
        if info and (info.sister_first_name or info.sister_last_name):
            return f"{info.sister_first_name or ''} {info.sister_last_name or ''}".strip()

    return user.full_name


def _get_primary_photo_url(user, request) -> str | None:
    photo = UserPhoto.objects.filter(user=user, is_primary=True).first()
    if not photo:
        photo = UserPhoto.objects.filter(user=user).first()
    if not photo or not photo.image:
        return None
    if request:
        return request.build_absolute_uri(photo.image.url)
    return photo.image.url


class AdminMatchProfileSerializer(serializers.Serializer):
    """Compact admin-facing summary for a match participant."""
    id = serializers.UUIDField()
    codename = serializers.CharField()
    full_name = serializers.CharField()
    gender = serializers.CharField(allow_null=True, required=False)
    phone = serializers.CharField(allow_null=True, required=False)
    profile_picture = serializers.CharField(allow_null=True, required=False)


# ─────────────────────────────────────────────────────────────────────────────
# 1. DIRECTORY / BROWSE
# ─────────────────────────────────────────────────────────────────────────────

class DirectoryProfileSerializer(serializers.Serializer):
    """
    Profile card shown when browsing the directory (opposite gender).
    Photos are always blurred/hidden in directory view (no mutual interest yet).

    Fields are pulled from User + the relevant BasicInfo model.
    For Wali-managed profiles, sister's data is shown (display name remains
    codename until mutual interest, per business rule).
    """
    id                    = serializers.UUIDField()
    codename              = serializers.CharField()
    first_name            = serializers.SerializerMethodField()
    last_name             = serializers.SerializerMethodField()
    role                  = serializers.CharField()
    gender                = serializers.CharField()
    subscription_plan     = serializers.CharField()
    last_active           = serializers.DateTimeField(allow_null=True)
    last_active_display   = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    age                   = serializers.SerializerMethodField()
    city                  = serializers.SerializerMethodField()
    country               = serializers.SerializerMethodField()
    sect                  = serializers.SerializerMethodField()
    marital_status        = serializers.SerializerMethodField()
    height                = serializers.SerializerMethodField()
    photos                = serializers.SerializerMethodField()
    has_boosted_profile   = serializers.BooleanField()
    photo_blurred         = serializers.SerializerMethodField()

    def get_last_active_display(self, obj) -> str | None:
        return _last_active_display(obj)

    def get_first_name(self, obj) -> str | None:
        return _get_directory_first_name(obj)

    def get_last_name(self, obj) -> str | None:
        return _get_directory_last_name(obj)

    def get_completion_percentage(self, obj) -> int:
        info = _get_basic_info(obj)
        return info.completion_percentage if info else 0

    def get_age(self, obj) -> int | None:
        info = _get_basic_info(obj)
        return info.age if info else None

    def get_city(self, obj) -> str | None:
        info = _get_basic_info(obj)
        return getattr(info, "city", None) if info else None

    def get_country(self, obj) -> str | None:
        info = _get_basic_info(obj)
        return getattr(info, "country", None) if info else None

    def get_sect(self, obj) -> str | None:
        info = _get_basic_info(obj)
        return getattr(info, "sect", None) if info else None

    def get_marital_status(self, obj) -> str | None:
        info = _get_basic_info(obj)
        return getattr(info, "marital_status", None) if info else None

    def get_height(self, obj) -> str | None:
        info = _get_basic_info(obj)
        return getattr(info, "height", None) if info else None

    def get_photos(self, obj) -> list:
        photos = UserPhoto.objects.filter(user=obj)
        return UserPhotoSerializer(photos, many=True, context=self.context).data

    def get_photo_blurred(self, obj) -> bool:
        """Always True in directory view — no mutual interest established."""
        return True


class DirectoryProfileDetailProfileSerializer(DirectoryProfileSerializer):
    def get_fields(self):
        fields = super().get_fields()
        fields.pop("photos", None)
        return fields


class DirectoryProfileDetailSerializer(serializers.Serializer):
    profile = serializers.SerializerMethodField()
    basic_info = serializers.SerializerMethodField()

    @extend_schema_field(DirectoryProfileDetailProfileSerializer)
    def get_profile(self, obj) -> dict:
        return DirectoryProfileDetailProfileSerializer(obj, context=self.context).data

    @extend_schema_field(
        PolymorphicProxySerializer(
            component_name="DirectoryBasicInfo",
            serializers=[
                MaleBasicInfoSerializer,
                FemaleBasicInfoSerializer,
                WaliBasicInfoSerializer,
            ],
            resource_type_field_name=None,
        )
    )
    def get_basic_info(self, obj) -> dict | None:
        info = _get_basic_info(obj)
        if not info:
            return None
        serializer = _get_basic_info_serializer(info, self.context)
        return serializer.data if serializer else None


# ─────────────────────────────────────────────────────────────────────────────
# 2. CONNECTION REQUESTS
# ─────────────────────────────────────────────────────────────────────────────

class SendConnectionRequestSerializer(serializers.Serializer):
    """Male sends a connection request to a Female/Wali by their User UUID."""
    target_user_id = serializers.UUIDField()

    def validate_target_user_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            target = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Target user not found.")

        if target.role not in (UserRole.FEMALE, UserRole.WALI):
            raise serializers.ValidationError("Connection requests can only be sent to Female or Wali profiles.")

        if target.is_private_matchmaking_client: 
            raise ValidationError("Not available.")
        
        request = self.context.get("request")
        if request and target == request.user:
            raise serializers.ValidationError("You cannot send a connection request to yourself.")

        if request:
            from wishlists.services import VisibilityService
            if not VisibilityService.can_view_profile(request.user, target):
                raise serializers.ValidationError("Target user not found.")

        return value


class ConnectionRequestListSerializer(serializers.ModelSerializer):
    """
    Used for listing sent/received connection requests (PENDING status).
    Shows the OTHER party's directory-style profile.
    """
    other_user = serializers.SerializerMethodField()

    class Meta:
        model  = Match
        fields = ["id", "match_id", "status", "other_user", "requested_at"]
        read_only_fields = fields

    def get_other_user(self, obj) -> dict:
        request     = self.context.get("request")
        viewer      = request.user if request else None
        other_user  = obj.other_party(viewer) if viewer else obj.other_user
        return DirectoryProfileSerializer(other_user, context=self.context).data


# ─────────────────────────────────────────────────────────────────────────────
# 3. MATCH DETAIL  (visibility-aware)
# ─────────────────────────────────────────────────────────────────────────────

class MatchedProfileSerializer(serializers.Serializer):
    """
    Profile representation of the OTHER party in a Match, with visibility
    rules applied based on match.is_mutual and photo state.

    Visibility rules:
        - codename: always visible
        - full_name / display_name: visible only if is_mutual
        - photos: visible only if photos_currently_visible=True
        - contact details (phone): visible only if is_mutual
        - wali details: visible only if match.wali_details_visible
    """
    id                    = serializers.UUIDField()
    codename              = serializers.CharField()
    display_name          = serializers.SerializerMethodField()
    role                  = serializers.CharField()
    gender                = serializers.CharField()
    last_active_display   = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    age                   = serializers.SerializerMethodField()
    city                  = serializers.SerializerMethodField()
    country               = serializers.SerializerMethodField()
    photos                = serializers.SerializerMethodField()
    photo_blurred         = serializers.SerializerMethodField()
    phone                 = serializers.SerializerMethodField()
    wali_details          = serializers.SerializerMethodField()

    def _match(self) -> Match:
        return self.context["match"]

    def get_display_name(self, obj) -> str:
        match = self._match()
        return _get_display_name(obj, match.is_mutual)

    def get_last_active_display(self, obj) -> str | None:
        return _last_active_display(obj)

    def get_completion_percentage(self, obj) -> int:
        info = _get_basic_info(obj)
        return info.completion_percentage if info else 0

    def get_age(self, obj) -> int | None:
        info = _get_basic_info(obj)
        return info.age if info else None

    def get_city(self, obj) -> str | None:
        info = _get_basic_info(obj)
        return getattr(info, "city", None) if info else None

    def get_country(self, obj) -> str | None:
        info = _get_basic_info(obj)
        return getattr(info, "country", None) if info else None

    def get_photo_blurred(self, obj) -> bool:
        match = self._match()
        return not match.photos_currently_visible

    def get_photos(self, obj) -> list:
        match = self._match()
        if not match.photos_currently_visible:
            return []
        photos = UserPhoto.objects.filter(user=obj)
        return UserPhotoSerializer(photos, many=True, context=self.context).data

    def get_phone(self, obj) -> str | None:
        """Phone visible only after mutual interest."""
        match = self._match()
        if not match.is_mutual:
            return None
        info = _get_basic_info(obj)
        return getattr(info, "phone", None) if info else None

    def get_wali_details(self, obj) -> dict | None:
        """
        Wali details visible only when match.wali_details_visible is True.
        Returns wali_name / wali_relation / wali_number from the female's
        FemaleBasicInfo, or — if obj is a Wali user — their own WaliProfile info.
        """
        match = self._match()
        if not match.wali_details_visible:
            return None

        if obj.role == UserRole.FEMALE:
            info = FemaleBasicInfo.objects.filter(user=obj).first()
            if info:
                return {
                    "wali_name":     info.wali_name,
                    "wali_relation": info.wali_relation,
                    "wali_number":   info.wali_number,
                }
        elif obj.role == UserRole.WALI:
            from questions.models import WaliProfile
            wali_profile = WaliProfile.objects.filter(user=obj).first()
            if wali_profile:
                return {
                    "wali_name":     obj.full_name,
                    "wali_relation": wali_profile.relation_to_sister,
                    "wali_number":   wali_profile.phone,
                }
        return None


class MatchDetailSerializer(serializers.ModelSerializer):
    """
    Full match detail from the perspective of the requesting user.
    Includes the other party's profile (visibility-aware) and all
    status/timestamp fields relevant to the match lifecycle.
    """
    other_user           = serializers.SerializerMethodField()
    is_mutual            = serializers.BooleanField(read_only=True)
    wali_details_visible = serializers.BooleanField(read_only=True)

    class Meta:
        model  = Match
        fields = [
            "id", "match_id", "status",
            "other_user",
            "is_mutual",
            "cancelled_by", "cancelled_at",
            "dropped_by", "dropped_at",
            "photo_request_status", "photos_currently_visible",
            "photos_revealed_count",
            "first_photos_revealed_at", "last_photos_revealed_at",
            "wali_request_status", "wali_details_visible",
            "wali_requested_at", "wali_responded_at",
            "requested_at", "responded_at", "accepted_at",
            "in_discussion_at", "married_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_other_user(self, obj) -> dict:
        request    = self.context.get("request")
        viewer     = request.user if request else None
        other_user = obj.other_party(viewer) if viewer else obj.other_user
        ctx = {**self.context, "match": obj}
        return MatchedProfileSerializer(other_user, context=ctx).data


class MatchListSerializer(serializers.ModelSerializer):
    """Compact representation for listing matches (lighter than detail)."""
    other_user = serializers.SerializerMethodField()
    photo_requested_by_other_user = serializers.SerializerMethodField()

    class Meta:
        model  = Match
        fields = [
            "id", "match_id", "status",
            "other_user",
            "photo_request_status",
            "photo_requested_by_other_user",
            "photos_currently_visible",
            "wali_request_status",
            "accepted_at", "updated_at",
        ]
        read_only_fields = fields

    def get_other_user(self, obj) -> dict:
        request    = self.context.get("request")
        viewer     = request.user if request else None
        other_user = obj.other_party(viewer) if viewer else obj.other_user
        ctx = {**self.context, "match": obj}
        return MatchedProfileSerializer(other_user, context=ctx).data

    def get_photo_requested_by_other_user(self, obj) -> bool:
        request = self.context.get("request")
        viewer = request.user if request else None
        if not viewer or obj.photo_request_status != PhotoRequestStatus.REQUESTED:
            return False
        return obj.photo_requested_by_id is not None and obj.photo_requested_by_id != viewer.id


# ─────────────────────────────────────────────────────────────────────────────
# 4. ACTION SERIALIZERS  (no-payload actions use empty serializers for schema)
# ─────────────────────────────────────────────────────────────────────────────

class EmptyActionSerializer(serializers.Serializer):
    """Placeholder serializer for actions that take no request body."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# 5. SUBSCRIPTION USAGE
# ─────────────────────────────────────────────────────────────────────────────

class ConnectionUsageSerializer(serializers.Serializer):
    """Returned by GET /matches/usage/ — shows remaining connection requests."""
    subscription_plan  = serializers.CharField()
    requests_sent      = serializers.IntegerField()
    requests_remaining = serializers.IntegerField(allow_null=True)
    monthly_limit      = serializers.IntegerField(allow_null=True)
    cycle_start        = serializers.DateTimeField()


# ─────────────────────────────────────────────────────────────────────────────
# 6. ADMIN
# ─────────────────────────────────────────────────────────────────────────────

class AdminMatchListSerializer(serializers.ModelSerializer):
    """
    Admin dashboard match list.
    Fields: Match ID, Groom, Bride, Created Date, Photos, Status.
    """
    groom  = serializers.SerializerMethodField()
    bride  = serializers.SerializerMethodField()
    photos_revealed = serializers.SerializerMethodField()
    total_matches = serializers.SerializerMethodField()
    in_discussion_count = serializers.SerializerMethodField()
    married_count = serializers.SerializerMethodField()
    dropped_count = serializers.SerializerMethodField()

    class Meta:
        model  = Match
        fields = [
            "id", "match_id", "status",
            "groom", "bride",
            "photos_revealed", "photos_revealed_count",
            "total_matches", "in_discussion_count", "married_count", "dropped_count",
            "wali_request_status",
            "requested_at", "accepted_at", "married_at", "dropped_at",
            "created_at",
        ]
        read_only_fields = fields

    def _profile_summary(self, user) -> dict:
        request = self.context.get("request")
        info = _get_basic_info(user)
        return {
            "id":         str(user.id),
            "codename":   user.codename,
            "full_name":  _get_display_name(user, has_mutual_interest=True),
            "gender":     user.gender,
            "phone":      getattr(info, "phone", None) if info else None,
            "profile_picture": _get_primary_photo_url(user, request),
        }

    @extend_schema_field(AdminMatchProfileSerializer)
    def get_groom(self, obj) -> dict:
        return self._profile_summary(obj.male_user)

    @extend_schema_field(AdminMatchProfileSerializer)
    def get_bride(self, obj) -> dict:
        return self._profile_summary(obj.other_user)

    def get_photos_revealed(self, obj) -> bool:
        return obj.photos_revealed_count > 0

    def _counters(self) -> dict:
        return self.context.get("match_counters", {})

    def get_total_matches(self, obj) -> int:
        return self._counters().get("total_matches", 0)

    def get_in_discussion_count(self, obj) -> int:
        return self._counters().get("in_discussion_count", 0)

    def get_married_count(self, obj) -> int:
        return self._counters().get("married_count", 0)

    def get_dropped_count(self, obj) -> int:
        return self._counters().get("dropped_count", 0)


class AdminMatchDetailSerializer(AdminMatchListSerializer):
    """Extended admin detail view — includes all timestamps and tracking fields."""

    class Meta(AdminMatchListSerializer.Meta):
        fields = AdminMatchListSerializer.Meta.fields + [
            "cancelled_by", "cancelled_at",
            "dropped_by", "dropped_at",
            "photo_request_status",
            "first_photos_revealed_at", "last_photos_revealed_at",
            "wali_requested_at", "wali_responded_at",
            "in_discussion_at",
            "last_status_changed_by_admin",
            "updated_at",
        ]
        read_only_fields = fields


class AdminMatchStatusOverrideSerializer(serializers.Serializer):
    """Admin overrides a match's status to any value, including MARRIED/DROPPED."""
    status = serializers.ChoiceField(choices=MatchStatus.choices)
