# The bug report pages

Read this before changing `templates/reports/bug_*.html`, `templates/reports/partials/` or
the `.rp-*` classes. The rules behind the pages: [../architecture/reports.md](../architecture/reports.md#bug-reports).
The list's controls and pager are the shared ones ([lists.md](lists.md)). The pages sit in
the app shell under the rail's **Reports** item (`reports:*`; the content report page,
`reports:create`, belongs to no rail item).

| Template | Page or part |
|---|---|
| `reports/bug_list.html` | `/reports/bugs/`: New report, the controls (search, Status, Kind, About, Assigned, Sort by), the live region `#bug-list-live`, the list's part |
| `reports/partials/bug_list.html` | `#bug-list`: the heading and count, a row per report (title link, status and kind tags, what it's about, number, date, "Yours", the assignee or "Unassigned", the start of the description), the pager; or "No reports yet" with New report (`data-empty`); or "No reports match" with Clear (`data-no-match`) |
| `reports/bug_form.html` | `/reports/bugs/new/`: About (the engine, then the member's projects; `?about=<slug>` chooses one), Kind (radios), title, what happened, steps, expected, engine version, platform; at the limit, its message above the form (`data-limit`) |
| `reports/bug_detail.html` | `/reports/bugs/<pk>/`: Back to reports, the kind and number, the status tag, "Yours", title, sender and date, the details list (about, status, assignee, version, platform), the text sections; **Handle this report** (`data-manage`) for those who handle it; **Activity** (`#activity`) with the comment form |

Copy lives in `reports/strings.py`; the pages get it as `text`.

- **The list** swaps in place like every list. Its live region is `#bug-list-live`, not
  `#<list_id>-status`: the status filter's select already has the id `bug-list-status`.
- **Handling** is two plain forms that post and come back to the page with a message:
  *Change status* offers only the statuses the report may move to (`next_statuses`; a Closed
  report says its status is final instead), *Assign* offers Nobody and those who may be
  assigned it (name and username). A refusal is the message at the top of the page.
- **Commenting** posts to `bug_comment` and comes back to the new entry
  (`#activity-<pk>`); an empty or over-long comment renders the page with the field's error
  and `aria-invalid`.
- The project page shows **Report a bug** (`?about=<slug>`) to every member, and **Bug
  reports · N open** (`/reports/bugs/?about=<slug>`) to its Owners and Maintainers.
- Everything is plain text: titles, descriptions and comments are escaped, line breaks kept.

## The `.rp-*` classes

Inside the forum's rows and panels (`.fm-rows`, `.fm-row`, `.fm-meta`, `.fm-post`,
`.fm-comment`) and the projects' (`.pj-panel`, `.pj-bar`, `.pj-tag`, `.pj-fields`);
monochrome tokens only, the accent never used.

- `.rp-status` (on a `.pj-tag`): New in ink, Closed and Won't fix faint, the rest outlined.
- `.rp-text` (a heading and its text), `.rp-manage` (the handling panel), `.rp-inline` (a
  select and its button in a row, wrapping on phones).
- Icons: `flag` (the rail item and the list's heading), `history` (Activity).

## Tests

`tests/test_reports_bugs.py` and `tests/test_reports_bugs_list.py` (markup, the list's part,
unique ids). `tests/test_reports_browser.py` (`browser`): an Owner filters the list in place,
confirms, assigns and comments on a report, and the form shows its errors, at 360 and 1280
px, dark and light, with no sideways scroll; screenshots in `screenshots/reports/`.
