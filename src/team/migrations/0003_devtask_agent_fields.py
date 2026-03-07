from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("team", "0002_project_github_repo_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="devtask",
            name="pr_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="devtask",
            name="branch_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="devtask",
            name="agent_log",
            field=models.TextField(blank=True),
        ),
    ]
