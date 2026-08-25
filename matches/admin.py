from django.contrib import admin

from .models import Match


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "match_id",
        "male_user",
        "other_user",
        "status",
        "photo_request_status",
        "second_photo_request_status",
        "wali_request_status",
        "photos_revealed_count",
        "photo_view_count",
        "created_at",
    )
    list_filter = (
        "status",
        "photo_request_status",
        "second_photo_request_status",
        "wali_request_status",
        "photos_currently_visible",
        "created_at",
        "accepted_at",
        "married_at",
    )
    search_fields = (
        "match_id",
        "male_user__email",
        "male_user__first_name",
        "male_user__last_name",
        "male_user__codename",
        "other_user__email",
        "other_user__first_name",
        "other_user__last_name",
        "other_user__codename",
    )
    raw_id_fields = (
        "male_user",
        "other_user",
        "initiated_by",
        "cancelled_by",
        "dropped_by",
        "photo_requested_by",
        "last_status_changed_by_admin",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Core",
            {
                "fields": (
                    "match_id",
                    "male_user",
                    "other_user",
                    "initiated_by",
                    "status",
                )
            },
        ),
        (
            "Photo Access",
            {
                "fields": (
                    "photo_request_status",
                    "photo_requested_by",
                    "photos_currently_visible",
                    "photos_revealed_count",
                    "photo_view_count",
                    "second_photo_request_status",
                    "first_photos_revealed_at",
                    "last_photos_revealed_at",
                )
            },
        ),
        (
            "Wali",
            {
                "fields": (
                    "wali_request_status",
                    "wali_requested_at",
                    "wali_responded_at",
                )
            },
        ),
        (
            "Lifecycle",
            {
                "fields": (
                    "requested_at",
                    "responded_at",
                    "accepted_at",
                    "in_discussion_at",
                    "married_at",
                )
            },
        ),
        (
            "Cancellation / Drop",
            {
                "fields": (
                    "cancelled_by",
                    "cancelled_at",
                    "dropped_by",
                    "dropped_at",
                )
            },
        ),
        (
            "Admin Tracking",
            {
                "fields": (
                    "last_status_changed_by_admin",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
