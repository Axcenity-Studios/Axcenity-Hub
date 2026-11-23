"""Writes the responsive derivatives of every captured image in the media manifest.

    uv run python manage.py make_media           # only what's missing or out of date
    uv run python manage.py make_media --force   # rewrite every file

See marketing/media.py and docs/frontend/media.md.
"""

from django.core.management.base import BaseCommand

from marketing import content, media


class Command(BaseCommand):
    help = "Write AVIF, WebP and JPEG derivatives of every image in the media manifest."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="rewrite files that are current")

    def handle(self, *args, force: bool = False, **options):
        written = 0
        for item in content.MEDIA.values():
            if not item.source:
                continue
            files = media.build(item.key, item.source, item.source_size, force=force)
            written += len(files)
            self.stdout.write(f"{item.key}: {len(files)} of {len(item.derivatives)} written")
        self.stdout.write(self.style.SUCCESS(f"Done: {written} files written."))
