import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create admin superuser if it does not exist"

    def handle(self, *args, **kwargs):
        User = get_user_model()
        username = "admin"
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin")
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username, "daisyhuang1993@gmail.com", password
            )
            self.stdout.write(
                self.style.SUCCESS(f"Superuser '{username}' created.")
            )
        else:
            self.stdout.write(f"Superuser '{username}' already exists.")
