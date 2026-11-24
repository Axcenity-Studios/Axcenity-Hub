# Projects and repositories

Read this before touching `projects/`, `accounts/limits.py`, the repository webhook or any
GitHub call made with a member's token. Linking the GitHub account itself:
[github-linking.md](github-linking.md).

| Module | Does |
|---|---|
| `models.Project` | A member's project: name (unique in any case), slug (the name, slugified; follows renames), description |
| `models.RepositoryLink` | The repository linked to a project, as GitHub last described it; `github_id` unique; `hook_id` |
| `models.WebhookDelivery` | Each accepted delivery, to refuse replays (unique per link) |
| `services.py` | `create_project` (the limit), `link_repository`, `refresh_repository`, `webhook_settings`, `unlink_repository` |
| `github.py` | `GET /repos/{owner}/{repo}` with the member's token; `require_permission`; rate limits, budget, ETags |
| `webhooks.py` | Per-link secrets, `verify`, `receive` (replays, events) |
| `accounts/limits.py` | `lock_member` and `LimitReached`: the pattern for every count-based limit |

## Projects

- **Owner only** in this phase: every project URL is a 404 for anyone else (Phase 11 adds
  members). Views fetch through `Project.objects.owned_by(user)`.
- **Names** are unique across the Hub whatever their case: `Project.clean` checks it (and
  that the slug is free, non-empty and not `new` or `hooks`), and the database holds a
  unique index on `LOWER(name)` plus the unique slug. "Space Game", "space game" and
  "space-game" are the same name. Renaming changes the address; old addresses 404.
- Creating, editing and linking need a **verified email** (`VerifiedEmailRequiredMixin`,
  and `ensure_can_contribute` in the services). Deleting and unlinking don't.

## The five-project limit (concurrency-safe)

`create_project` counts the owner's projects and inserts inside one transaction, after
`lock_member(owner)`:

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
| Link a repository | `ADMIN` (asked fresh) |
| Show the webhook's URL and secret | `ADMIN` |
| Refresh the details (button, or a stale page view) | `PULL` (asked fresh) |
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
- **Events:** `ping` (200); `repository` updates the details, `deleted` sets
  `deleted_on_github`; `push` updates `pushed_at` (Unix seconds there). Events about another
  repository id, and other kinds, are 202 and change nothing. A refused delivery rolls back.

**Setting one up** (development needs a tunnel for GitHub to reach the Hub): set
`GITHUB_WEBHOOK_SECRET` (`uv run python -c "import secrets; print(secrets.token_hex(32))"`),
open the project's **Set up webhook**, and add a webhook in the repository's settings with
that payload URL, `application/json`, the secret, and the Pushes and Repositories events.

## Tests

`tests/test_projects.py` (limit with concurrent creation, names, pages, 404s, the gate,
CSRF), `tests/test_projects_github.py` (permission, failures, rate limits, budget, ETags,
duplicates, pages), `tests/test_projects_webhooks.py` (signatures with GitHub's test vector,
replays per link, events, refusals). GitHub is mocked with `responses`;
`tests/fixtures/github/repository.json` is GitHub's documented example repository, trimmed.
