# Projects and repositories

Read this before touching `projects/`, `accounts/limits.py`, the repository webhook or any
GitHub call made with a member's token. Linking the GitHub account itself:
[github-linking.md](github-linking.md).

| Module | Does |
|---|---|
| `models.Project` | A project: name (unique in any case), slug (the name, slugified; follows renames), description. No owner field: its team says who owns it |
| `models.ProjectMembership` | A member of a project's team in one `Role` (Owner, Maintainer, Viewer); one per member and project |
| `models.ProjectInvitation` | An Owner's pending invitation for a member, in a role; one per member and project |
| `models.PERMISSIONS` | Each `Action` and the roles allowed it; `allows(role, action)`; `Project.objects.allowing(user, action)` |
| `models.RepositoryLink` | The repository linked to a project, as GitHub last described it; `github_id` unique; `hook_id` |
| `models.WebhookDelivery` | Each accepted delivery, to refuse replays (unique per link) |
| `services.py` | `create_project` (the limit), `owned_count`, `link_repository`, `refresh_repository`, `webhook_settings`, `unlink_repository` |
| `teams.py` | `find_members` (the invite field's suggestions), `invite`, `accept`, `decline`, `cancel`, `change_role`, `remove`, `leave`: transactional, the last Owner kept |
| `management/commands/seed_team_demo.py` | Demo members and a demo project for trying teams (development only) |
| `github.py` | `GET /repos/{owner}/{repo}` with the member's token; `require_permission`; rate limits, budget, ETags |
| `webhooks.py` | Per-link secrets, `verify`, `receive` (replays, events) |
| `setup.py` | The four setup steps' states for the project page ([../frontend/projects.md](../frontend/projects.md)) |
| `accounts/limits.py` | `lock_member` and `LimitReached`: the pattern for every count-based limit |

## Projects and teams

- **Roles.** Every view names the `Action` it needs and fetches through
  `Project.objects.allowing(user, action)`: anyone whose role doesn't allow it (non-members
  included) gets a **404**, never a 403. The services check the same table.

  | Action | Owner | Maintainer | Viewer |
  |---|---|---|---|
  | View the project, its repository's details and its team | ✓ | ✓ | ✓ |
  | Edit the description; refresh the repository from GitHub | ✓ | ✓ | |
  | Rename; delete; manage the team; link, unlink, the setup and the webhook | ✓ | | |
  | See and handle the project's bug reports (`MANAGE_REPORTS`; [reports.md](reports.md#bug-reports)) | ✓ | ✓ | |
  | Leave | ✓ (another Owner stays) | ✓ | ✓ |

  Renaming goes through the edit page: a Maintainer's form (`DescriptionForm`) has no name, so
  a posted one is ignored. A stale repository is refreshed on view only for roles that may
  refresh, with their own GitHub permission; Viewers see the stored details.
- **Names** are unique across the Hub whatever their case: `Project.clean` checks it (and
  that the slug is free, non-empty and not `new` or `hooks`), and the database holds a
  unique index on `LOWER(name)` plus the unique slug. "Space Game", "space game" and
  "space-game" are the same name. Renaming changes the address; old addresses 404.
- Creating, editing, linking and inviting need a **verified email** (`VerifiedEmailRequiredMixin`,
  and `ensure_can_contribute` in the services). Deleting, unlinking, answering an invitation,
  role changes and leaving don't.

## Teams (`teams.py`)

- **Finding someone to invite** (`find_members`, `GET /projects/<slug>/members/search/?q=`):
  Owners only (others 404), at least 2 characters, at most 6 active members whose username or
  display name starts with the query (any case), an exact username first. Each is marked
  available, already in the team, already invited, or you. Emails are never matched or shown;
  the response is never cached.
- **Invitations** are by username (case-insensitive; active members only), as any role, up to
  10 at once (`invite_many`; `parse_usernames` reads every `username` value sent, each
  possibly comma-separated, repeats once). Each is its own transaction: the valid ones are
  sent and each refusal is reported by name; too many, none, or an invalid role sends none. The
  inviter can't invite themselves, a member, or someone already invited. Only the invitee
  accepts or declines (a 404 for anyone else); Owners cancel. An invitation is deleted once
  answered or cancelled. No email: the invitee sees it on `/projects/`.
- **The last Owner.** A project always has at least one Owner. Stepping down, removing the
  last Owner or leaving as them is refused (`TeamError`, `strings.LAST_OWNER`). Deleting the
  account of a project's last Owner is refused too: `ProjectMembership.user`'s `on_delete` is
  `models.protect_last_owner`, which raises `ProtectedError` (the admin lists it as the
  reason). Ownership never moves by itself: an Owner makes another member an Owner, then steps
  down, or deletes the project.
