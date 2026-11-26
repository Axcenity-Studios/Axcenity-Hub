"""Demo posts for trying the forum's search, filters, sorting and pages on a development
server: a member may publish only 5 posts a day, so a second page can't be reached by hand.

    uv run python manage.py seed_forum_demo

Creates 45 posts (three pages) by the team demo's members (`seed_team_demo`'s alice, bob,
cara, dan, dana and erin, made here too if they don't exist yet, with the same published
password), written straight to the database and backdated from an hour to about ten weeks
ago, with comments and ratings on some and none on others, so every filter and order shows
a difference. One post by each member falls in the last 24 hours, so each can still post.

It refuses to run unless DEBUG is on, adds nobody to staff, and never changes an account or
a post that already exists: running it again changes nothing. Nothing is deleted.
"""

from datetime import timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from forums.models import Comment, ForumPost, Rating
from projects.management.commands.seed_team_demo import DEMO_PASSWORD, MEMBERS

TOPICS = (
    "spawning a decal when a part is touched",
    "scripting doors in Luau",
    "sculpting terrain hills",
    "scattering foliage on terrain",
    "ray-traced reflections",
    "docking panels across two monitors",
    "keying a walk animation",
    "exporting a desktop build",
    "testing a level with F5",
    "organising the Hierarchy",
    "finding textures with the Toolbox",
    "building engine-ready packs",
    "connecting Touched events",
    "tuning ambient occlusion",
    "laying out a graybox level",
)
TITLES = ("How do I get started with {topic}?", "Tips for {topic}", "Show and tell: {topic}")
BODY = (
    "A demo post about {topic}, made by seed_forum_demo to try the forum's search, filters "
    "and pages.\n\nThe engine is in alpha, so details may change."
)
DECAL = (
    "\n\nThe blocks: When touched → Spawn decal. In Luau:\n"
    "part.Touched:Connect(function(otherPart)\n    workspace:SpawnDecal(otherPart)\nend)"
)
COMMENT = "Demo comment {number} on this post."


def demo_posts() -> list[tuple[str, str]]:
    """Each demo post's title and body, newest first."""
    posts = []
    for form in TITLES:
        for topic in TOPICS:
            body = BODY.format(topic=topic) + (DECAL if "decal" in topic else "")
            posts.append((form.format(topic=topic), body))
    return posts


class Command(BaseCommand):
    help = "Create demo forum posts for trying search, filters and pages (development only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_forum_demo runs only with DEBUG on (a development server).")
        User = get_user_model()
        now = timezone.now()
        with transaction.atomic():
            people = []
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
                people.append(user)

            made = 0
            for index, (title, body) in enumerate(demo_posts()):
                author = people[index % len(people)]
                if ForumPost.objects.filter(author=author, title=title).exists():
                    continue
                # An hour ago, then further apart: six in the last day (one per member),
                # about a third within a week, the oldest some ten weeks back.
                created = now - timedelta(hours=1 + 0.9 * index**2)
                post = ForumPost.objects.create(author=author, title=title, body=body)
                ForumPost.objects.filter(pk=post.pk).update(created=created)
                others = [person for person in people if person != author]
                for number in range(index * 7 % 5):  # 0 to 4 comments
                    comment = Comment.objects.create(
                        post=post,
                        author=others[number % len(others)],
                        body=COMMENT.format(number=number + 1),
                    )
                    Comment.objects.filter(pk=comment.pk).update(
                        created=created + timedelta(minutes=10 * (number + 1))
                    )
                if index % 3:  # every third post stays unrated
                    for place, rater in enumerate(others[: 1 + index % 4]):
                        Rating.objects.create(
                            post=post, user=rater, score=1 + (index + 2 * place) % 5
                        )
                made += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {made} demo posts created ({len(demo_posts()) - made} already there). "
                f"Sign in with <username>@example.com and the password {DEMO_PASSWORD}"
            )
        )
