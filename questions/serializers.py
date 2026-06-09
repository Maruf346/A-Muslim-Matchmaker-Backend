"""
questions/serializers.py

Serializers for MaleBasicInfo, FemaleBasicInfo, WaliProfile,
WaliBasicInfo, and UserPhoto.

Design notes:
    • All fields are optional (allow_null=True, required=False) to support
      step-by-step PATCH from the mobile app — frontend submits each step
      separately to the same endpoint.
    • JSONField multiselects (ethnicity, nationality etc.) accept a list of
      choice key strings. Validation ensures each submitted key is a valid
      choice.
    • `completion_percentage` and `age` are read-only computed properties.
    • children_count is conditionally required only when has_children=True —
      validated in the serializer's validate() method.
    • pref_age_min/max cross-validation: min must be <= max when both provided.
    • UserPhoto serializer handles multiple photo uploads.
"""

from rest_framework import serializers

from .choices import *
from .models import *


# ─────────────────────────────────────────────────────────────────────────────
# Shared JSONField multiselect validator factory
# ─────────────────────────────────────────────────────────────────────────────

def _make_choice_keys(choices: list) -> set:
    return {key for key, _ in choices}


def _validate_multiselect(value, valid_keys: set, field_name: str) -> list:
    """Validate that every item in a multiselect JSONField is a known choice key."""
    if value is None:
        return value
    if not isinstance(value, list):
        raise serializers.ValidationError(
            {field_name: "Expected a list of choice keys."}
        )
    invalid = [v for v in value if v not in valid_keys]
    if invalid:
        raise serializers.ValidationError(
            {field_name: f"Invalid choice(s): {invalid}"}
        )
    return value


# Pre-build key sets once at import time
_HOW_FOUND_KEYS      = _make_choice_keys(HOW_FOUND_CHOICES)
_ETHNICITY_KEYS      = _make_choice_keys(ETHNICITY_CHOICES)
_NATIONALITY_KEYS    = _make_choice_keys(NATIONALITY_CHOICES)
_MARITAL_KEYS        = _make_choice_keys(MARITAL_STATUS_CHOICES)
_LANGUAGE_KEYS       = _make_choice_keys(LANGUAGE_CHOICES)


# ─────────────────────────────────────────────────────────────────────────────
# User Photo
# ─────────────────────────────────────────────────────────────────────────────

class UserPhotoSerializer(serializers.ModelSerializer):
    """
    Serializer for a single photo.
    Use UserPhotoUploadSerializer for creating new photos.
    """

    class Meta:
        model  = UserPhoto
        fields = ["id", "image", "is_primary", "created_at"]
        read_only_fields = ["id", "created_at"]

    def to_representation(self, instance):
        rep     = super().to_representation(instance)
        request = self.context.get("request")
        if instance.image and request:
            rep["image"] = request.build_absolute_uri(instance.image.url)
        return rep