- **Bug report assignments** follow the role: dropping to Viewer, being removed and leaving
  unassign the member from the project's bug reports in the same transaction
  (`reports.bugs.release_assignments`).
- **Transactions and locks.** Every change runs in one transaction that locks the project row
  (`SELECT … FOR UPDATE`; SQLite's IMMEDIATE transactions serialize instead), then re-reads
  the actor's role and the membership or invitation it changes. Locks go in one order, the
  project then a member (`lock_member`), so changes queue and never deadlock. Account deletion
  locks the projects too when it runs in a transaction (the admin's does).
- **Database constraints:** one membership and one invitation per member and project (unique
  together), and a valid role (check constraints).
- **Becoming an Owner counts against the limit.** Accepting an Owner invitation or being made
  an Owner takes the member's lock and counts their Owner memberships; at five it's refused
  (`LimitReached`) and nothing changes: the invitation stays pending, the role stays.
- **The admin** shows teams read-only; they change only through `teams.py`.
- **Migrations:** `0003_teams` makes every project's `owner` its first Owner member (the
  owner column goes nullable first, so it rolls back); `0004` drops the column.

## Demo members (development)

`uv run python manage.py seed_team_demo` creates alice (Owner of "Demo Space Game"), bob
(Maintainer), cara (Viewer), erin (invited as Maintainer), and dan and dana (in no project),
each with a verified `<username>@example.com` and the published password
`axcenity-team-demo`. It refuses unless `DEBUG` is on, grants no staff, superuser, group or
permission, never changes an account or project that already exists, and deletes nothing.

## The five-project limit (concurrency-safe)

`create_project` counts the member's Owner memberships (`owned_count`) and inserts the project
and its Owner membership inside one transaction, after `lock_member(owner)`:

- **PostgreSQL:** `SELECT … FOR UPDATE` on the owner's `auth_user` row. Creations by the same
  member queue; other members never wait. Other members' projects never count.
- **SQLite** (development and tests): no row locks, so `DATABASES["default"]["OPTIONS"]
  ["transaction_mode"] = "IMMEDIATE"` makes every transaction take the write lock when it
  begins, which serializes them. (These `OPTIONS` are SQLite's; PostgreSQL's settings drop them.)
- A name race (two members, one name, same moment) ends in the unique index; the service
  turns its `IntegrityError` into the name's form error.

Later count-based limits (posts a day, comments a minute) follow the same shape: atomic,
`lock_member`, count, raise `LimitReached`, insert.

## GitHub permission

**The authorization model.** The GitHub link is an OAuth App with **no scopes**, which GitHub
documents as "read-only access to public information (including … repository info)". The
Hub asks for no more:

- `GET /repos/{owner}/{repo}` has no scope requirement, and its reply carries `permissions`
  (`admin`, `maintain`, `push`, `triage`, `pull`): the member's own role. That's the check.
  `admin`, `push` and `pull` must be booleans, or the permission is **unverifiable**.
- Endpoints that list or check collaborators need `repo` and `read:org`; managing hooks needs
  `admin:repo_hook`. The Hub uses none of them: owners add the webhook by hand.
- So only **public** repositories can be linked (a private one is a 404 to this token).

**Before every repository-dependent action** the services call
`github.require_permission(user, full_name, needed)`:

| Action | Needs |
|---|---|
| Link a repository (Owners) | `ADMIN` (asked fresh) |
| Show the webhook's URL and secret (`?webhook=show`; records `webhook_shown_at`) | `ADMIN` |
| Refresh the details (Owners and Maintainers: button, or a stale page view) | `PULL` (asked fresh) |
| Unlink, delete the project | Nothing: the Hub's own records; GitHub isn't asked |

- A member's check is cached per member and repository with its `checked_at`, and reused only
  while `now - checked_at < GITHUB_PERMISSION_TTL` (**60 s**), compared explicitly, never by
  trusting the cache to expire it. **A permission GitHub revokes keeps working for up to 60 s.**
- Past that, GitHub is asked again with the last reply's ETag; a 304 means nothing changed,
  `permissions` included. `fresh=True` skips the reuse (still conditional).
- **Fails closed:** no linked account, a needs-reconnect link, a 401 (marks the link, Phase 9's
  prompt), 403 or 404, a rate limit, a 5xx, a timeout, or a reply without a valid
  `permissions` all refuse the action, and any failure drops the stored check.
- `services.RepositoryError` carries the `Reason` and the message (`strings.REFUSED`).

## Rate limits, budget and outages

- Every reply's `X-RateLimit-Remaining` / `X-RateLimit-Reset`, and `Retry-After` on a 403 or
  429 (or a 403 whose message says "rate limit"), set a **per-member backoff** (1 s to 1 h):
  GitHub isn't asked for that member until it ends. A 200 that spent the last request is used,
  then backs off.
- A **budget** of `GITHUB_CALLS_PER_MEMBER_PER_HOUR` (60) calls per member per clock hour,
  counted in the shared cache.
- The project page fetches details older than `GITHUB_REPOSITORY_REFRESH` (1 h). When GitHub
  refuses or fails, it shows the stored details with a notice: when they're from, why, and
  when to retry after a rate limit. Never an error page.
- GitHub's reply is untrusted: `github.parse_details` checks each field (positive int id,
  `owner/name`, `html_url` exactly `https://github.com/<full_name>`, booleans).

