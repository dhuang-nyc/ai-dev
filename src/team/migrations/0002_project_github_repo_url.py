from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("team", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="github_repo_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
