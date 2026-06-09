"""
questions/models.py

Models:
    MaleBasicInfo    — Brother's onboarding data (Steps 1–4)
    FemaleBasicInfo  — Sister's onboarding data (Steps 1–4)
    WaliProfile      — Wali's own personal info (Step 1)
    WaliBasicInfo    — The sister's profile data submitted by wali (Steps 2–4)
    UserPhoto        — Multiple photos per user (Step 5, shared across all roles)

Design notes:
    • All fields are blank=True, null=True to support partial saves and
      step-by-step form submission from the mobile app.
    • Multiselect fields use JSONField (stores a list of choice keys).
    • Profile completion % is a @property computed from non-null fields.
    • Height/Weight stored as full display strings e.g. "170cm - 5' 7\"".
    • Phone is stored here (not on User model) per the agreed design.
    • Steps map to field groups in comments but the API is a single
      endpoint — frontend PATCHes in as many calls as needed.
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

from .choices import *

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Shared completion helper
# ─────────────────────────────────────────────────────────────────────────────

def _completion_percent(instance, fields: list[str]) -> int:
    """
    Given a list of field names that count toward completion,
    return the percentage of those fields that are filled (not null/empty).
    JSONField lists are considered filled if non-empty.
    """
    if not fields:
        return 0
    filled = 0
    for field in fields:
        val = getattr(instance, field, None)
        if val is None:
            continue
        if isinstance(val, list) and len(val) == 0:
            continue
        if isinstance(val, str) and val.strip() == "":
            continue
        filled += 1
    return round((filled / len(fields)) * 100)


# ─────────────────────────────────────────────────────────────────────────────
# Male Basic Info
# ─────────────────────────────────────────────────────────────────────────────

class MaleBasicInfo(models.Model):
    """
    Complete onboarding profile for a Brother (Male user).

    Steps (frontend only — backend treats all as one model):
        Step 1: how_found, phone, date_of_birth, city, country
        Step 2: About You — sect, marital_status, ethnicity, nationality,
                has_children, children_count, height, weight, pray_5x,
                open_to_relocate, employment, education, income, frame,
                languages_spoken
        Step 3: Preferences — preferred_dress, pref_age_min, pref_age_max,
                pref_marital_status, pref_ethnicity
        Step 4: Idea of marriage — all text fields + pref_country_of_residence
        Step 5: Photos — handled by UserPhoto model
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="male_basic_info",
    )

    # ── Step 1 ────────────────────────────────────────────────────────────────
    how_found    = models.JSONField(
        default=list, blank=True, null=True,
        help_text="Multiselect — list of HOW_FOUND_CHOICES keys.",
    )
    phone        = models.CharField(max_length=30, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    city         = models.CharField(max_length=100, blank=True, null=True)
    country      = models.CharField(max_length=100, blank=True, null=True)

    # ── Step 2 — About You ───────────────────────────────────────────────────
    sect           = models.CharField(max_length=20,  choices=SECT_CHOICES,           blank=True, null=True)
    marital_status = models.CharField(max_length=30,  choices=MARITAL_STATUS_CHOICES, blank=True, null=True)
    ethnicity      = models.JSONField(default=list, blank=True, null=True,
                        help_text="Multiselect — list of ETHNICITY_CHOICES keys.")
    nationality    = models.JSONField(default=list, blank=True, null=True,
                        help_text="Multiselect — list of NATIONALITY_CHOICES keys.")
    has_children   = models.BooleanField(blank=True, null=True)
    children_count = models.CharField(
        max_length=10, choices=CHILDREN_COUNT_CHOICES, blank=True, null=True,
        help_text="Required only if has_children=True.",
    )
    height         = models.CharField(max_length=30, choices=MALE_HEIGHT_CHOICES, blank=True, null=True,
                        help_text="Full display string e.g. '170cm - 5' 7\"'.")
    weight         = models.CharField(max_length=30, choices=MALE_WEIGHT_CHOICES, blank=True, null=True,
                        help_text="Full display string e.g. '70kg - 154lbs'.")
    pray_5x        = models.CharField(max_length=10, choices=PRAY_CHOICES,       blank=True, null=True)
    open_to_relocate = models.CharField(max_length=20, choices=RELOCATION_CHOICES, blank=True, null=True)
    employment     = models.CharField(max_length=200, blank=True, null=True)
    education      = models.CharField(max_length=30,  choices=EDUCATION_CHOICES,  blank=True, null=True)
    income         = models.CharField(max_length=20,  choices=INCOME_CHOICES,     blank=True, null=True)
    frame          = models.CharField(max_length=20,  choices=FRAME_CHOICES,      blank=True, null=True)
    languages_spoken = models.JSONField(default=list, blank=True, null=True,
                        help_text="Multiselect — list of LANGUAGE_CHOICES keys.")

    # ── Step 3 — Preferences ─────────────────────────────────────────────────
    preferred_dress       = models.CharField(
        max_length=20, choices=PREFERRED_DRESS_CHOICES, blank=True, null=True,
        help_text="Brother's preference for how his spouse dresses.",
    )
    pref_age_min          = models.PositiveSmallIntegerField(blank=True, null=True)
    pref_age_max          = models.PositiveSmallIntegerField(blank=True, null=True)
    pref_marital_status   = models.JSONField(default=list, blank=True, null=True,
                                help_text="Multiselect — list of MARITAL_STATUS_CHOICES keys.")
    pref_ethnicity        = models.JSONField(default=list, blank=True, null=True,
                                help_text="Multiselect — list of ETHNICITY_CHOICES keys.")

    # ── Step 4 — Idea of marriage ─────────────────────────────────────────────
    pref_country_of_residence   = models.JSONField(default=list, blank=True, null=True,
                                    help_text="Multiselect — country/region strings.")
    relationship_with_islam     = models.TextField(blank=True, null=True)
    role_as_spouse              = models.TextField(blank=True, null=True)
    about_yourself              = models.TextField(blank=True, null=True)
    envision_spouse             = models.TextField(blank=True, null=True)
    envision_marriage           = models.TextField(blank=True, null=True)
    spouse_religious_status_pref = models.TextField(blank=True, null=True)
    open_to_relocate_details    = models.TextField(blank=True, null=True)
    health_concerns             = models.TextField(blank=True, null=True)
    other_preferences           = models.TextField(blank=True, null=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Profile completion ────────────────────────────────────────────────────

    # Fields that count toward completion % (excludes optional free-text)
    COMPLETION_FIELDS = [
        "how_found", "phone", "date_of_birth", "city", "country",
        "sect", "marital_status", "ethnicity", "nationality",
        "has_children", "height", "weight", "pray_5x", "open_to_relocate",
        "employment", "education", "income", "frame", "languages_spoken",
        "preferred_dress", "pref_age_min", "pref_age_max",
        "pref_marital_status", "pref_ethnicity",
        "relationship_with_islam", "role_as_spouse", "about_yourself",
        "envision_spouse", "envision_marriage",
    ]

    @property
    def completion_percentage(self) -> int:
        return _completion_percent(self, self.COMPLETION_FIELDS)

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        dob   = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def __str__(self):
        return f"MaleBasicInfo → {self.user.codename or self.user.email}"

    class Meta:
        verbose_name        = "Brother Basic Info"
        verbose_name_plural = "Brothers Basic Info"


# ─────────────────────────────────────────────────────────────────────────────
# Female Basic Info
# ─────────────────────────────────────────────────────────────────────────────

class FemaleBasicInfo(models.Model):
    """
    Complete onboarding profile for a Sister (Female user).

    Differences from MaleBasicInfo:
        - Has `dress` field (how she dresses) instead of `preferred_dress`
        - Has wali_name, wali_relation, wali_number fields
        - Uses female height/weight ranges
        - No preferred_dress preference field (that's a male preference)
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="female_basic_info",
    )

    # ── Step 1 ────────────────────────────────────────────────────────────────
    how_found     = models.JSONField(default=list, blank=True, null=True)
    phone         = models.CharField(max_length=30, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    city          = models.CharField(max_length=100, blank=True, null=True)
    country       = models.CharField(max_length=100, blank=True, null=True)

    # ── Step 2 — About You ───────────────────────────────────────────────────
    sect           = models.CharField(max_length=20,  choices=SECT_CHOICES,           blank=True, null=True)
    marital_status = models.CharField(max_length=30,  choices=MARITAL_STATUS_CHOICES, blank=True, null=True)
    ethnicity      = models.JSONField(default=list, blank=True, null=True)
    nationality    = models.JSONField(default=list, blank=True, null=True)
    has_children   = models.BooleanField(blank=True, null=True)
    children_count = models.CharField(max_length=10, choices=CHILDREN_COUNT_CHOICES, blank=True, null=True)
    height         = models.CharField(max_length=30, choices=FEMALE_HEIGHT_CHOICES, blank=True, null=True)
    weight         = models.CharField(max_length=30, choices=FEMALE_WEIGHT_CHOICES, blank=True, null=True)
    pray_5x        = models.CharField(max_length=10, choices=PRAY_CHOICES,          blank=True, null=True)
    open_to_relocate = models.CharField(max_length=20, choices=RELOCATION_CHOICES,  blank=True, null=True)
    dress          = models.CharField(
        max_length=20, choices=DRESS_CHOICES, blank=True, null=True,
        help_text="How the sister dresses.",
    )

    # Wali info (collected during sister's own Step 2)
    wali_name     = models.CharField(max_length=150, blank=True, null=True)
    wali_relation = models.CharField(max_length=50,  blank=True, null=True)
    wali_number   = models.CharField(max_length=30,  blank=True, null=True)

    employment       = models.CharField(max_length=200, blank=True, null=True)
    education        = models.CharField(max_length=30,  choices=EDUCATION_CHOICES, blank=True, null=True)
    income           = models.CharField(max_length=20,  choices=INCOME_CHOICES,    blank=True, null=True)
    frame            = models.CharField(max_length=20,  choices=FRAME_CHOICES,     blank=True, null=True)
    languages_spoken = models.JSONField(default=list, blank=True, null=True)

    # ── Step 3 — Preferences ─────────────────────────────────────────────────
    pref_age_min        = models.PositiveSmallIntegerField(blank=True, null=True)
    pref_age_max        = models.PositiveSmallIntegerField(blank=True, null=True)
    pref_marital_status = models.JSONField(default=list, blank=True, null=True)
    pref_ethnicity      = models.JSONField(default=list, blank=True, null=True)

    # ── Step 4 — Idea of marriage ─────────────────────────────────────────────
    pref_country_of_residence    = models.JSONField(default=list, blank=True, null=True)
    relationship_with_islam      = models.TextField(blank=True, null=True)
    role_as_spouse               = models.TextField(blank=True, null=True)
    about_yourself               = models.TextField(blank=True, null=True)
    envision_spouse              = models.TextField(blank=True, null=True)
    envision_marriage            = models.TextField(blank=True, null=True)
    spouse_religious_status_pref = models.TextField(blank=True, null=True)
    open_to_relocate_details     = models.TextField(blank=True, null=True)
    health_concerns              = models.TextField(blank=True, null=True)
    other_preferences            = models.TextField(blank=True, null=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    COMPLETION_FIELDS = [
        "how_found", "phone", "date_of_birth", "city", "country",
        "sect", "marital_status", "ethnicity", "nationality",
        "has_children", "height", "weight", "pray_5x", "open_to_relocate",
        "dress", "wali_name", "wali_relation", "wali_number",
        "employment", "education", "income", "frame", "languages_spoken",
        "pref_age_min", "pref_age_max", "pref_marital_status", "pref_ethnicity",
        "relationship_with_islam", "role_as_spouse", "about_yourself",
        "envision_spouse", "envision_marriage",
    ]

    @property
    def completion_percentage(self) -> int:
        return _completion_percent(self, self.COMPLETION_FIELDS)

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        dob   = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def __str__(self):
        return f"FemaleBasicInfo → {self.user.codename or self.user.email}"

    class Meta:
        verbose_name        = "Sister Basic Info"
        verbose_name_plural = "Sisters Basic Info"


# ─────────────────────────────────────────────────────────────────────────────
# Wali Profile  (Wali's own personal info — Step 1)
# ─────────────────────────────────────────────────────────────────────────────

class WaliProfile(models.Model):
    """
    The Wali's own personal details collected in Step 1.
    Separate from WaliBasicInfo which holds the sister's data.
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wali_profile",
    )

    how_found         = models.JSONField(default=list, blank=True, null=True)
    gender            = models.CharField(max_length=10, choices=WALI_GENDER_CHOICES, blank=True, null=True)
    relation_to_sister = models.CharField(max_length=20, choices=WALI_RELATION_CHOICES, blank=True, null=True)
    phone             = models.CharField(max_length=30, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    COMPLETION_FIELDS = ["how_found", "gender", "relation_to_sister", "phone"]

    @property
    def completion_percentage(self) -> int:
        return _completion_percent(self, self.COMPLETION_FIELDS)

    def __str__(self):
        return f"WaliProfile → {self.user.codename or self.user.email}"

    class Meta:
        verbose_name        = "Wali Profile"
        verbose_name_plural = "Wali Profiles"


# ─────────────────────────────────────────────────────────────────────────────
# Wali Basic Info  (The sister's profile, submitted by Wali — Steps 2–4)
# ─────────────────────────────────────────────────────────────────────────────

class WaliBasicInfo(models.Model):
    """
    The sister's complete profile data as submitted by her Wali.

    Step 2 begins with sister's personal details (first/last name, DOB,
    location) since the wali is filling this on the sister's behalf.
    The rest mirrors FemaleBasicInfo closely.

    Note: Wali is guardian of a female only (per business logic).
    The ward linkage (to a User account for the sister) is handled
    in the matches/onboarding flow — not at this stage.
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wali_basic_info",
    )

    # ── Step 2 — About the Sister ─────────────────────────────────────────────
    sister_first_name = models.CharField(max_length=75,  blank=True, null=True)
    sister_last_name  = models.CharField(max_length=75,  blank=True, null=True)
    date_of_birth     = models.DateField(blank=True, null=True)
    city              = models.CharField(max_length=100, blank=True, null=True)
    country           = models.CharField(max_length=100, blank=True, null=True)

    about             = models.TextField(blank=True, null=True)
    sect              = models.CharField(max_length=20, choices=SECT_CHOICES,           blank=True, null=True)
    marital_status    = models.CharField(max_length=30, choices=MARITAL_STATUS_CHOICES, blank=True, null=True)
    ethnicity         = models.JSONField(default=list, blank=True, null=True)
    nationality       = models.JSONField(default=list, blank=True, null=True)
    has_children      = models.BooleanField(blank=True, null=True)
    children_count    = models.CharField(max_length=10, choices=CHILDREN_COUNT_CHOICES, blank=True, null=True)
    height            = models.CharField(max_length=30, choices=FEMALE_HEIGHT_CHOICES,  blank=True, null=True)
    weight            = models.CharField(max_length=30, choices=FEMALE_WEIGHT_CHOICES,  blank=True, null=True)
    pray_5x           = models.CharField(max_length=10, choices=PRAY_CHOICES,           blank=True, null=True)
    open_to_relocate  = models.CharField(max_length=20, choices=RELOCATION_CHOICES,     blank=True, null=True)
    dress             = models.CharField(max_length=20, choices=DRESS_CHOICES,          blank=True, null=True)
    employment        = models.CharField(max_length=200, blank=True, null=True)
    education         = models.CharField(max_length=30, choices=EDUCATION_CHOICES,      blank=True, null=True)
    income            = models.CharField(max_length=20, choices=INCOME_CHOICES,         blank=True, null=True)
    frame             = models.CharField(max_length=20, choices=FRAME_CHOICES,          blank=True, null=True)
    languages_spoken  = models.JSONField(default=list, blank=True, null=True)

    # ── Step 3 — Her preferences ──────────────────────────────────────────────
    pref_age_min        = models.PositiveSmallIntegerField(blank=True, null=True)
    pref_age_max        = models.PositiveSmallIntegerField(blank=True, null=True)
    pref_marital_status = models.JSONField(default=list, blank=True, null=True)
    pref_ethnicity      = models.JSONField(default=list, blank=True, null=True)

    # ── Step 4 — Idea of marriage ─────────────────────────────────────────────
    pref_country_of_residence    = models.JSONField(default=list, blank=True, null=True)
    relationship_with_islam      = models.TextField(blank=True, null=True)
    role_as_spouse               = models.TextField(blank=True, null=True)
    about_yourself               = models.TextField(blank=True, null=True)
    envision_spouse              = models.TextField(blank=True, null=True)
    envision_marriage            = models.TextField(blank=True, null=True)
    spouse_religious_status_pref = models.TextField(blank=True, null=True)
    open_to_relocate_details     = models.TextField(blank=True, null=True)
    health_concerns              = models.TextField(blank=True, null=True)
    other_preferences            = models.TextField(blank=True, null=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    COMPLETION_FIELDS = [
        "sister_first_name", "sister_last_name", "date_of_birth", "city", "country",
        "sect", "marital_status", "ethnicity", "nationality",
        "has_children", "height", "weight", "pray_5x", "open_to_relocate",
        "dress", "employment", "education", "income", "frame", "languages_spoken",
        "pref_age_min", "pref_age_max", "pref_marital_status", "pref_ethnicity",
        "relationship_with_islam", "role_as_spouse", "about_yourself",
        "envision_spouse", "envision_marriage",
    ]

    @property
    def completion_percentage(self) -> int:
        return _completion_percent(self, self.COMPLETION_FIELDS)

    @property
    def age(self) -> int | None:
        if not self.date_of_birth:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        dob   = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def __str__(self):
        name = f"{self.sister_first_name or ''} {self.sister_last_name or ''}".strip()
        return f"WaliBasicInfo → {name or self.user.codename or self.user.email}"

    class Meta:
        verbose_name        = "Wali — Sister Basic Info"
        verbose_name_plural = "Wali — Sisters Basic Info"


# ─────────────────────────────────────────────────────────────────────────────
# User Photo  (Step 5 — shared across Male, Female, Wali)
# ─────────────────────────────────────────────────────────────────────────────

class UserPhoto(models.Model):
    """
    Multiple photos per user. Shared across all normal user roles.

    Visibility rule (enforced at serializer level in the matches app):
        Photos are HIDDEN (blurred by frontend) until mutual interest.
        After mutual interest, photos are viewable ONCE then require
        a PhotoRequest to view again.
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image      = models.ImageField(upload_to="users/photos/")
    is_primary = models.BooleanField(
        default=False,
        help_text="True for the main profile photo. Only one photo per user should be primary.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo → {self.user.codename or self.user.email} (primary={self.is_primary})"

    class Meta:
        verbose_name        = "User Photo"
        verbose_name_plural = "User Photos"
        ordering            = ["-is_primary", "created_at"]