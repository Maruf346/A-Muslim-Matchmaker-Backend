from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_user_is_private_matchmaking_client"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_verified",
            field=models.BooleanField(
                default=False,
                help_text="True when an admin has manually verified the user.",
                verbose_name="Verified",
            ),
        ),
    ]
