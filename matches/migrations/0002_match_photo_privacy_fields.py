from django.db import migrations, models


def backfill_photo_privacy_fields(apps, schema_editor):
    Match = apps.get_model("matches", "Match")
    for match in Match.objects.all().iterator():
        update_fields = []

        revealed_count = min(match.photos_revealed_count or 0, 2)
        if revealed_count and match.photo_view_count != revealed_count:
            match.photo_view_count = revealed_count
            update_fields.append("photo_view_count")

        if (
            match.photo_request_status == "requested"
            and match.photo_requested_by_id == match.male_user_id
            and match.second_photo_request_status == "none"
        ):
            match.second_photo_request_status = "pending"
            update_fields.append("second_photo_request_status")
        elif revealed_count >= 2 and match.second_photo_request_status == "none":
            match.second_photo_request_status = "accepted"
            update_fields.append("second_photo_request_status")

        if update_fields:
            match.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("matches", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="photo_view_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Number of female-photo viewing windows granted to the male user.",
            ),
        ),
        migrations.AddField(
            model_name="match",
            name="second_photo_request_status",
            field=models.CharField(
                choices=[
                    ("none", "None"),
                    ("pending", "Pending"),
                    ("accepted", "Accepted"),
                    ("rejected", "Rejected"),
                ],
                default="none",
                help_text="Tracks the one-time second female-photo viewing request.",
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_photo_privacy_fields, migrations.RunPython.noop),
    ]
