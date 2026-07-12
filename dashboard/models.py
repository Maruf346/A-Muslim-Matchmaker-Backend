from django.conf import settings
from django.db import models


class ActivityType(models.TextChoices):
    USER_REGISTERED = "user_registered", "User Registered"
    MATCH_CREATED = "match_created", "Match Created"
    MATCHMAKING_REQUEST_CREATED = "matchmaking_request_created", "Matchmaking Request Created"
    MATCHMAKING_REQUEST_APPROVED = "matchmaking_request_approved", "Matchmaking Request Approved"
    MATCHMAKING_REQUEST_DECLINED = "matchmaking_request_declined", "Matchmaking Request Declined"
    USER_MARRIED = "user_married", "User Married"
    USER_VERIFIED = "user_verified", "User Verified"


class RecentActivity(models.Model):
    """
    Stores admin-facing activity history for dashboard cards and timelines.
    User snapshot fields are persisted so the log remains readable even if a
    related user is later edited or deleted.
    """

    activity_type = models.CharField(max_length=50, choices=ActivityType.choices, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    primary_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dashboard_activities_primary",
    )
    secondary_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dashboard_activities_secondary",
    )
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dashboard_activities_actor",
    )

    primary_user_name = models.CharField(max_length=160, blank=True)
    secondary_user_name = models.CharField(max_length=160, blank=True)
    actor_user_name = models.CharField(max_length=160, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["activity_type", "created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.title} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
