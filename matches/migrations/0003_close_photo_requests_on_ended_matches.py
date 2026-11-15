"""
Data fix: matches that were cancelled / dropped / declined while a photo request
was still open kept that request, so the app showed "Review Photo Request" for a
connection that no longer exists. Close those requests (MatchService now does this
whenever a match ends).
"""
from django.db import migrations

ENDED = ("declined", "cancelled", "dropped")


def close_photo_requests(apps, schema_editor):
    Match = apps.get_model("matches", "Match")
    ended = Match.objects.filter(status__in=ENDED)
    ended.filter(photo_request_status="requested").update(
        photo_request_status="none", photo_requested_by=None
    )
    ended.filter(second_photo_request_status="pending").update(second_photo_request_status="none")
    ended.filter(photos_currently_visible=True).update(photos_currently_visible=False)


class Migration(migrations.Migration):
    dependencies = [("matches", "0002_match_photo_privacy_fields")]
    operations = [migrations.RunPython(close_photo_requests, migrations.RunPython.noop)]
