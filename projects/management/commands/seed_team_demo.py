"""Demo members and a demo project, for trying teams on a development server.

    uv run python manage.py seed_team_demo

Creates, if they don't exist yet, these members, each with a verified email
(<username>@example.com) and the published password `DEMO_PASSWORD`:

- alice: Owner of "Demo Space Game"
- bob: its Maintainer
- cara: its Viewer
- erin: invited to it as a Maintainer, not yet answered
- dan, dana: in no project, to invite (both start with "da", to try the invite field's
  suggestions)

It refuses to run unless DEBUG is on, adds nobody to staff, superusers, groups or
permissions, and never changes an account or project that already exists (so running it
again changes nothing, and a real account named bob keeps its password). Nothing is deleted.
"""

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from projects.models import Project, ProjectInvitation, ProjectMembership

# Published on purpose: these accounts exist only on development servers.
DEMO_PASSWORD = "axcenity-team-demo"
PROJECT = "Demo Space Game"
MEMBERS = {
    "alice": "Alice Owner",
    "bob": "Bob Maintainer",
    "cara": "Cara Viewer",
    "dan": "Dan Newcomer",
    "dana": "Dana Newcomer",
    "erin": "Erin Invited",
}


class Command(BaseCommand):
    help = "Create demo members and a demo project for trying teams (development only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_team_demo runs only with DEBUG on (a development server).")
        User = get_user_model()
        with transaction.atomic():
            people = {}
            for username, display_name in MEMBERS.items():
                user = User.objects.filter(username__iexact=username).first()
                if user is None:
                    user = User.objects.create_user(
                        username, f"{username}@example.com", DEMO_PASSWORD
                    )
                    EmailAddress.objects.create(
                        user=user, email=user.email, primary=True, verified=True
                    )
                    user.profile.display_name = display_name
                    user.profile.save(update_fields=["display_name"])
                    self.stdout.write(f"Created {username}")
                else:
                    self.stdout.write(f"{username} already exists: left as it is")
                people[username] = user

            if Project.objects.filter(name__iexact=PROJECT).exists():
                self.stdout.write(f"{PROJECT} already exists: left as it is")
            else:
                project = Project.objects.create_with_owner(
                    people["alice"],
                    name=PROJECT,
                    description="A demo project for trying teams.",
                )
                for username, role in [("bob", "maintainer"), ("cara", "viewer")]:
                    ProjectMembership.objects.create(
                        project=project, user=people[username], role=role
                    )
                ProjectInvitation.objects.create(
                    project=project,
                    invitee=people["erin"],
                    role="maintainer",
                    invited_by=people["alice"],
                )
                self.stdout.write(f"Created {PROJECT}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Sign in with <username>@example.com and the password {DEMO_PASSWORD}"
            )
        )
