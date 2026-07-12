from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RecentActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("activity_type", models.CharField(choices=[("user_registered", "User Registered"), ("match_created", "Match Created"), ("matchmaking_request_created", "Matchmaking Request Created"), ("matchmaking_request_approved", "Matchmaking Request Approved"), ("matchmaking_request_declined", "Matchmaking Request Declined"), ("user_married", "User Married"), ("user_verified", "User Verified")], db_index=True, max_length=50)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("primary_user_name", models.CharField(blank=True, max_length=160)),
                ("secondary_user_name", models.CharField(blank=True, max_length=160)),
                ("actor_user_name", models.CharField(blank=True, max_length=160)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor_user", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="dashboard_activities_actor", to=settings.AUTH_USER_MODEL)),
                ("primary_user", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="dashboard_activities_primary", to=settings.AUTH_USER_MODEL)),
                ("secondary_user", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="dashboard_activities_secondary", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="recentactivity",
            index=models.Index(fields=["activity_type", "created_at"], name="dashboard_r_activit_28d8dc_idx"),
        ),
        migrations.AddIndex(
            model_name="recentactivity",
            index=models.Index(fields=["created_at"], name="dashboard_r_created_492d14_idx"),
        ),
    ]
