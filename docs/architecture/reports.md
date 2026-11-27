# Reports, bug reports and moderation states

Read this before touching `reports/`, or before showing members' content anywhere: the
moderation states and who sees them, members reporting content, and bug reports and feedback
with their handling. The forum's side: [forums.md](forums.md). The bug pages:
[../frontend/reports.md](../frontend/reports.md).

| Module | Does |
|---|---|
| `moderation.py` | `Visibility` (visible, hidden, removed), `can_see_moderated(user)`, `ModeratedQuerySet` (`visible_to`, `published`, a `parent` that hides children with it), `is_published(obj)` |
| `models.py` | `Report`: reporter (`SET_NULL`), kind (abuse; feedback is a `BugReport` kind instead), reason, details ≤ 1,000, a generic target (`content_type`, `object_id`), `created`. `BugReport`, `BugStatus`, `TRANSITIONS`, `allows_transition`, `OPEN_STATUSES`, `BugActivity`, and `BugReportQuerySet` (`visible_to`, `managed_by`) |
| `targets.py` | `TARGETS`: what can be reported (`post`, `comment`, `showcase`), how each is found, and its label |
| `services.py` | `report_content`, `has_reported`, `reported_ids`, `AlreadyReported` |
| `bugs.py` | Bug reports: `submit` (the gate, membership, validation, the daily limit), `change_status`, `assign`, `assignable`, `comment`, `can_manage`, `limit_message`, `reportable_projects`, `release_assignments`; `TransitionRefused`, `AssigneeRefused` |
| `listing.py` | The reports list: `for_member(user, visible)` (search, status, kind, about, assigned, sorts) |
| `forms.py`, `views.py`, `strings.py` | The report page (`ReportForm`, `ReportCreateView`); the bug pages (`BugReportForm`, `BugStatusForm`, `BugAssignForm`, `BugCommentForm`; `BugListView`, `BugCreateView`, `BugDetailView`, `BugStatusView`, `BugAssignView`, `BugCommentView`) and their words |
| `management/commands/seed_report_demo.py` | 24 demo reports in every status, with timelines (development only, idempotent) |
| `admin.py` | Read-only: looking up reports and bug reports with their timelines. Acting on reported content is Phase 15's; bug reports change only through `bugs.py` |

## Moderation states

- Content with a `state` uses a `ModeratedQuerySet`. Only moderation (Phase 15) sets the
  state; nothing in the app or the admin changes it yet (in development, the shell does).
- **`visible_to(user)`** is every read: everything for staff, and otherwise visible content
  whose `parent` (a comment's post) is visible too. Hidden and removed content is missing from
  lists, counts and pages, and its URLs are a 404, for its author too.
- **`published()`** is every interaction (comment, rate, report): visible content under a
  visible parent, for staff too.
- **`can_see_moderated(user)`** is the one place staff access is decided (`is_staff`). Staff
  see hidden and removed content marked with its state (`data-state`, "Hidden", "Removed").
- New content kinds give their model a `state` and their queryset `ModeratedQuerySet`, as
  showcases do; no view writes its own rule.

## Reporting

| Rule | Where |
|---|---|
| Members only, verified | `VerifiedEmailRequiredMixin`; `report_content` calls `ensure_can_contribute` |
| Someone else's published post, comment or showcase; otherwise **404** (an unknown kind, a missing, hidden or own item) | `Target.find`, before sign-in or verification run; `report_content` raises `PermissionDenied` for your own |
| Once per member per item | The database: a unique constraint on (reporter, content type, object id) for abuse reports (`one_abuse_report_per_member_per_target`). `report_content` saves inside a savepoint and turns the `IntegrityError` into `AlreadyReported`, so simultaneous duplicates give one report and no error page. Feedback (Phase 14) isn't limited |
| A reason; details required for "Something else" | `ReportForm` |
| Deleted with its target; kept (reporter emptied) when the reporter's account is deleted | `GenericRelation` on the target; `SET_NULL` |

The page (`/reports/<kind>/<pk>/`, `templates/reports/form.html`) names the content, offers
the reasons as radio buttons, and says so instead when the member has already reported it.
After sending, the member goes back to the content with "Thanks for the report", and the
content shows "Reported" in place of its Report link. Abuse reports have no status: Phase 15
acts on them.

## Bug reports

A `BugReport` is a bug or feedback (`kind`) about a member's project or, with no project, the
Axcenity Engine itself. A bug needs a title, what happened, the steps to reproduce it, the
engine version (`0.4`, `0.4.0`, `v0.4.0`, `0.4.0-alpha.2`) and the platform (Windows, macOS,
Linux, Other); feedback needs a title and what happened. What was expected is optional. Text
is trimmed, so whitespace alone is empty (`BugReport.clean`; its errors use the code
`missing`, since a form swaps a `required` error for its generic message).

| Who | Sees it (opens, finds in the list, comments) | Handles it (status, assignee) |
|---|---|---|
| The submitter | ✓ (also after leaving the project) | |
| The project's Owners and Maintainers (`Action.MANAGE_REPORTS`) | ✓ project reports | ✓ project reports |
| Admins (`is_staff`) | ✓ every report | ✓ every report |
| Anyone else, signed out included | **404** | **404** |

- **One rule for every query:** `BugReport.objects.visible_to(user)` and `managed_by(user)`.
  Each view finds the report through one of them before sign-in or verification run
  (`BugLookupMixin`), so a report someone can't reach reads as missing. The services re-read
  the report under its row lock through the same querysets.
- **Sending** (`bugs.submit`): verified members (`ensure_can_contribute`), about the engine or
  a project they're a member of in any role (the form offers only those; the service checks
  again). **5 a day:** a rolling 24 hours of the member's reports of either kind, counted
  under `lock_member` with `next_allowed`, as every windowed limit.
- **Statuses** change only along `TRANSITIONS`; anything else (an unknown value, the status
  it has, anything from Closed) raises `TransitionRefused` and changes nothing:

  | From | To |
  |---|---|
  | New | Confirmed, Won't fix |
  | Confirmed | In progress, Won't fix |
  | In progress | Resolved, Confirmed |
  | Resolved | Closed, In progress |
  | Won't fix | Closed, New |
  | Closed | (final) |

  "Open" (the list's filter, the project page's count) is New, Confirmed or In progress.
  The database also refuses a status or kind outside the choices (check constraints).
- **Assignees** handle the report: a project report's Owners and Maintainers, an engine
  report's admins (`bugs.assignable`); anyone else is `AssigneeRefused`. Assigning to whoever
  has it already records nothing. When a member stops handling a project's reports (their
  role drops to Viewer, they're removed, or they leave), `projects.teams` calls
  `release_assignments` in the same transaction, so an assignee always handles the report.
  Deleted accounts leave reports unassigned (`SET_NULL`), and their reports stay with "A
  deleted member" as the sender.
- **The timeline** (`BugActivity`): every status change, assignment and comment, with its
  actor and time, oldest first; written only by `bugs.py`. Comments are for anyone who sees
  the report, verified, 1 to 2,000 characters; they move the report up "Recently updated".
- Deleting a project deletes its reports. Status changes and assignments need no verified
  email (like role changes); sending and commenting do.

## Tests

`tests/test_reports.py`; the visibility walk is in `tests/test_forums_comments.py`. Bug
reports: `tests/test_reports_bugs.py` (the transition table and the access matrix, both
test-first), `tests/test_reports_bugs_list.py`, `tests/test_reports_browser.py`.
