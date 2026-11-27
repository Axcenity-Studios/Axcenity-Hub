"""Demo bug reports and feedback for trying the reports list, its filters and pages, and a
report's handling, on a development server: a member may send only 5 reports a day.

    uv run python manage.py seed_report_demo

Runs `seed_team_demo` first (its members and "Demo Space Game"; idempotent), then creates 24
reports (two pages) written straight to the database and backdated from an hour to about
eight weeks ago:

- 16 about Demo Space Game, sent by cara (its Viewer), bob (its Maintainer) and alice (its
  Owner), in every status, some assigned to alice or bob. Each status is reached along the
  real transition table, with a timeline entry per step by alice or bob, and a comment on
  some.
- 8 about the Axcenity Engine, sent by dan, dana, cara and erin: new and unassigned, since
  only admins handle engine reports and the seed makes nobody an admin.

At most one report per member falls in the last 24 hours, so each can still send more. It
refuses to run unless DEBUG is on, adds nobody to staff, and never changes a report that
already exists (same sender and title): running it again changes nothing. Nothing is
deleted.
"""

from collections import deque
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from projects.management.commands.seed_team_demo import DEMO_PASSWORD, PROJECT
from projects.models import Project
from reports.models import TRANSITIONS, BugActivity, BugReport, BugStatus

S = BugStatus
# (sender, kind, title, status, assignee) about Demo Space Game, newest first.
PROJECT_REPORTS = (
    ("cara", "bug", "Decals spawn at the origin after Touched", S.NEW, None),
    ("bob", "bug", "Door script errors when the player respawns", S.CONFIRMED, "bob"),
    ("alice", "feedback", "A shortcut to frame the selection in the Viewport", S.NEW, None),
    ("cara", "bug", "Terrain brush leaves seams between chunks", S.IN_PROGRESS, "alice"),
    ("bob", "bug", "Foliage scatter ignores the slope limit", S.RESOLVED, "bob"),
    ("cara", "feedback", "Group the Toolbox results by source", S.WONT_FIX, None),
    ("alice", "bug", "Exported Linux build can't find its packs", S.CLOSED, "alice"),
    ("bob", "bug", "Animation pane drops the last key on loop", S.IN_PROGRESS, "bob"),
    ("cara", "bug", "Reflections flicker on the lake at dusk", S.CONFIRMED, None),
    ("alice", "bug", "Hierarchy loses its order after undo", S.NEW, None),
    ("bob", "feedback", "Remember which panels were docked per monitor", S.CLOSED, None),
    ("cara", "bug", "F5 test run keeps the last frame's decals", S.RESOLVED, "alice"),
    ("alice", "bug", "Spawn decal block has no size input", S.WONT_FIX, None),
    ("bob", "bug", "Graybox materials turn black after a reload", S.NEW, None),
    ("cara", "bug", "Touched fires twice for one collision", S.CONFIRMED, "bob"),
    ("alice", "feedback", "Show the Luau a block makes while wiring it", S.IN_PROGRESS, "alice"),
)
# (sender, kind, title) about the Axcenity Engine, newest first.
ENGINE_REPORTS = (
    ("dan", "bug", "Installer asks for the folder twice on Windows"),
    ("dana", "feedback", "A dark theme for the Console's timestamps"),
    ("erin", "bug", "macOS build opens off screen on a second monitor"),
    ("cara", "bug", "Ambient occlusion is too dark under thin parts"),
    ("dan", "feedback", "Let task.wait take milliseconds"),
    ("dana", "bug", "Path tracer stops after resizing the window"),
    ("erin", "bug", "Scripting docs example for TweenService errors"),
    ("dan", "bug", "Linux build ignores the system's display scaling"),
)
DESCRIPTION = (
    "A demo report made by seed_report_demo to try the reports list and its handling. The "
    "engine is in alpha, so details may change."
)
DECAL_STEPS = (
    "1. Add a Part to the Workspace\n2. Wire When touched → Spawn decal\n3. Press F5 and "
    "touch the part\n\nIts Luau:\npart.Touched:Connect(function(otherPart)\n"
    "    workspace:SpawnDecal(otherPart)\nend)"
)
STEPS = "1. Open the demo project\n2. Do what the title says\n3. Watch what happens"
COMMENT = "Demo comment: still happens on the latest build."