class UserPhotoUploadSerializer(serializers.ModelSerializer):
    """Used for POST — upload a new photo."""

    class Meta:
        model  = UserPhoto
        fields = ["id", "image", "is_primary"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        user = self.context["request"].user
        # If marked primary, unset any existing primary photo first
        if validated_data.get("is_primary"):
            UserPhoto.objects.filter(user=user, is_primary=True).update(is_primary=False)
        return UserPhoto.objects.create(user=user, **validated_data)


class SetPrimaryPhotoSerializer(serializers.Serializer):
    """Payload for setting a photo as primary."""
    photo_id = serializers.UUIDField()


# ─────────────────────────────────────────────────────────────────────────────
# Male Basic Info
# ─────────────────────────────────────────────────────────────────────────────

class MaleBasicInfoSerializer(serializers.ModelSerializer):
    """
    Read + Write serializer for MaleBasicInfo.

    All fields are optional to allow partial PATCH at any step.
    Multiselect JSONFields are validated against their choice lists.
    `completion_percentage` and `age` are read-only computed properties.
    Photos are managed via the dedicated /photos/ endpoint.
    """

    completion_percentage = serializers.SerializerMethodField(read_only=True)
    age                   = serializers.SerializerMethodField(read_only=True)
    photos                = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = MaleBasicInfo
        fields = [
            # identifiers
            "id",
            # step 1
            "how_found", "phone", "date_of_birth", "city", "country",
            # step 2
            "sect", "marital_status", "ethnicity", "nationality",
            "has_children", "children_count",
            "height", "weight", "pray_5x", "open_to_relocate",
            "employment", "education", "income", "frame", "languages_spoken",
            # step 3
            "preferred_dress",
            "pref_age_min", "pref_age_max",
            "pref_marital_status", "pref_ethnicity",
            # step 4
            "pref_country_of_residence",
            "relationship_with_islam", "role_as_spouse", "about_yourself",
            "envision_spouse", "envision_marriage",
            "spouse_religious_status_pref", "open_to_relocate_details",
            "health_concerns", "other_preferences",
            # computed
            "completion_percentage", "age",
            # photos (read-only, managed via /photos/ endpoint)
            "photos",
            # timestamps
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "completion_percentage", "age", "photos", "created_at", "updated_at"]
        extra_kwargs = {f: {"required": False, "allow_null": True} for f in fields if f not in read_only_fields}

    def get_completion_percentage(self, obj) -> int:
        return obj.completion_percentage

    def get_age(self, obj) -> int | None:
        return obj.age

    def get_photos(self, obj) -> list:
        photos = UserPhoto.objects.filter(user=obj.user)
        return UserPhotoSerializer(photos, many=True, context=self.context).data

    # ── Multiselect validation ─────────────────────────────────────────────

    def validate_how_found(self, value):
        return _validate_multiselect(value, _HOW_FOUND_KEYS, "how_found")

    def validate_ethnicity(self, value):
        return _validate_multiselect(value, _ETHNICITY_KEYS, "ethnicity")

    def validate_nationality(self, value):
        return _validate_multiselect(value, _NATIONALITY_KEYS, "nationality")

    def validate_languages_spoken(self, value):
        return _validate_multiselect(value, _LANGUAGE_KEYS, "languages_spoken")

    def validate_pref_marital_status(self, value):
        return _validate_multiselect(value, _MARITAL_KEYS, "pref_marital_status")

    def validate_pref_ethnicity(self, value):
        return _validate_multiselect(value, _ETHNICITY_KEYS, "pref_ethnicity")

    def validate(self, data):
        # children_count required if has_children=True
        has_children   = data.get("has_children", getattr(self.instance, "has_children", None))
        children_count = data.get("children_count", getattr(self.instance, "children_count", None))
        if has_children is True and not children_count:
            raise serializers.ValidationError(
                {"children_count": "This field is required when has_children is true."}
            )

        # pref age range cross-validation
        age_min = data.get("pref_age_min", getattr(self.instance, "pref_age_min", None))
        age_max = data.get("pref_age_max", getattr(self.instance, "pref_age_max", None))
        if age_min is not None and age_max is not None and age_min > age_max:
            raise serializers.ValidationError(
                {"pref_age_min": "Minimum preferred age cannot be greater than maximum."}
            )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Female Basic Info
# ─────────────────────────────────────────────────────────────────────────────

class FemaleBasicInfoSerializer(serializers.ModelSerializer):
    """
    Read + Write serializer for FemaleBasicInfo.
    Same pattern as MaleBasicInfoSerializer with female-specific fields.
    """

    completion_percentage = serializers.SerializerMethodField(read_only=True)
    age                   = serializers.SerializerMethodField(read_only=True)
    photos                = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = FemaleBasicInfo
        fields = [
            "id",
            # step 1
            "how_found", "phone", "date_of_birth", "city", "country",
            # step 2
            "sect", "marital_status", "ethnicity", "nationality",
            "has_children", "children_count",
            "height", "weight", "pray_5x", "open_to_relocate",
            "dress",
            "wali_name", "wali_relation", "wali_number",
            "employment", "education", "income", "frame", "languages_spoken",
            # step 3
            "pref_age_min", "pref_age_max",
            "pref_marital_status", "pref_ethnicity",
            # step 4
            "pref_country_of_residence",
            "relationship_with_islam", "role_as_spouse", "about_yourself",
            "envision_spouse", "envision_marriage",
            "spouse_religious_status_pref", "open_to_relocate_details",
            "health_concerns", "other_preferences",
            # computed
            "completion_percentage", "age",
            "photos",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "completion_percentage", "age", "photos", "created_at", "updated_at"]
        extra_kwargs = {f: {"required": False, "allow_null": True} for f in fields if f not in read_only_fields}

    def get_completion_percentage(self, obj) -> int:
        return obj.completion_percentage

    def get_age(self, obj) -> int | None:
        return obj.age

    def get_photos(self, obj) -> list:
        photos = UserPhoto.objects.filter(user=obj.user)
        return UserPhotoSerializer(photos, many=True, context=self.context).data

    def validate_how_found(self, value):
        return _validate_multiselect(value, _HOW_FOUND_KEYS, "how_found")

    def validate_ethnicity(self, value):
        return _validate_multiselect(value, _ETHNICITY_KEYS, "ethnicity")

    def validate_nationality(self, value):
        return _validate_multiselect(value, _NATIONALITY_KEYS, "nationality")

    def validate_languages_spoken(self, value):
        return _validate_multiselect(value, _LANGUAGE_KEYS, "languages_spoken")

    def validate_pref_marital_status(self, value):
        return _validate_multiselect(value, _MARITAL_KEYS, "pref_marital_status")

    def validate_pref_ethnicity(self, value):
        return _validate_multiselect(value, _ETHNICITY_KEYS, "pref_ethnicity")

    def validate(self, data):
        has_children   = data.get("has_children", getattr(self.instance, "has_children", None))
        children_count = data.get("children_count", getattr(self.instance, "children_count", None))
        if has_children is True and not children_count:
            raise serializers.ValidationError(
                {"children_count": "This field is required when has_children is true."}
            )

        age_min = data.get("pref_age_min", getattr(self.instance, "pref_age_min", None))
        age_max = data.get("pref_age_max", getattr(self.instance, "pref_age_max", None))
        if age_min is not None and age_max is not None and age_min > age_max:
            raise serializers.ValidationError(
                {"pref_age_min": "Minimum preferred age cannot be greater than maximum."}
            )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Wali Profile  (Wali's own Step 1 info)
# ─────────────────────────────────────────────────────────────────────────────

class WaliProfileSerializer(serializers.ModelSerializer):
    """
    Wali's own personal info — Step 1.
    Managed separately from WaliBasicInfo (the sister's data).
    """

    completion_percentage = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = WaliProfile
        fields = [
            "id",
            "how_found", "gender", "relation_to_sister", "phone",
            "completion_percentage",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "completion_percentage", "created_at", "updated_at"]
        extra_kwargs = {f: {"required": False, "allow_null": True} for f in fields if f not in read_only_fields}

    def get_completion_percentage(self, obj) -> int:
        return obj.completion_percentage

    def validate_how_found(self, value):
        return _validate_multiselect(value, _HOW_FOUND_KEYS, "how_found")


# ─────────────────────────────────────────────────────────────────────────────
# Wali Basic Info  (Sister's profile data — Steps 2–4)
# ─────────────────────────────────────────────────────────────────────────────

class WaliBasicInfoSerializer(serializers.ModelSerializer):
    """
    The sister's full profile as submitted by her Wali (Steps 2–4).
    Mirrors FemaleBasicInfo closely with sister_first/last_name instead of user fields.
    """

    completion_percentage = serializers.SerializerMethodField(read_only=True)
    age                   = serializers.SerializerMethodField(read_only=True)
    photos                = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = WaliBasicInfo
        fields = [
            "id",
            # step 2 — sister's personal details
            "sister_first_name", "sister_last_name",
            "date_of_birth", "city", "country",
            "about",
            "sect", "marital_status", "ethnicity", "nationality",
            "has_children", "children_count",
            "height", "weight", "pray_5x", "open_to_relocate",
            "dress",
            "employment", "education", "income", "frame", "languages_spoken",
            # step 3
            "pref_age_min", "pref_age_max",
            "pref_marital_status", "pref_ethnicity",
            # step 4
            "pref_country_of_residence",
            "relationship_with_islam", "role_as_spouse", "about_yourself",
            "envision_spouse", "envision_marriage",
            "spouse_religious_status_pref", "open_to_relocate_details",
            "health_concerns", "other_preferences",
            # computed
            "completion_percentage", "age",
            "photos",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "completion_percentage", "age", "photos", "created_at", "updated_at"]
        extra_kwargs = {f: {"required": False, "allow_null": True} for f in fields if f not in read_only_fields}

    def get_completion_percentage(self, obj) -> int:
        return obj.completion_percentage

    def get_age(self, obj) -> int | None:
        return obj.age

    def get_photos(self, obj) -> list:
        photos = UserPhoto.objects.filter(user=obj.user)
        return UserPhotoSerializer(photos, many=True, context=self.context).data

    def validate_how_found(self, value):
        return _validate_multiselect(value, _HOW_FOUND_KEYS, "how_found")

    def validate_ethnicity(self, value):
        return _validate_multiselect(value, _ETHNICITY_KEYS, "ethnicity")

    def validate_nationality(self, value):
        return _validate_multiselect(value, _NATIONALITY_KEYS, "nationality")

    def validate_languages_spoken(self, value):
        return _validate_multiselect(value, _LANGUAGE_KEYS, "languages_spoken")

    def validate_pref_marital_status(self, value):
        return _validate_multiselect(value, _MARITAL_KEYS, "pref_marital_status")

    def validate_pref_ethnicity(self, value):
        return _validate_multiselect(value, _ETHNICITY_KEYS, "pref_ethnicity")

    def validate(self, data):
        has_children   = data.get("has_children", getattr(self.instance, "has_children", None))
        children_count = data.get("children_count", getattr(self.instance, "children_count", None))
        if has_children is True and not children_count:
            raise serializers.ValidationError(
                {"children_count": "This field is required when has_children is true."}
            )

        age_min = data.get("pref_age_min", getattr(self.instance, "pref_age_min", None))
        age_max = data.get("pref_age_max", getattr(self.instance, "pref_age_max", None))
        if age_min is not None and age_max is not None and age_min > age_max:
            raise serializers.ValidationError(
                {"pref_age_min": "Minimum preferred age cannot be greater than maximum."}
            )
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Choice listing serializers  (for frontend dropdowns)
# ─────────────────────────────────────────────────────────────────────────────

class ChoiceItemSerializer(serializers.Serializer):
    """Single choice item: key + display label."""
    key   = serializers.CharField()
    label = serializers.CharField()


class ChoicesResponseSerializer(serializers.Serializer):
    """
    Wraps all dropdown/multiselect choice lists in a single response.
    Returned by GET /api/questions/choices/.
    """
    how_found         = ChoiceItemSerializer(many=True)
    sect              = ChoiceItemSerializer(many=True)
    marital_status    = ChoiceItemSerializer(many=True)
    ethnicity         = ChoiceItemSerializer(many=True)
    nationality       = ChoiceItemSerializer(many=True)
    children_count    = ChoiceItemSerializer(many=True)
    male_heights      = ChoiceItemSerializer(many=True)
    female_heights    = ChoiceItemSerializer(many=True)
    male_weights      = ChoiceItemSerializer(many=True)
    female_weights    = ChoiceItemSerializer(many=True)
    pray              = ChoiceItemSerializer(many=True)
    relocation        = ChoiceItemSerializer(many=True)
    dress             = ChoiceItemSerializer(many=True)
    preferred_dress   = ChoiceItemSerializer(many=True)
    education         = ChoiceItemSerializer(many=True)
    income            = ChoiceItemSerializer(many=True)
    frame             = ChoiceItemSerializer(many=True)
    languages         = ChoiceItemSerializer(many=True)
    wali_relation     = ChoiceItemSerializer(many=True)
