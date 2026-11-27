"""Demo showcases for trying the showcase list's search, tags, sorting and pages on a
development server: a member may publish only one showcase a day, so a second page can't be
reached by hand.

    uv run python manage.py seed_showcase_demo

Creates 30 showcases (two pages) by the team demo's members (`seed_team_demo`'s alice, bob,
cara, dan, dana and erin, made here too if they don't exist yet, with the same published
password), backdated from two days to about ten weeks ago, with tags and likes on some. Only
alice's newest falls within the last 24 hours, so alice is at the one-a-day limit and the
others can still publish.

Their images are abstract gradients drawn here with Pillow and processed like any upload. They
are placeholders, not engine captures, and each says so in its description and image
description.

It refuses to run unless DEBUG is on, adds nobody to staff, and never changes an account or a
showcase that already exists: running it again changes nothing. Nothing is deleted.
"""

from datetime import timedelta
from io import BytesIO

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from projects.management.commands.seed_team_demo import DEMO_PASSWORD, MEMBERS
from showcases import images, services
from showcases.models import Like, Showcase, Tag

SUBJECTS = (
    ("Lantern-lit courtyard", ("lighting", "ray-tracing")),
    ("Graybox arena", ("graybox", "level-design")),
    ("Foothill meadow", ("terrain", "foliage")),
    ("Decal trail on touch", ("luau", "decals")),
    ("Walk cycle on the default humanoid", ("animation",)),
    ("Mirror hall", ("ray-tracing", "reflections")),
    ("Two-monitor workspace", ("editor",)),
    ("Canyon flyover", ("terrain",)),
    ("Spinning door puzzle", ("luau", "level-design")),
    ("Moss and stone path", ("foliage", "materials")),
)
VARIANTS = ("", " (night)", " (rework)")
DESCRIPTION = (
    "A demo showcase about {subject}, made by seed_showcase_demo to try the showcase list's "
    "search, tags and pages.\n\nThe image is an illustrative placeholder drawn by the seed, "
    "not an engine capture. The engine is in alpha, so details may change."
)
ALT = "Illustrative placeholder: an abstract gradient, not an engine capture."
# Monochrome pairs, so the demo never borrows the accent.
PALETTE = ((28, 28, 30), (64, 66, 70), (110, 112, 118), (160, 162, 168), (210, 210, 214))


def placeholder(index: int) -> SimpleUploadedFile:
    """A 1600 × 900 abstract gradient with a few shapes, different for each index."""
    dark, light = PALETTE[index % 2], PALETTE[2 + index % 3]
    image = Image.linear_gradient("L").resize((1600, 900)).rotate(index * 37 % 360, expand=False)
    image = Image.merge(
        "RGB",
        [image.point(lambda v, a=dark[c], b=light[c]: a + (b - a) * v // 255) for c in range(3)],
    )
    draw = ImageDraw.Draw(image)
    for n in range(3 + index % 4):
        x, y = (180 + n * 310 + index * 53) % 1500, (140 + n * 190 + index * 71) % 800
        r = 50 + (index * 13 + n * 29) % 120
        draw.ellipse((x - r, y - r, x + r, y + r), outline=PALETTE[4 - n % 2], width=6)
    out = BytesIO()
    image.save(out, "PNG")
    return SimpleUploadedFile(f"demo-{index}.png", out.getvalue(), "image/png")


class Command(BaseCommand):
    help = "Create demo showcases for trying the showcase list (development only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_showcase_demo runs only with DEBUG on (a development server).")
        User = get_user_model()
        people = []
        for username, display_name in MEMBERS.items():
            user = User.objects.filter(username__iexact=username).first()
            if user is None:
                user = User.objects.create_user(username, f"{username}@example.com", DEMO_PASSWORD)
                EmailAddress.objects.create(
                    user=user, email=user.email, primary=True, verified=True
                )
                user.profile.display_name = display_name
                user.profile.save(update_fields=["display_name"])
                self.stdout.write(f"Created {username}")
            people.append(user)

        now = timezone.now()
        made = 0
        index = 0
        for variant in VARIANTS:
            for subject, tags in SUBJECTS:
                title = f"{subject}{variant}"
                author = people[index % len(people)]
                # alice's newest is two hours old; everything else is older than a day.
                age = (
                    timedelta(hours=2) if index == 0 else timedelta(days=2 + index * 2, hours=index)
                )
                index += 1
                if Showcase.objects.filter(author=author, title=title).exists():
                    continue
                upload = placeholder(index)
                images.check(upload)
                with transaction.atomic():
                    # Written straight to the database (the one-a-day limit is for members
                    # publishing by hand), with the images processed as any upload is.
                    showcase = Showcase(
                        author=author,
                        title=title,
                        description=DESCRIPTION.format(subject=subject.lower()),
                        image_alt=ALT,
                        slug=next(
                            slug
                            for slug in services.slug_candidates(title)
                            if not Showcase.objects.filter(slug=slug).exists()
                        ),
                    )
                    processed = images.process(upload)
                    showcase.image.save(processed.display.name, processed.display, save=False)
                    showcase.card.save(processed.card.name, processed.card, save=False)
                    showcase.save()
                    showcase.tags.set([Tag.objects.get_or_create(name=name)[0] for name in tags])
                    Showcase.objects.filter(pk=showcase.pk).update(created=now - age)
                    fans = [p for p in people if p != author][: (index * 7) % len(people)]
                    Like.objects.bulk_create(
                        [Like(showcase=showcase, user=fan) for fan in fans], ignore_conflicts=True
                    )
                made += 1
        if made:
            self.stdout.write(self.style.SUCCESS(f"Created {made} demo showcases"))
        else:
            self.stdout.write("The demo showcases already exist: left as they are")
