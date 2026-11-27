# Reports and moderation states

Read this before touching `reports/`, or before showing members' content anywhere: the
moderation states and who sees them, and members reporting content. The forum's side:
[forums.md](forums.md).

| Module | Does |
|---|---|
| `moderation.py` | `Visibility` (visible, hidden, removed), `can_see_moderated(user)`, `ModeratedQuerySet` (`visible_to`, `published`, a `parent` that hides children with it), `is_published(obj)` |
| `models.py` | `Report`: reporter (`SET_NULL`), kind (abuse or feedback), reason, details ≤ 1,000, a generic target (`content_type`, `object_id`), `created` |
| `targets.py` | `TARGETS`: what can be reported (`post`, `comment`, `showcase`), how each is found, and its label |
| `services.py` | `report_content`, `has_reported`, `reported_ids`, `AlreadyReported` |
| `forms.py`, `views.py`, `strings.py` | The report page (`ReportForm`, `ReportCreateView`) and its words |
| `admin.py` | Read-only: looking up reports. Acting on them is Phase 15's |

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
content shows "Reported" in place of its Report link. Reports have no status yet: Phase 14
adds statuses and management, Phase 15 acts on them.

## Tests

`tests/test_reports.py`; the visibility walk is in `tests/test_forums_comments.py`.
