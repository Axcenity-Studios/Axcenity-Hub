"""Copies the engine's documentation into the Hub's committed snapshot.

    uv run python manage.py sync_engine_docs                  # from AXCENITY_ENGINE_DIR
    uv run python manage.py sync_engine_docs --engine PATH    # from another checkout

Reads documentation/ at the engine's HEAD commit, checks the copy (its git tree hash
and the docs' own build check) and only then replaces documentation/content/. See
documentation/sync.py and docs/frontend/documentation.md.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from documentation import library, sync


class Command(BaseCommand):
    help = "Copy the engine's documentation/ folder (at its HEAD commit) into the snapshot."

    def add_arguments(self, parser):
        parser.add_argument(
            "--engine",
            type=Path,
            default=settings.AXCENITY_ENGINE_DIR,
            help="the engine repository's checkout (default: AXCENITY_ENGINE_DIR)",
        )

    def handle(self, *args, engine: Path, **options):
        try:
            result = sync.sync(engine, settings.DOCS_SNAPSHOT_DIR, validate=library.check_snapshot)
        except sync.SyncError as error:
            raise CommandError(f"Nothing changed: {error}") from error
        library.library.cache_clear()
        short = result.commit[:12]
        if result.changed:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Synced {result.files} files from {short} (tree {result.tree})."
                )
            )
        else:
            self.stdout.write(f"Already current at {short}: nothing changed.")
