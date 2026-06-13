"""
wishlists/serializers.py

Organized by concern:
    1. Saved profiles — toggle + list
    2. Profile views — "who viewed me" list
    3. Block / Hide — toggle
    4. Report — create + admin list/detail
"""

from rest_framework import serializers

from matches.serializers import DirectoryProfileSerializer

from .models import BlockedProfile, HiddenProfile, ProfileView, Report, ReportReason, ReportStatus, SavedProfile


# ─────────────────────────────────────────────────────────────────────────────
# 1. Saved Profiles
# ─────────────────────────────────────────────────────────────────────────────

class ToggleTargetSerializer(serializers.Serializer):
    """Generic payload for toggle actions (save, block, hide) — target user UUID."""
    target_user_id = serializers.UUIDField()

    def validate_target_user_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            target = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Target user not found.")

        request = self.context.get("request")
        if request and target == request.user:
            raise serializers.ValidationError("You cannot perform this action on your own profile.")

        return value


class SaveToggleResponseSerializer(serializers.Serializer):
    """Response for the save/unsave toggle endpoint."""
    is_saved = serializers.BooleanField()
    message  = serializers.CharField()


class SavedProfileListSerializer(serializers.ModelSerializer):
    """List of saved/favorited profiles — shows directory-style card for each."""
    profile = serializers.SerializerMethodField()

    class Meta:
        model  = SavedProfile
        fields = ["id", "profile", "created_at"]
        read_only_fields = fields

    def get_profile(self, obj) -> dict:
        return DirectoryProfileSerializer(obj.saved_user, context=self.context).data


# ─────────────────────────────────────────────────────────────────────────────
# 2. Profile Views  ("who viewed me")
# ─────────────────────────────────────────────────────────────────────────────

class ProfileViewListSerializer(serializers.ModelSerializer):
    """
    List of users who viewed the authenticated user's profile.
    Gated by subscription (can_see_viewers) at the view level.
    Shows the most recent view per viewer.
    """
    profile = serializers.SerializerMethodField()

    class Meta:
        model  = ProfileView
        fields = ["id", "profile", "viewed_at"]
        read_only_fields = fields

    def get_profile(self, obj) -> dict:
        return DirectoryProfileSerializer(obj.viewer, context=self.context).data


# ─────────────────────────────────────────────────────────────────────────────
# 3. Block / Hide
# ─────────────────────────────────────────────────────────────────────────────

class BlockToggleResponseSerializer(serializers.Serializer):
    """Response for the block/unblock toggle endpoint."""
    is_blocked = serializers.BooleanField()
    message    = serializers.CharField()


class HideToggleResponseSerializer(serializers.Serializer):
    """Response for the hide/unhide toggle endpoint."""
    is_hidden = serializers.BooleanField()
    message   = serializers.CharField()


class BlockedProfileListSerializer(serializers.ModelSerializer):
    """List of profiles the authenticated user has blocked."""
    profile = serializers.SerializerMethodField()

    class Meta:
        model  = BlockedProfile
        fields = ["id", "profile", "created_at"]
        read_only_fields = fields

    def get_profile(self, obj) -> dict:
        return DirectoryProfileSerializer(obj.blocked, context=self.context).data


class HiddenProfileListSerializer(serializers.ModelSerializer):
    """List of profiles the authenticated user has hidden."""
    profile = serializers.SerializerMethodField()

    class Meta:
        model  = HiddenProfile
        fields = ["id", "profile", "created_at"]
        read_only_fields = fields

    def get_profile(self, obj) -> dict:
        return DirectoryProfileSerializer(obj.hidden_user, context=self.context).data


# ─────────────────────────────────────────────────────────────────────────────
# 4. Report
# ─────────────────────────────────────────────────────────────────────────────

class CreateReportSerializer(serializers.Serializer):
    """Payload for filing a report against a user."""
    target_user_id = serializers.UUIDField()
    reason         = serializers.ChoiceField(choices=ReportReason.choices)
    details        = serializers.CharField(required=False, allow_blank=True)

    def validate_target_user_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            target = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Target user not found.")

        request = self.context.get("request")
        if request and target == request.user:
            raise serializers.ValidationError("You cannot report your own profile.")

        return value


class ReportCreateResponseSerializer(serializers.Serializer):
    """Response after filing a report."""
    id      = serializers.UUIDField()
    message = serializers.CharField()


# ── Admin ──────────────────────────────────────────────────────────────────

class AdminReportListSerializer(serializers.ModelSerializer):
    """Admin dashboard — list of reports with reporter/reported summaries."""
    reporter      = serializers.SerializerMethodField()
    reported_user = serializers.SerializerMethodField()

    class Meta:
        model  = Report
        fields = [
            "id", "reporter", "reported_user",
            "reason", "details", "status",
            "created_at",
        ]
        read_only_fields = fields

    def get_reporter(self, obj) -> dict:
        return {
            "id":       str(obj.reporter.id),
            "codename": obj.reporter.codename,
            "role":     obj.reporter.role,
        }

    def get_reported_user(self, obj) -> dict:
        return {
            "id":       str(obj.reported_user.id),
            "codename": obj.reported_user.codename,
            "role":     obj.reported_user.role,
        }


class AdminReportDetailSerializer(AdminReportListSerializer):
    """Extended admin detail — includes review tracking fields."""
    reviewed_by = serializers.SerializerMethodField()

    class Meta(AdminReportListSerializer.Meta):
        fields = AdminReportListSerializer.Meta.fields + [
            "reviewed_by", "reviewed_at", "admin_notes",
        ]
        read_only_fields = fields

    def get_reviewed_by(self, obj) -> dict | None:
        if not obj.reviewed_by:
            return None
        return {
            "id":       str(obj.reviewed_by.id),
            "codename": obj.reviewed_by.codename,
        }


class AdminReportUpdateSerializer(serializers.Serializer):
    """Admin updates a report's status and adds notes."""
    status      = serializers.ChoiceField(choices=ReportStatus.choices)
    admin_notes = serializers.CharField(required=False, allow_blank=True)