def path_to(status: BugStatus) -> list[BugStatus]:
    """The shortest run of statuses from New to `status` along the transition table."""
    paths = deque([[BugStatus.NEW]])
    while paths:
        path = paths.popleft()
        if path[-1] == status:
            return path
        paths.extend([*path, step] for step in TRANSITIONS[path[-1]] if step not in path)
    raise ValueError(status)


class Command(BaseCommand):
    help = "Create demo bug reports and feedback (development only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_report_demo runs only with DEBUG on (a development server).")
        call_command("seed_team_demo", stdout=self.stdout)
        User = get_user_model()
        people = {user.username.lower(): user for user in User.objects.all()}
        project = Project.objects.get(name=PROJECT)
        handlers = [people["alice"], people["bob"]]
        now = timezone.now()
        made = 0
        with transaction.atomic():
            rows = [(*row, project) for row in PROJECT_REPORTS] + [
                (sender, kind, title, S.NEW, None, None) for sender, kind, title in ENGINE_REPORTS
            ]
            # Interleaved so both pages hold both kinds of report.
            order = sorted(range(len(rows)), key=lambda i: (i % 3, i))
            for place, index in enumerate(order):
                sender, kind, title, status, assignee, about = rows[index]
                submitter = people[sender]
                if BugReport.objects.filter(submitter=submitter, title=title).exists():
                    continue
                # The newest an hour ago, each later one a day and a half further back: one
                # report per member at most in the last day.
                created = now - timedelta(hours=1 + 36 * place)
                report = BugReport.objects.create(
                    project=about,
                    submitter=submitter,
                    kind=kind,
                    title=title,
                    description=DESCRIPTION,
                    steps=(DECAL_STEPS if "ecal" in title else STEPS) if kind == "bug" else "",
                    engine_version="0.4.0-alpha.2" if kind == "bug" else "",
                    platform=("windows", "macos", "linux")[place % 3] if kind == "bug" else "",
                    status=status,
                    assignee=people[assignee] if assignee else None,
                )
                moment = created
                statuses = path_to(BugStatus(status))
                for step, (old, new) in enumerate(zip(statuses, statuses[1:], strict=False)):
                    moment += timedelta(hours=2)
                    entry = BugActivity.objects.create(
                        report=report,
                        actor=handlers[step % 2],
                        kind=BugActivity.Kind.STATUS,
                        old_status=old,
                        new_status=new,
                    )
                    BugActivity.objects.filter(pk=entry.pk).update(created=moment)
                if assignee:
                    moment += timedelta(hours=1)
                    entry = BugActivity.objects.create(
                        report=report,
                        actor=people["alice"],
                        kind=BugActivity.Kind.ASSIGNED,
                        assignee=people[assignee],
                    )
                    BugActivity.objects.filter(pk=entry.pk).update(created=moment)
                if place % 4 == 1:
                    moment += timedelta(minutes=30)
                    entry = BugActivity.objects.create(
                        report=report, actor=submitter, kind=BugActivity.Kind.COMMENT, body=COMMENT
                    )
                    BugActivity.objects.filter(pk=entry.pk).update(created=moment)
                BugReport.objects.filter(pk=report.pk).update(created=created, updated=moment)
                made += 1
        total = len(PROJECT_REPORTS) + len(ENGINE_REPORTS)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {made} demo reports created ({total - made} already there). Sign in "
                f"with <username>@example.com and the password {DEMO_PASSWORD}"
            )
        )
