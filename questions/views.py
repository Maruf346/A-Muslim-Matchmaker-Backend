"""
questions/views.py

Swagger tag strategy:
    Basic Info - Male     — MaleBasicInfo GET/PATCH + photos
    Basic Info - Female   — FemaleBasicInfo GET/PATCH + photos
    Basic Info - Wali     — WaliProfile + WaliBasicInfo GET/PATCH + photos
    Basic Info - Choices  — dropdown/multiselect option lists (all roles)
    Basic Info - Admin    — admin read access to any user's basic info

Each role has a single upsert endpoint (GET + PATCH).
The record is auto-created on first PATCH if it doesn't exist yet
(get_or_create pattern) so the frontend never needs a separate POST.

Photos are managed via dedicated sub-endpoints per role.
"""

import logging

from django.contrib.auth import get_user_model
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .choices import *
from .models import *
from .serializers import *
from users.permissions import IsAdminUser, IsFemaleUser, IsMaleUser, IsWaliUser

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _choices_to_list(choices: list) -> list[dict]:
    """Convert (key, label) tuples to [{"key": ..., "label": ...}] dicts."""
    return [{"key": k, "label": v} for k, v in choices]


# ═══════════════════════════════════════════════════════════════════════════════
# CHOICES ENDPOINT  (all roles — used to populate frontend dropdowns)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(
    tags=["Basic Info - Choices"],
    summary="Get all dropdown / multiselect choice lists",
    description=(
        "Returns every choice list used across all onboarding forms in a single call. "
        "The frontend should cache this response and use it to populate all dropdowns "
        "and multiselect fields.\n\n"
        "Available to all authenticated users (Male, Female, Wali, Admin)."
    ),
    responses={200: ChoicesResponseSerializer},
)
class ChoicesView(APIView):
    """Returns all dropdown and multiselect options for all onboarding forms."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            "how_found":       _choices_to_list(HOW_FOUND_CHOICES),
            "sect":            _choices_to_list(SECT_CHOICES),
            "marital_status":  _choices_to_list(MARITAL_STATUS_CHOICES),
            "ethnicity":       _choices_to_list(ETHNICITY_CHOICES),
            "nationality":     _choices_to_list(NATIONALITY_CHOICES),
            "children_count":  _choices_to_list(CHILDREN_COUNT_CHOICES),
            "male_heights":    _choices_to_list(MALE_HEIGHT_CHOICES),
            "female_heights":  _choices_to_list(FEMALE_HEIGHT_CHOICES),
            "male_weights":    _choices_to_list(MALE_WEIGHT_CHOICES),
            "female_weights":  _choices_to_list(FEMALE_WEIGHT_CHOICES),
            "pray":            _choices_to_list(PRAY_CHOICES),
            "relocation":      _choices_to_list(RELOCATION_CHOICES),
            "dress":           _choices_to_list(DRESS_CHOICES),
            "preferred_dress": _choices_to_list(PREFERRED_DRESS_CHOICES),
            "education":       _choices_to_list(EDUCATION_CHOICES),
            "income":          _choices_to_list(INCOME_CHOICES),
            "frame":           _choices_to_list(FRAME_CHOICES),
            "languages":       _choices_to_list(LANGUAGE_CHOICES),
            "wali_relation":   _choices_to_list(WALI_RELATION_CHOICES),
        }
        return Response(data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# MALE BASIC INFO
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Basic Info - Male"])
class MaleBasicInfoView(APIView):
    """
    GET  — Retrieve own basic info (creates empty record if none exists yet).
    PATCH — Partially update basic info. Can be called multiple times (per step).
    Available to: Male users only.
    """
    permission_classes = [IsMaleUser]
    parser_classes     = [JSONParser, FormParser, MultiPartParser]

    @extend_schema(
        summary="Male — Get my basic info",
        description=(
            "Returns the brother's full onboarding profile including "
            "`completion_percentage`, `age` (computed from DOB), and attached photos. "
            "An empty record is created automatically on first call if none exists."
        ),
        responses={200: MaleBasicInfoSerializer},
    )
    def get(self, request):
        obj, _ = MaleBasicInfo.objects.get_or_create(user=request.user)
        serializer = MaleBasicInfoSerializer(obj, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Male — Update my basic info (partial)",
        description=(
            "Partially update the brother's onboarding profile. "
            "All fields are optional — submit only the fields being updated at this step. "
            "The record is created automatically on first PATCH if it doesn't exist yet.\n\n"
            "**Multiselect fields** (`how_found`, `ethnicity`, `nationality`, "
            "`languages_spoken`, `pref_marital_status`, `pref_ethnicity`, "
            "`pref_country_of_residence`) accept a JSON **list** of choice key strings.\n\n"
            "`children_count` is required when `has_children=true`.\n\n"
            "`pref_age_min` must be ≤ `pref_age_max` when both are provided."
        ),
        request=MaleBasicInfoSerializer,
        responses={
            200: MaleBasicInfoSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def patch(self, request):
        obj, _ = MaleBasicInfo.objects.get_or_create(user=request.user)
        serializer = MaleBasicInfoSerializer(
            obj, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# MALE PHOTOS
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Basic Info - Male"])
class MalePhotosView(APIView):
    """
    GET  — List all photos for the authenticated male user.
    POST — Upload a new photo (Step 5).
    Available to: Male users only.
    """
    permission_classes = [IsMaleUser]
    parser_classes     = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Male — List my photos",
        responses={200: UserPhotoSerializer(many=True)},
    )
    def get(self, request):
        photos = UserPhoto.objects.filter(user=request.user)
        return Response(
            UserPhotoSerializer(photos, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Male — Upload a photo",
        description=(
            "Upload a new profile photo. Pass `image` as multipart file. "
            "Set `is_primary=true` to make it the main profile photo "
            "(automatically unsets the previous primary)."
        ),
        request=UserPhotoUploadSerializer,
        responses={
            201: UserPhotoSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def post(self, request):
        serializer = UserPhotoUploadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        photo = serializer.save()
        return Response(
            UserPhotoSerializer(photo, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Basic Info - Male"])
class MalePhotoDetailView(APIView):
    """
    DELETE — Delete a specific photo.
    PATCH  — Set a photo as primary.
    Available to: Male users only.
    """
    permission_classes = [IsMaleUser]

    def _get_photo(self, request, photo_id):
        try:
            return UserPhoto.objects.get(id=photo_id, user=request.user)
        except UserPhoto.DoesNotExist:
            return None

    @extend_schema(
        summary="Male — Delete a photo",
        responses={
            204: OpenApiResponse(description="Photo deleted."),
            404: OpenApiResponse(description="Photo not found."),
        },
    )
    def delete(self, request, photo_id):
        photo = self._get_photo(request, photo_id)
        if not photo:
            return Response({"error": "Photo not found."}, status=status.HTTP_404_NOT_FOUND)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Male — Set photo as primary",
        request=SetPrimaryPhotoSerializer,
        responses={
            200: UserPhotoSerializer,
            404: OpenApiResponse(description="Photo not found."),
        },
    )
    def patch(self, request, photo_id):
        photo = self._get_photo(request, photo_id)
        if not photo:
            return Response({"error": "Photo not found."}, status=status.HTTP_404_NOT_FOUND)
        UserPhoto.objects.filter(user=request.user, is_primary=True).update(is_primary=False)
        photo.is_primary = True
        photo.save(update_fields=["is_primary"])
        return Response(
            UserPhotoSerializer(photo, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# FEMALE BASIC INFO
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Basic Info - Female"])
class FemaleBasicInfoView(APIView):
    """
    GET  — Retrieve own basic info.
    PATCH — Partially update basic info.
    Available to: Female users only.
    """
    permission_classes = [IsFemaleUser]
    parser_classes     = [JSONParser, FormParser, MultiPartParser]

    @extend_schema(
        summary="Female — Get my basic info",
        description=(
            "Returns the sister's full onboarding profile including "
            "`completion_percentage`, `age`, and attached photos."
        ),
        responses={200: FemaleBasicInfoSerializer},
    )
    def get(self, request):
        obj, _ = FemaleBasicInfo.objects.get_or_create(user=request.user)
        return Response(
            FemaleBasicInfoSerializer(obj, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Female — Update my basic info (partial)",
        description=(
            "Partially update the sister's onboarding profile. "
            "All fields are optional — submit only the fields being updated at this step. "
            "`children_count` is required when `has_children=true`."
        ),
        request=FemaleBasicInfoSerializer,
        responses={
            200: FemaleBasicInfoSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
    )
    def patch(self, request):
        obj, _ = FemaleBasicInfo.objects.get_or_create(user=request.user)
        serializer = FemaleBasicInfoSerializer(
            obj, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# FEMALE PHOTOS
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Basic Info - Female"])
class FemalePhotosView(APIView):
    """GET — List photos. POST — Upload photo. Available to: Female users only."""
    permission_classes = [IsFemaleUser]
    parser_classes     = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Female — List my photos",
        responses={200: UserPhotoSerializer(many=True)},
    )
    def get(self, request):
        photos = UserPhoto.objects.filter(user=request.user)
        return Response(
            UserPhotoSerializer(photos, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Female — Upload a photo",
        request=UserPhotoUploadSerializer,
        responses={201: UserPhotoSerializer},
    )
    def post(self, request):
        serializer = UserPhotoUploadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        photo = serializer.save()
        return Response(
            UserPhotoSerializer(photo, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Basic Info - Female"])
class FemalePhotoDetailView(APIView):
    """DELETE / PATCH (set primary) for a specific photo. Female users only."""
    permission_classes = [IsFemaleUser]

    def _get_photo(self, request, photo_id):
        try:
            return UserPhoto.objects.get(id=photo_id, user=request.user)
        except UserPhoto.DoesNotExist:
            return None

    @extend_schema(
        summary="Female — Delete a photo",
        responses={204: OpenApiResponse(description="Deleted."), 404: OpenApiResponse(description="Not found.")},
    )
    def delete(self, request, photo_id):
        photo = self._get_photo(request, photo_id)
        if not photo:
            return Response({"error": "Photo not found."}, status=status.HTTP_404_NOT_FOUND)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Female — Set photo as primary",
        responses={200: UserPhotoSerializer, 404: OpenApiResponse(description="Not found.")},
    )
    def patch(self, request, photo_id):
        photo = self._get_photo(request, photo_id)
        if not photo:
            return Response({"error": "Photo not found."}, status=status.HTTP_404_NOT_FOUND)
        UserPhoto.objects.filter(user=request.user, is_primary=True).update(is_primary=False)
        photo.is_primary = True
        photo.save(update_fields=["is_primary"])
        return Response(
            UserPhotoSerializer(photo, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# WALI — OWN PROFILE (Step 1)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Basic Info - Wali"])
class WaliProfileView(APIView):
    """
    GET  — Retrieve wali's own profile (Step 1 data).
    PATCH — Update wali's own profile.
    Available to: Wali users only.
    """
    permission_classes = [IsWaliUser]
    parser_classes     = [JSONParser, FormParser, MultiPartParser]

    @extend_schema(
        summary="Wali — Get my profile (Step 1)",
        description="Returns the wali's own personal info: how_found, gender, relation_to_sister, phone.",
        responses={200: WaliProfileSerializer},
    )
    def get(self, request):
        obj, _ = WaliProfile.objects.get_or_create(user=request.user)
        return Response(
            WaliProfileSerializer(obj, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Wali — Update my profile (Step 1)",
        request=WaliProfileSerializer,
        responses={200: WaliProfileSerializer, 400: OpenApiResponse(description="Validation error.")},
    )
    def patch(self, request):
        obj, _ = WaliProfile.objects.get_or_create(user=request.user)
        serializer = WaliProfileSerializer(
            obj, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# WALI — SISTER'S BASIC INFO (Steps 2–4)
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Basic Info - Wali"])
class WaliBasicInfoView(APIView):
    """
    GET  — Retrieve the sister's profile data as entered by the wali.
    PATCH — Partially update the sister's profile data.
    Available to: Wali users only.
    """
    permission_classes = [IsWaliUser]
    parser_classes     = [JSONParser, FormParser, MultiPartParser]

    @extend_schema(
        summary="Wali — Get the sister's basic info (Steps 2–4)",
        description=(
            "Returns the sister's full profile data submitted by the wali, "
            "including `completion_percentage`, `age`, and photos."
        ),
        responses={200: WaliBasicInfoSerializer},
    )
    def get(self, request):
        obj, _ = WaliBasicInfo.objects.get_or_create(user=request.user)
        return Response(
            WaliBasicInfoSerializer(obj, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Wali — Update the sister's basic info (partial)",
        description=(
            "Partially update the sister's onboarding profile. "
            "All fields optional — submit only the fields being updated at this step."
        ),
        request=WaliBasicInfoSerializer,
        responses={200: WaliBasicInfoSerializer, 400: OpenApiResponse(description="Validation error.")},
    )
    def patch(self, request):
        obj, _ = WaliBasicInfo.objects.get_or_create(user=request.user)
        serializer = WaliBasicInfoSerializer(
            obj, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# WALI PHOTOS
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Basic Info - Wali"])
class WaliPhotosView(APIView):
    """GET — List photos. POST — Upload photo. Available to: Wali users only."""
    permission_classes = [IsWaliUser]
    parser_classes     = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Wali — List sister's photos",
        responses={200: UserPhotoSerializer(many=True)},
    )
    def get(self, request):
        photos = UserPhoto.objects.filter(user=request.user)
        return Response(
            UserPhotoSerializer(photos, many=True, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Wali — Upload a photo for the sister",
        request=UserPhotoUploadSerializer,
        responses={201: UserPhotoSerializer},
    )
    def post(self, request):
        serializer = UserPhotoUploadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        photo = serializer.save()
        return Response(
            UserPhotoSerializer(photo, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Basic Info - Wali"])
class WaliPhotoDetailView(APIView):
    """DELETE / PATCH (set primary) for a specific photo. Wali users only."""
    permission_classes = [IsWaliUser]

    def _get_photo(self, request, photo_id):
        try:
            return UserPhoto.objects.get(id=photo_id, user=request.user)
        except UserPhoto.DoesNotExist:
            return None

    @extend_schema(
        summary="Wali — Delete a photo",
        responses={204: OpenApiResponse(description="Deleted."), 404: OpenApiResponse(description="Not found.")},
    )
    def delete(self, request, photo_id):
        photo = self._get_photo(request, photo_id)
        if not photo:
            return Response({"error": "Photo not found."}, status=status.HTTP_404_NOT_FOUND)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Wali — Set photo as primary",
        responses={200: UserPhotoSerializer, 404: OpenApiResponse(description="Not found.")},
    )
    def patch(self, request, photo_id):
        photo = self._get_photo(request, photo_id)
        if not photo:
            return Response({"error": "Photo not found."}, status=status.HTTP_404_NOT_FOUND)
        UserPhoto.objects.filter(user=request.user, is_primary=True).update(is_primary=False)
        photo.is_primary = True
        photo.save(update_fields=["is_primary"])
        return Response(
            UserPhotoSerializer(photo, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — READ ANY USER'S BASIC INFO
# ═══════════════════════════════════════════════════════════════════════════════

@extend_schema(tags=["Basic Info - Admin"])
class AdminUserBasicInfoView(APIView):
    """
    GET — Retrieve any user's basic info by their User UUID.
    Returns the correct info model based on the user's role.
    Available to: Matchmaker, Superadmin.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Admin — Get any user's basic info",
        description=(
            "Returns the basic info record for the specified user. "
            "The response schema varies by role:\n"
            "- **Male** → MaleBasicInfo fields\n"
            "- **Female** → FemaleBasicInfo fields\n"
            "- **Wali** → WaliProfile + WaliBasicInfo fields combined\n\n"
            "Pass the user's UUID as `user_id` in the URL."
        ),
        parameters=[
            OpenApiParameter("user_id", str, location="path", description="User UUID."),
        ],
        responses={
            200: OpenApiResponse(description="Basic info for the requested user."),
            404: OpenApiResponse(description="User not found."),
            400: OpenApiResponse(description="User has no basic info or unsupported role."),
        },
    )
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        ctx = {"request": request}

        if user.role == "male":
            obj, _ = MaleBasicInfo.objects.get_or_create(user=user)
            return Response(MaleBasicInfoSerializer(obj, context=ctx).data)

        if user.role == "female":
            obj, _ = FemaleBasicInfo.objects.get_or_create(user=user)
            return Response(FemaleBasicInfoSerializer(obj, context=ctx).data)

        if user.role == "wali":
            wali_profile, _ = WaliProfile.objects.get_or_create(user=user)
            wali_info, _    = WaliBasicInfo.objects.get_or_create(user=user)
            return Response({
                "wali_profile":    WaliProfileSerializer(wali_profile, context=ctx).data,
                "sister_info":     WaliBasicInfoSerializer(wali_info, context=ctx).data,
            })

        return Response(
            {"error": f"Basic info is not applicable for role: {user.role}."},
            status=status.HTTP_400_BAD_REQUEST,
        )
        
    @extend_schema(
        tags=["Basic Info - Admin"],
        summary="Admin — Update any user's basic info",
        description=(
            "Partially update the basic info for the specified user. "
            "Routes to the correct model based on user role. "
            "All fields are optional — only submitted fields are updated. "
            "For Wali users, pass `target`: `wali_profile` or `sister_info` "
            "to indicate which record to update (defaults to `sister_info`)."
        ),
        parameters=[
            OpenApiParameter("user_id", str, location="path", description="User UUID."),
            OpenApiParameter(
                "target", str,
                description="For Wali only: `wali_profile` or `sister_info` (default).",
            ),
        ],
        responses={
            200: OpenApiResponse(description="Updated basic info."),
            404: OpenApiResponse(description="User not found."),
            400: OpenApiResponse(description="Validation error or unsupported role."),
        },
    )
    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
 
        ctx = {"request": request}
 
        if user.role == "male":
            obj, _ = MaleBasicInfo.objects.get_or_create(user=user)
            serializer = MaleBasicInfoSerializer(obj, data=request.data, partial=True, context=ctx)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
 
        if user.role == "female":
            obj, _ = FemaleBasicInfo.objects.get_or_create(user=user)
            serializer = FemaleBasicInfoSerializer(obj, data=request.data, partial=True, context=ctx)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
 
        if user.role == "wali":
            target = request.query_params.get("target", "sister_info")
            if target == "wali_profile":
                obj, _ = WaliProfile.objects.get_or_create(user=user)
                serializer = WaliProfileSerializer(obj, data=request.data, partial=True, context=ctx)
            else:
                obj, _ = WaliBasicInfo.objects.get_or_create(user=user)
                serializer = WaliBasicInfoSerializer(obj, data=request.data, partial=True, context=ctx)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
 
        return Response(
            {"error": f"Basic info is not applicable for role: {user.role}."},
            status=status.HTTP_400_BAD_REQUEST,
        )