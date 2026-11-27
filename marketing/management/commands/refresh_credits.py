"""Copies the engine's LICENSE and NOTICE and regenerates the credits lists.

    uv run python manage.py refresh_credits                  # from AXCENITY_ENGINE_DIR
    uv run python manage.py refresh_credits --engine PATH    # from another checkout

A test run already does this when the lists are stale (tests/conftest.py); run it by hand
to record the engine's latest commit regardless. Needs git and cargo, never the network.
See marketing/credits.py and docs/frontend/credits.md.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from marketing import credits


class Command(BaseCommand):
    help = "Copy the engine's LICENSE and NOTICE (at HEAD) and regenerate /credits/'s lists."

    def add_arguments(self, parser):
        parser.add_argument(
            "--engine",
            type=Path,
            default=settings.AXCENITY_ENGINE_DIR,
            help="the engine repository's checkout (default: AXCENITY_ENGINE_DIR)",
        )

    def handle(self, *args, engine: Path, **options):
        try:
            result = credits.refresh(engine)
        except credits.CreditsError as error:
            raise CommandError(f"Nothing changed: {error}") from error
        for label, crates in (("New", result.added), ("Gone", result.removed)):
            if crates:
                self.stdout.write(f"{label} crates ({len(crates)}): {', '.join(crates)}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Credits at engine {result.commit[:12]}: {result.crates} crates, "
                f"{result.packages} Python packages."
            )
        )
