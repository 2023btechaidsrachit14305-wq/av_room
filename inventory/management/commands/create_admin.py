import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update a staff admin account without storing a password in source control."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", default="")
        parser.add_argument("--password", default=None, help="Optional password. Omit to enter it securely.")
        parser.add_argument("--first-name", default="AV Room")
        parser.add_argument("--last-name", default="Admin")

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"] or getpass.getpass("Admin password: ")
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")

        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        user.email = options["email"].strip()
        user.first_name = options["first_name"].strip()
        user.last_name = options["last_name"].strip()
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} admin account '{username}'."))