## Duplicate links

`RepositoryLink.github_id` (GitHub's numeric id, stable across renames) is unique, and a
project has one link (`OneToOneField`). A second attempt anywhere gets "This repository is
already linked to a Hub project." without naming the project. A race ends in the unique
index and the same message. Refreshing a link whose name now answers with another id is
refused (`REPOSITORY_REPLACED`).

## Webhooks

`POST /projects/hooks/github/<hook_id>/`: the Hub's **only** CSRF-exempt view (GitHub can't
send a token; the signature authenticates instead). Public by necessity.

- **Secrets:** `GITHUB_WEBHOOK_SECRET` (environment) is the root. A link's secret is
  `HMAC-SHA256(root, "axcenity-hub:repository-webhook:<hook_id>")`, shown only on the
  webhook page after an `ADMIN` check, never stored, never in the admin. One repository's
  secret can't sign another's deliveries. Changing the root changes every link's secret.
- **Order:** unknown hook or webhooks off → 404. Then the signature: `sha256=` and 64 hex
  digits, `hmac.compare_digest` against the raw body → otherwise **403**. Only then are the
  headers and body read (bad `X-GitHub-Event`, `X-GitHub-Delivery` or JSON → 400). Bodies
  over `DATA_UPLOAD_MAX_MEMORY_SIZE` → 413.
- **Replays:** GitHub signs the body but not `X-GitHub-Delivery`, so both the delivery id and
  the body's SHA-256 are unique **per link** (409, nothing applied). The same body or id for
  another link isn't a replay. Rows go when the link does.
- **Events:** every accepted delivery sets `webhook_at` (and `first_webhook_at` once), which
  completes the setup checklist. `ping` (200); `repository` updates the details, `deleted` sets
  `deleted_on_github`; `push` updates `pushed_at` (Unix seconds there). Events about another
  repository id, and other kinds, are 202 and change nothing. A refused delivery rolls back.

**The payload URL** is built on `HUB_PUBLIC_URL` when it's set (the Hub's address on the
internet: production's origin, or a tunnel's in development; its host is added to
`ALLOWED_HOSTS`, and settings refuse anything but a scheme and host), else on the address the
page was opened at.

**Setting one up** (development needs a tunnel for GitHub to reach the Hub): set
`GITHUB_WEBHOOK_SECRET` (`uv run python -c "import secrets; print(secrets.token_hex(32))"`)
and `HUB_PUBLIC_URL` (the tunnel's `https://` address), restart,
open the project's checklist at step 3 (**Show webhook settings**), and add a webhook in the
repository's settings with that payload URL, `application/json`, the secret, and the Pushes
and Repositories events. Members get the same walkthrough as each step's help on the
checklist.

## Tests

`tests/test_projects.py` (limit with concurrent creation, names, pages, 404s, the gate,
CSRF), `tests/test_projects_teams.py` (the role matrix and the last Owner (TDD), invitations,
the limit on becoming an Owner, re-checks, constraints, pages per role, the migration), `tests/test_projects_github.py` (permission, failures, rate limits, budget, ETags,
duplicates, pages), `tests/test_projects_webhooks.py` (signatures with GitHub's test vector,
replays per link, events, refusals), `tests/test_projects_setup.py` and
`tests/test_projects_browser.py` (the pages: [../frontend/projects.md](../frontend/projects.md)). GitHub is mocked with `responses`;
`tests/fixtures/github/repository.json` is GitHub's documented example repository, trimmed.
