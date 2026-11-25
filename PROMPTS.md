# PROMPTS.md — AI Usage Log

This file is the record of AI use on this codebase. At the end of every
agent session, direct the agent to write the session log with this prompt:

> Append a session log to PROMPTS.md at the repo root, under today's date,
> newest entry at the top. Record every prompt I gave you this session, in
> order, including any corrections. End the entry with a short summary:
> the outcome, any places where I deviated from a recommended answer or
> asked follow-up questions, and anything that went sideways.

Two rules:

- Entries are added only by that prompt, never unprompted.
- New entries go at the top. Never rewrite or delete an old entry — the
  log is part of your work, and an honest log of a session that went
  sideways is worth more than a tidy one.

Each entry has this shape:

    ## YYYY-MM-DD — <one-line summary>

    ### Prompts
    1. ...

    ### Summary
    - **Outcome:** what was built and what was kept
    - **Deviations:** recommendations overridden, follow-up questions asked
    - **Sideways:** failures, wrong turns, and how they were caught

## 2026-11-25 — Axcenity Hub: Phase 12B/17, Comments, ratings, limits and moderation hooks

### Prompts

1. The `/implement` skill, given `axcenity-hub phase  12B`.
2. "Looks good I would just reccomed the 4 following changes" with a pasted list: 1. rating
   averages from individual 1–5 integer ratings, from visible ratings only, shown to one
   decimal place, never exposing a hidden or removed post's rating to non-staff;
   2. `lock_member` must serialize simultaneous submissions from one member, so a sixth can't
   slip through (database locking, not an in-memory counter); 3. one report per member per
   target as a database uniqueness constraint, with simultaneous duplicates handled
   gracefully; 4. visibility filtering centralized in reusable querysets or shared functions,
   with staff access controlled only through `can_see_moderated`. "Other than that continue
   to TDD only stopping on red".
3. "go ahead, make it pass and move to next red phase" (after TDD behavior 1 was red).
4. "go ahead, make it pass and finish the phase" (after TDD behavior 2 was red).

### Summary

- **Outcome:** Comments on forum posts (add, and delete your own), 1–5 star ratings (one
  per member per post, changeable and clearable, not on your own post), the posting limits
  (5 posts in 24 hours, 5 comments a minute, rolling windows under the member's lock), and
  the moderation hooks: a `state` on posts and comments (visible, hidden, removed) that only
  staff see past, and a new `reports` app where members report someone else's post or comment
  once each. Rating and commenting work in place through HTMX with focus following each swap,
  and everything also works without JavaScript. 1352 fast tests and 108 browser tests pass;
  Ruff is clean. The one failing test is still
  `test_download.py::test_the_copied_license_and_notice_match_the_engines`: the engine's
  NOTICE changed again today (commit 3a43b6f5), and `refresh_credits` is outside this phase.
- **Changes:**
  - `reports/` (new) — `moderation.py` (`Visibility`, `can_see_moderated`,
    `ModeratedQuerySet.visible_to` / `published` with a `parent` so a hidden post hides its
    comments, `is_published`), `models.py` (`Report`, generic target, a conditional unique
    constraint for abuse reports), migration `0001_initial`, `targets.py` (post and comment),
    `services.py` (`report_content` turning the constraint's `IntegrityError` into
    `AlreadyReported`, `has_reported`, `reported_ids`), `forms.py`, `views.py`, `urls.py`,
    `strings.py`, a read-only `admin.py`.
  - `forums/models.py` — `Comment`, `Rating` (unique per member and post, score 1–5 as a
    check constraint), `state` on posts and comments, `with_stats`, author-and-time indexes,
    `MaxLengthValidator` on bodies; migration `0002_comments_ratings_and_states`.
  - `forums/services.py` — the post limit, `add_comment` with its limit, `delete_comment`,
    `rate_post`, `clear_rating`. `accounts/limits.py` — `next_allowed` and `wait_words`.
  - `forums/views.py`, `urls.py`, `forms.py`, `strings.py`, `admin.py` — comment, rate and
    comment-delete views; every read through `visible_to`, every interaction through
    `published()`; the limit as a form error that keeps the draft.
  - Templates — `rating.html`, `comments.html`, `comment.html`,
    `comment_confirm_delete.html` (partial and page), `reports/form.html`; `post.html` (rating,
    Report or Reported, staff's state tag), `deleted.html` (removes `#comments` out of band),
    `detail.html`, `list.html` (comment count and average); `star` and `flag` icons.
  - `styles/source.css` — the rating, comment and report `.fm-*` classes.
  - `config/settings.py`, `config/urls.py` — `reports`, `/reports/`.
  - Tests: `test_forums_comments.py` (31) and `test_reports.py` (19), both new;
    `test_forums_browser.py` (6 more); `test_accounts_security.py` (the new URLs and the
    `csrf_exempt` scan of `reports/`).
  - Docs: `docs/architecture/reports.md` (new); `architecture/forums.md`,
    `frontend/forums.md`, `ARCHITECTURE.md`, `FRONTEND.md`, `TESTING.md`.
  - `plans/axcenity-hub.md` — all four 12B criteria ticked.
- **TDD:** 1. The sixth comment within a minute is refused with the wait in words, and the
  next is allowed once the oldest is a minute old (red: `DID NOT RAISE`). 2. Hidden and
  removed posts and comments are missing from every list, count and page for a visitor,
  another member and both authors, every way to read or act on them is a 404, and staff see
  them marked but can't interact with them (red: the list showed "Hidden post"). The
  querysets' filters were held back until behavior 2, so it started red.
- **Decisions:** 1–5 stars; comments can't be edited; rolling windows that count hidden and
  removed content too (deleted content frees its place); "admin" is `is_staff`, decided only
  in `can_see_moderated`; hidden content is a 404 even for its author; interacting needs
  visible content under a visible post, for staff too; the report constraint covers abuse
  reports only, so Phase 14's feedback isn't limited; reports are deleted with their target
  and kept (reporter emptied) when the reporter leaves; the report page is a full page, never
  HTMX; no status on reports yet (Phase 14); nothing sets the state yet (Phase 15).
- **Deviations:** The user's four additions were adopted as written: averages from rating
  rows to one decimal place, shown only with a visible post; threaded tests that hold
  simultaneous posts and comments to the limit; the database constraint plus a threaded
  duplicate-report test; and the single visibility layer in `reports.moderation`. The user
  asked to stop only at each red test.
- **Sideways:** A `TextField`'s `max_length` binds only forms, so `full_clean` let an
  over-long comment, report or post body through the services. This was caught by a service
  test and fixed with validators, including on 12A's post body. `"٣".isdigit()` is true, so
  the score parsing now accepts only `"1"` to `"5"`. `timeuntil` joins with non-breaking
  spaces, which the limit messages now replace. A report's target lookup crashed for a
  signed-out visitor (excluding an `AnonymousUser` author) before sign-in could redirect.
  Test-side fixes: Django's textarea starts with a newline, `.micro` uppercases text, and a
  reported comment redirects to its `#comment-` anchor.

## 2026-11-25 — Axcenity Hub: Phase 12A/17, Forum posts and ownership

### Prompts

1. The `/implement` skill, given `axcenity-hub phase 12a`.
2. "Looks good just include these smaller additions: 1. Test author ownership explicitly:
   Verify that another signed-in user, an anonymous visitor, and an administrator who isn't
   the author cannot edit or delete someone else's post. All should receive a 404 rather than
   a 403. 2. Preserve accessibility and graceful fallback: HTMX interactions should retain
   keyboard accessibility, provide clear focus behavior when content is swapped, and work
   through the full-page routes when JavaScript is unavailable. Other than that continue to
   development"

### Summary

- **Outcome:** A `forums` app: anyone reads `/forums/` and each post; verified members
  publish; only a post's author edits or deletes it, and everyone else (another member, an
  admin who isn't the author, a signed-out visitor) gets a 404. On a post's page Edit and
  Delete swap the post in place through HTMX (the Hub's first), with focus following each
  swap, and every action still works as full pages without JavaScript. 1302 fast tests and
  102 browser tests pass; Ruff is
  clean. The one failing fast test is
  `test_download.py::test_the_copied_license_and_notice_match_the_engines`: the engine
  checkout has new commits that change its NOTICE, which fails on a clean `main` too.
- **Changes:**
  - `forums/` (new) — `models.py` (`ForumPost`, `authored_by`, `is_author`), migration
    `0001_initial`, `services.py` (`create_post`, `edit_post`, `delete_post`: the
    verification gate and an author check), `forms.py` (`PostForm`, lengths in plain words),
    `views.py` (`AuthorPostMixin`: the 404 lookup before anything else;
    `HtmxAwareMixin`: `Vary: HX-Request` and redirects as `HX-Redirect`; partial or page per
    request), `urls.py`, `strings.py`, a read-only `admin.py`.
  - `templates/forums/` (new) — list, detail, form and confirm-delete pages; `partials/` for
    the post, its edit form, the question and the deleted notice, each `#post` at its root.
  - `static/js/forums.js` (new) — an htmx error answer loads the page in full.
  - `templates/app/shell.html` — `{% htmx_script %}` and an `app_head` block.
  - `config/settings.py`, `config/urls.py` — `django_htmx`, `HtmxMiddleware`, `forums`,
    `/forums/`.
  - `pyproject.toml`, `uv.lock`, `marketing/legal/hub.json` — django-htmx 1.29.0 (htmx
    2.0.10) and its credit.
  - `accounts/strings.py`, `templates/partials/icon.html` — the rail's Forums item and a
    `chat` icon. `marketing/content.py` — the nav's Community and the footer's Forums link
    to `/forums/` instead of "Soon".
  - `styles/source.css` — the `.fm-*` classes.
  - Tests: `test_forums.py` (35), `test_forums_browser.py` (9);
    `test_accounts_security.py` (forums' public pages, the `csrf_exempt` scan, the walk's
    members-only names); `test_accounts.py` (the rail's Forums item).
  - Docs: `docs/architecture/forums.md` and `docs/frontend/forums.md` (new);
    `ARCHITECTURE.md`, `FRONTEND.md`, `TESTING.md`, `frontend/app-shell.md`, `README.md`.
  - `plans/axcenity-hub.md` — both 12A criteria ticked.
- **TDD:** Skipped, as the plan says: CRUD with a 404 for non-authors follows the ownership
  pattern Phases 10–11 test. Every criterion got ordinary tests.
- **Decisions:** Reading is public (story 58's visitors), in the app shell; deleting your own
  post isn't gated on verification; bodies are plain text; no pagination until 12C; htmx
  through django-htmx (as the Toolbox does), not a hand-copied file; focus by htmx's own
  `autofocus` handling (on HTMX answers only), with Save announced through a live region
  filled out of band; the engine's NOTICE and crate list that `refresh_credits` also
  rewrote were put back, keeping only the django-htmx credit.
- **Deviations:** The user added the explicit three-way ownership test and the
  accessibility and no-JavaScript requirements. A signed-out visitor now gets a 404 on edit
  and delete rather than the usual sign-in redirect, as asked (the walk of members-only URLs
  allows either).
- **Sideways:** The HTMX create test expected `HX-Redirect` from a view that lacked the
  mixin; added. The first browser runs failed: `hx-disabled-elt="find …"` logged an error once
  its form was swapped out (removed; htmx already drops a second request while one runs),
  and the test pressed keys before htmx had set up a swapped part, so the link acted as a
  plain link. Waiting for focus wasn't enough (a field keeps it across a swap); the test now
  waits on `htmx:load`.

## 2026-11-25 — Phase 11 follow-up: member suggestions while inviting, chips for several invitees, demo members and level role controls

### Prompts

1. "Ok so there are a few things that I want to change firslty when inviting member and typing
   their name I want to be able to see their profile come up while I am typing it otherwise I
   would hav no idea if I am typing it correctly. Also what is Bob and the other test users
   sign in information. Additionally some of the formatting looks a little off, in one of my
   screen shots the owner and change role buttns look sized and wrapped strangely. Please add
   these changes and let me know how I can test for them" (with a screenshot of the Owner row's
   tall role select beside a small "Change role" button).
2. "One last thing when I click on the username for instance bob I want it to show somewhere
   that I still am inviting him, becasue right now when I click his name it just disappears,
   then I would like to be able to add multiple people at once"
3. Sent while that was being built: "Ok I tested to make sure that bob could not access the
   space game project without being a member it returned a 404 page like it is supposed to but
   it is still using the default django template no the custom ones we made earlier."
4. "I understand now go ahead and append our conversation to PROMPTS.md and commit and push the
   changes"

### Summary

- **Outcome:** The Team page's invite field suggests members as an Owner types and adds each
  chosen one as a chip, so up to 10 people are invited at once in one role; a
  development-only `seed_team_demo` command creates demo members to sign in as; the role
  controls sit level with their buttons. 1267 fast tests and 93 browser tests pass; Ruff is
  clean. The one failing fast test is still
  `test_download.py::test_the_copied_license_and_notice_match_the_engines`, from the
  uncommitted credits work.
- **Changes:**
  - `projects/teams.py` — `find_members` (Owners only; at least 2 characters; at most 6
    active members whose username or display name starts with the query, exact username
    first; each marked available, already in the team, invited, or you; emails never matched
    or shown), `parse_usernames`, `invite_many` and `InviteResult` (each invitation its own
    transaction; refusals named; too many, none or an invalid role sends none).
  - `projects/views.py`, `urls.py` — `MemberSearchView` at `/projects/<slug>/members/search/`
    (never cached); `InviteView` reads every `username` value and reports each refusal.
  - `projects/forms.py`, `strings.py` — the field is "Usernames" (comma-separated without
    JavaScript, not required since chips carry the names); the suggestion, chip and batch copy;
    "No Hub member is called “…”."; "Invite members".
  - `templates/projects/member_suggestions.html` (new), `members.html` — the suggestions list;
    a compact role select (`h-8`, level with the small buttons) in a row that isn't
    `.app-actions` (its forms are `display: contents`); no role control on the only Owner's own
    row; the script's wording as `data-*` attributes.
  - `static/js/projects.js` — the invite field as a combobox (↑/↓, Enter, click, Escape, a
    polite live region) and the "Inviting" chips (×, Backspace, hidden inputs, "Send 2
    invitations", chosen people tagged "Added").
  - `projects/management/commands/seed_team_demo.py` (new) — alice, bob, cara, dan, dana and
    erin (`<username>@example.com`, password `axcenity-team-demo`, verified) and "Demo Space
    Game"; DEBUG only, no privileges, never changes existing accounts or projects.
  - Tests: `test_projects_teams.py` (search, states and access; the seed; batch invites and
    parsing; the last Owner's row), `test_projects_browser.py` (suggestions by keyboard and
    pointer, a disabled one refused, chips removed and re-added, two invited at once, role
    controls level with their buttons). Docs: `docs/architecture/projects.md`,
    `docs/frontend/projects.md`, `docs/TESTING.md`, `docs/ARCHITECTURE.md`.
- **Decisions:** Suggestions are server-rendered HTML fetched by a few lines of vanilla
  JavaScript (no vendored library); one role per batch; a batch invites who it can rather
  than all-or-nothing; the seed creates members only when missing, so a real "bob" keeps
  his password.
- **Deviations:** The user's 404 report: under `DEBUG` Django shows its technical 404 in
  place of the Hub's page (the Hub's shows with `DEBUG` off, and at `/errors/404/` in
  development); explained, nothing changed. Offered a switch to show the Hub's pages under
  `DEBUG`; not taken up.
- **Sideways:** A text replacement added the script block after every `{% endblock %}`,
  caught by a template error. The shell's `.app-actions > form { display: contents }`
  undid the role row's layout, and the only Owner's row kept an empty actions box: both seen
  in the phone screenshots. Playwright refuses to click an `aria-disabled` option, so the test
  forces the click to show it does nothing; the chips' hidden `username` inputs made the
  field's locator ambiguous, so it uses `[data-member-search]`.

## 2026-11-25 — Axcenity Hub: Phase 11/17, Project teams

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 11`.
2. Changes to the brief before building: prevent self-lockout (an Owner must not be able to
   demote, remove or leave as the last Owner), applied to account deletion too; make
   invitation and membership changes transactional, with unique constraints in the database,
   the project row locked before owner-count changes, and the membership and invitation
   state re-checked inside the transaction; test the 5-project owner limit at both invitation
   acceptance and role promotion (making someone an Owner at five must fail without changing
   their membership); "Other than that proceed to TDD only stopping at red".
3. "approved, keep rename on the edit page move to next red phase after making this one pass"
   (approving TDD 1's RED test).
4. "approved, make it pass and finish the build" (approving TDD 2's RED test).

### Summary

- **Outcome:** Projects have teams: Owner, Maintainer and Viewer memberships, invitations by
  username that only the invitee accepts or declines, role changes, removal and leaving, a
  Team page, invitations on `/projects/`, and every project page showing each role only what
  it may do (everything else a 404). A project always keeps an Owner, account deletion
  included. 1250 fast tests and 93 browser tests pass; Ruff is clean;
  `makemigrations --check` shows nothing new. One fast test fails that this phase didn't
  touch: `test_download.py::test_the_copied_license_and_notice_match_the_engines` (the
  engine's NOTICE now differs from `marketing/legal/NOTICE`, both part of the uncommitted
  credits work).
- **Changes:**
  - `projects/models.py` — `Role`, `Action`, `PERMISSIONS` and `allows`;
    `ProjectMembership` and `ProjectInvitation` (unique per member and project, roles held by
    check constraints); `Project.owner` removed; queryset `allowing`, `visible_to`,
    `owned_by`, `create_with_owner`; `Project.role_of`; `protect_last_owner`, the
    membership's `on_delete` that refuses to delete a project's last Owner (ProtectedError,
    which the admin lists as the reason).
  - `projects/migrations/0003_teams.py`, `0004_remove_project_owner.py` (new) — every owner
    becomes an Owner member (the column goes nullable first, so both roll back), then the
    column is dropped; tried forward, back and forward on a copy of the dev database.
  - `projects/teams.py` (new) — `invite`, `accept`, `decline`, `cancel`, `change_role`,
    `remove`, `leave`: one transaction each, the project row locked, then the actor's role and
    the target re-read; locks always project then member; the last Owner kept; becoming an
    Owner counts against the limit and changes nothing when refused.
  - `projects/services.py` — the limit counts Owner memberships (`owned_count`); repository
    actions check the role table instead of the owner.
  - `projects/views.py`, `urls.py`, `forms.py`, `strings.py` — `ProjectAccessMixin` (each
    view's `Action`); the team page and the POST views for inviting, roles, removing,
    cancelling, leaving, accepting and declining; `DescriptionForm` for Maintainers; stale
    repositories refreshed on view only for roles that may refresh; the copy.
  - `projects/admin.py` — owners in the list; memberships and invitations read-only inlines.
  - `templates/projects/members.html` (new), `detail.html`, `list.html` — the team page; role
    tags; actions per role; the invitations panel.
  - Tests: `tests/test_projects_teams.py` (new, 63 tests); a team-pages case in
    `test_projects_browser.py`; the other project tests and `test_errors.py` moved from
    `Project.objects.create(owner=…)` to `create_with_owner`.
  - Docs: `docs/architecture/projects.md`, `docs/frontend/projects.md`, `docs/TESTING.md`,
    `docs/ARCHITECTURE.md`; the plan's Phase 11 boxes ticked.
- **TDD:** (1) the role matrix: five actions × Owner, Maintainer, Viewer and a non-member
  through the real URLs, allowed changes happening and every refusal a 404 that changes
  nothing (a Maintainer's rename is ignored by the edit page's form). (2) A project always
  keeps an Owner: stepping down, removing themselves, leaving and deleting the account are
  refused for the last Owner and change nothing, and two Owners doing it at the same moment
  leave exactly one.
- **Decisions:** Memberships are the only record of ownership (`Project.owner` dropped);
  several Owners are allowed, and "transfer" is an explicit role change followed by stepping
  down; invitations may carry any role, including Owner; invite by username, not email (no
  enumeration); inviting needs a verified email, accepting doesn't; invitations are deleted
  once answered; no notification email; Viewers never trigger GitHub calls; the team page
  reuses existing classes, so `styles/source.css` (already modified) wasn't touched.
- **Deviations:** The user turned "the last Owner's account deletion deletes the project"
  (the brief) into "it's refused", and asked for transactional changes with database
  constraints, project locks, re-checks, and limit tests at acceptance and promotion. Rename
  stayed on the edit page at the user's choice.
- **Sideways:** TDD 1's first run had a test bug (viewing "took effect" was always true),
  fixed before RED. TDD 2's account-deletion case: Django's delete collector replaces an
  `on_delete`'s ProtectedError message with its own, so the test identifies the refusal by
  the protected objects (exactly the last Owner's membership) rather than the message, a
  change to what the approved test asserts, flagged to the user. A first `accept` deleted an
  already-used invitation and then raised inside the transaction, undoing the delete; the
  error now comes after it. `accept` first locked the invitation before the project, which
  could deadlock with a cancel; it now reads it unlocked, locks the project, then re-reads it.
  A text replacement missed the team view's context after `ruff format` had rewrapped it
  (caught by the tests). `.app-list`'s unlayered `padding: 0` beat a Tailwind utility, and
  clearing cookies in the browser test also cleared the theme; both caught in screenshots.

## 2026-11-24 — One Account settings page, profile photos, centred pages, and the setup guide folded into each step

### Prompts

1. "Ok everything so far is coming together functionally, however appearance-wise I feel like
   there could be some additional improvements. In all of the profile menus they are shifted
   to the left, I would like them to be centered liekt he rest of the application. There also
   is not really too much going on with each of the pages. I like the work gode with the
   setup guide for additing additional content to the page. As for profile and account I can
   not change my photo. I think it would laos be a good idea to put the profile email
   password 2FA and connected accounts into one page menu, also the setup guide while it is
   nice I feel like it should ultimately just be included when setting up a repository for
   the first time or if they would like further assistance on the steps. Also it says
   Axcenity then hub really this is more of an an account center than anything. remove the
   testing on your own computer section as well."
2. "Go ahead and append this conversation to PROMPTS.md then commit and push"

### Summary

- **Outcome:** All seven asks built. 1160 fast tests and 85 browser tests pass; Ruff is
  clean and `makemigrations --check` shows nothing new.
- **Changes:**
  - Centring: every signed-in page sits in one 60rem column (`.app-column`) centred beside
    the rail.
  - One page: the rail has a single **Account settings** item. Profile, Email, Password,
    Two-factor and Connected accounts are tabs (`strings.ACCOUNT_TABS`) under one header
    (`templates/accounts/base.html`): photo, name, "Member since", and status tiles for
    email, two-factor and GitHub, each linking to its tab. allauth's pages join through
    `layouts/manage.html` and new overrides of `account/password_change.html` and
    `mfa/index.html`. Every tab keeps its own URL.
  - Fuller pages, in the setup checklist's panel style: Profile has a live "As others see
    you" preview; Email has "What we send"; Password has "A good password"; Two-factor shows
    the app and recovery codes as numbered steps; Connected accounts has "What linking does".
  - Photos: `accounts/avatars.py` checks size (2 MB), format (PNG, JPEG, WebP, GIF) and
    dimensions (64–4096 px) before decoding. It then crops to a 256 px square and re-saves as
    WebP, so no metadata is kept, under a random name. Migration `0005_profile_avatar`. Old
    files are deleted on replace, remove or account deletion. `MEDIA_ROOT` (`DJANGO_MEDIA_ROOT`)
    is git-ignored, and `/media/` is served only while `DEBUG` is on (`config/media.py`).
    The photo, or an initial, shows in the bar, the menu, the header and the preview.
  - Setup guide: the `/projects/guide/` page is gone. Each checklist step ends in "Help with
    this step". On a member's first repository, the current step's help and a "Before you
    start" list open by themselves. Troubleshooting is in step 4's help; unlinking is under
    the repository panel. `guide` is now a usable project name.
  - "Testing on your own computer" removed, with the copy that pointed to it.
  - Bar label "Hub" → "Account center"; rail headings "Workspace" and "Account".
  - Tests: `test_accounts_photos.py` (new); the shell, header, help and browser tests were
    rewritten. Docs: app-shell, projects, accounts, ARCHITECTURE, TESTING, README.
- **Decisions:** One rail item with tabs rather than one long page, so allauth's flows and
  links keep working. The header reads only what the Hub recorded and never asks GitHub; a
  token GitHub refused shows "Reconnect", not "Linked". Photo uploads were planned for
  Phase 13 and built early because they were asked for. Production must serve `MEDIA_ROOT`
  at `/media/` from the web server. The README's Cloudflare Tunnel notes were kept, since
  they are for whoever runs the Hub, not for members. Product sentences still say "the Hub".
- **Deviations:** None; the ambiguous asks were settled by the decisions above.
- **Sideways:**
  - The migration test failed ("no such column: accounts_profile.avatar") because the profile
    signals fired at schema 0001; they are now disconnected for that window.
  - `static()`'s unnamed media route broke the URL walk test; it was replaced with a named
    development-only view.
  - Playwright locators matched two elements, and a menu toggle closed itself; both were
    fixed in the tests.
  - Screenshots caught: truncated status tiles and a wrapping bar label on phones; the
    GitHub tile saying "Linked" for a refused token; a cramped phone trouble table; a
    duplicate "Forgot password" link; help copy that said "Open your project" while already
    on it. All were fixed.
  - At commit time `test_the_copied_license_and_notice_match_the_engines` failed. The
    engine's `NOTICE` has uncommitted edits in its own checkout. The Hub's copy still
    matches the engine's last commit, so it was left alone.

## 2026-11-24 — Custom error pages for every status

### Prompts

1. "Ok another thing is the default 403 and 404 pages look somewhat basic can you make custom
   error pages for all error types."
2. "Please add to PROMPTS.md commit and push"

### Summary

- **Outcome:** Every error status renders the Hub's own page: 400, 403, the CSRF 403 ("Form
  expired"), 404, 405, 429 and 500. 1146 fast tests and 89 browser tests pass; Ruff is clean.
- **Changes:**
  - `config/errors.py` (new): each page's words, the handlers (`bad_request`,
    `permission_denied`, `page_not_found`, `server_error`, `too_many_requests`,
    `csrf_failure`), `render_error`, a development-only preview, and `ErrorPageMiddleware`
    (an empty 405 gets the page, keeping `Allow`).
  - `config/urls.py`: `handler400`/`403`/`404`/`500`, `handler429` (allauth's rate limits)
    and `/errors/<kind>/` (`errors:preview`, a 404 unless `DEBUG`). `config/settings.py`:
    `CSRF_FAILURE_VIEW` and the middleware.
  - `templates/errors/page.html` (new) and the `.err-*` classes in `styles/source.css`: the
    entrance's bar and grid backdrop, a panel with a title bar, the code in Home's outlined
    numerals, a motif, the headline, what happened, and three ways on.
  - Tests: `test_errors.py`, `test_errors_browser.py` (new). Docs: ARCHITECTURE (layout,
    URL, rule), FRONTEND ("Error pages"), TESTING.
- **Decisions:** Pages render without the request's context processors: no session, user or
  database (a 500 must render when the database failed; a 400 may come from an untrusted
  host), reading only the validated theme cookie. Nothing the visitor sent is echoed. The
  CSRF page shows Django's reason and the `HUB_PUBLIC_URL` hint only under `DEBUG`. Since
  `DEBUG` shows Django's technical 404 and 500, a development-only preview shows each page.
  Error pages are `no-store`. allauth looks for `handler429` in the root URLconf, so its rate
  limits use the same page.
- **Deviations:** None.
- **Sideways:** Three tests first asserted the wrong thing (Django's CSRF reason reads "Origin
  checking failed", the webhook's `Allow` is just `POST`, and counting queries needs the
  database mark even to prove there are none); fixed in the tests, not the code.

## 2026-11-24 — Phase 10 follow-up: webhooks through a Cloudflare Tunnel, honest setup messages, and the README

### Prompts

1. A screenshot of GitHub's Add webhook form: "Ok so I am at this screen what do I put for
   payload URL and secret"
2. A screenshot of the project page (steps 3 and 4 "Not available", "Repository connected,
   2 / 2"): "This is what I have"
3. A screenshot of Cloudflare's "Add published application" failing for the bare domain:
   "Ok it seems to not be working on cloudflare tunnels also fix the webhook messages"
4. "Can you add hub.axcenity.com to allowed hosts"
5. "Ok I got a 403 forbidden when trying to login to the ada account it was a csrf
   verification failed"
6. "Ok I got it to work can you include in the README the information about how to setup a
   domain in cloudflare tunnels and what information to put in the webhooks etc. go ahead and
   update PROMPTS.md commit and push"

### Summary

- **Outcome:** The user's repository webhook works through a named Cloudflare Tunnel on their
  own domain. The setup checklist no longer claims completion when the server has webhooks
  off; a new `HUB_PUBLIC_URL` setting builds payload URLs on the Hub's public address, allows
  its host and trusts it for CSRF; the README documents the whole setup. 1135 fast tests and
  the project browser tests (8) pass; Ruff is clean.
- **Changes:**
  - `projects/setup.py`: progress is out of four always; with webhooks off the setup is
    never complete (`live_updates_off`). `projects/strings.py`, `templates/projects/detail.html`:
    member-facing wording for webhooks off ("Live updates aren't available on this Hub yet");
    the operator's hint (set `GITHUB_WEBHOOK_SECRET`) only on a development server; the
    local-host warning points at `HUB_PUBLIC_URL`; the guide's "Testing on your own computer"
    covers quick and named tunnels and lists the commands.
  - `config/settings.py`: `HUB_PUBLIC_URL` (scheme and host only, else settings refuse to
    load), added to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`; `DJANGO_CSRF_TRUSTED_ORIGINS`
    read in development too. `projects/views.py`: `payload_url` builds on it.
  - `.env.example`, `README.md` (status table, stack, environment variables, a new
    "Connecting GitHub repositories" section: the server's settings, a named or quick
    Cloudflare Tunnel, GitHub's webhook form field by field, troubleshooting), and the docs
    (ARCHITECTURE, `architecture/projects.md`, `frontend/projects.md`, TESTING).
  - Tests: `test_projects_setup.py` (webhooks off never complete, the operator hint in
    development only, the payload URL on the public address), `test_settings_production.py`
    (the public address allowed and trusted, malformed values refused).
  - The user's `.env` (git-ignored, never committed or printed): `HUB_PUBLIC_SECRET` renamed
    to `GITHUB_WEBHOOK_SECRET`, `DJANGO_ALLOWED_HOSTS` and `HUB_PUBLIC_URL` added, at the
    user's request; only variable names were read.
- **Decisions:** One setting, `HUB_PUBLIC_URL`, rather than asking members to swap hosts by
  hand: it's the site's own origin, so allowing it and trusting it for CSRF follows. Settings
  names appear on member pages only when `DEBUG` is on. The README recommends publishing only
  the webhook path through the tunnel, since the development server runs with `DEBUG` on.
- **Deviations:** None.
- **Sideways:** The webhook steps were "Not available" because the user's `.env` held the
  secret under a misremembered name (`HUB_PUBLIC_SECRET`), found by checking the value's
  shape without printing it. The checklist's "Repository connected, 2 / 2" with webhooks off
  was misleading (the user's screenshot showed it); fixed. Cloudflare refused the bare domain
  (likely an existing DNS record); a subdomain worked. Signing in through the tunnel failed
  CSRF's origin check (https at Cloudflare, http at Django); trusting the public origin fixed
  it. A test edit missed once because Ruff had reformatted the test; reread and reapplied.

## 2026-11-24 — Phase 10 follow-up: webhook setup help, guided repository setup and a setup guide

### Prompts

1. "Ok so how would I setup a webhook I know I create one in github"
2. "Ok but how would this work for other users if they do not have access to the internal env
   file"
3. "Ok there are a few problems for me functionally this works, but clarically I am getting
   lost and I feel that for end users they would be likely to get lost as well. I currently
   have no clear setup guide the interface looks simple and boring unlike the rest of the site
   and overall there should be more emphasis on guiding users on how to setup their
   repositories."
4. Answers to two questions: the setup flow as a checklist on the project page
   (recommended), and the guide in the app, public (recommended).
5. "Commit and push", and log this follow-up in PROMPTS.md.

### Summary

- **Outcome:** Prompt 1: walked through a local webhook (the root secret and a tunnel host in
  `.env`, a Cloudflare quick tunnel, swapping the tunnel's https address into the payload URL,
  GitHub's form, and each failure code). Prompt 2: explained that `.env` is the server's
  configuration: members of a hosted Hub only copy their own repository's URL and derived
  secret, and the tunnel is for local development; noted the two ways to remove the manual
  step (the `admin:repo_hook` scope, or a GitHub App) as later decisions. Prompt 3: rebuilt
  the project pages around guidance. 1131 fast tests and the related browser tests (19)
  pass; Ruff is clean.
- **Changes:**
  - `projects/setup.py` (new): the four setup steps' states from the records (done, current,
    attention, waiting, off; one current at a time). Migration 0002: `webhook_shown_at` and
    `first_webhook_at` on `RepositoryLink`; `webhooks.receive` sets the first delivery;
    `services.webhook_settings` records when the values were shown.
  - `projects/views.py`: the project page's checklist (`step_rows`), the webhook's values
    shown inline with `?webhook=show` (never cached; the old `/repository/webhook/` page and
    its template removed), a local-host warning, cards with setup progress, and
    `ProjectGuideView`. `projects/urls.py`: `/projects/guide/`; `guide` is a reserved name.
  - `templates/projects/detail.html`, `list.html`, `guide.html` (new): numbered steps with
    Home's outlined numerals and motif icons, the Toolbox's title-bar chips, GitHub's Add
    webhook form field by field with copy buttons and a direct link, a repository panel with
    fact tiles, project cards, an empty state previewing the steps, and the guide (before you
    start, the steps, what the Hub can and can't do, troubleshooting by response, unlinking,
    testing on your own computer).
  - `static/js/projects.js` (new): the copy buttons (hidden without JavaScript).
    `styles/source.css`: the `.pj-*` classes. `templates/partials/icon.html`: `chain`,
    `repo`, `hook`, `ping`, `guide` motifs and `copy`, `external`, `plus`, `check`.
  - The app shell: the rail's Hub section gains Setup guide; signed out, it shows only the Hub
    section and a Sign in button (`accounts/templatetags/app_shell.py`, `strings.py`,
    `templates/app/shell.html`).
  - Tests: `test_projects_setup.py`, `test_projects_browser.py` (new); updates to
    `test_projects.py`, `test_projects_github.py`, `test_accounts.py`,
    `test_accounts_security.py` (the guide is public; the webhook page is gone).
  - Docs: `docs/frontend/projects.md` (new); FRONTEND, ARCHITECTURE, TESTING,
    `architecture/projects.md`, `frontend/app-shell.md`.
- **Decisions:** Step 3 counts as done once the owner has shown the webhook's values (a
  recorded timestamp), since the Hub can't see GitHub's settings; step 4 once a delivery has
  arrived. The checklist folds itself when complete. The guide lives in the app shell, not in
  `/docs/` (the engine's snapshot). The guide's troubleshooting codes come from the webhook's
  real responses, and a test keeps them in step.
- **Deviations:** None: the user chose both recommended options.
- **Sideways:** The project templates had to keep `text` (the shell's `copy`). Browser review
  caught the setup bar crowding at 360 px, a doubled border on the folded checklist, a `−`
  toggle that read as a stray dash (now "Show steps" / "Hide steps"), a button clipped by its
  panel (the fit check now compares each element with its own panel, and fails without the
  fix), and phone rules placed before the base rules they overrode. A test asserting
  `?webhook=show` was absent tripped over the theme switch's own form URL. A second webhook
  request in one test reused the 60 s permission check, as designed, so its mock was relaxed.

## 2026-11-24 — Axcenity Hub: Phase 10/17, Projects and repository integration

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 10`.
2. Changes to the brief before building: scope webhook delivery-id and body-hash uniqueness to
   the repository link; resolve the permission before every repository-dependent action with
   a cache of at most 60 s per member and repository, never reused after expiry, failing
   closed, and document that revocation can take up to 60 s; make the permission-check
   mechanism an explicit prerequisite (verify which GitHub endpoint establishes the role with
   the existing no-scope token, settle the authorization model if it needs scopes, never
   silently expand OAuth permissions); make the five-project limit concurrency-safe (atomic
   transaction, owner-level locking, a concurrency test, other members' projects never
   counting); then "continue to TDD phases only stopping on red".
3. "Looks good move to next red test" (approving TDD 2's RED test).
4. "Looks good move on" (approving TDD 3's RED test).
5. "move on and finish the rest of the phase" (approving TDD 1's RED test).

### Summary

- **Outcome:** A `projects` app: create, view, edit and delete projects (owner only; others
  404), at most 5 per member under a per-member lock, names unique in any case, slug URLs;
  link one public GitHub repository per project (needs admin on GitHub), refresh it, unlink
  it; GitHub calls with per-member backoff, an hourly budget and ETags; stored details with a
  notice when GitHub fails; signed webhooks with per-link derived secrets and per-link replay
  refusal. 1123 fast tests and 77 browser tests pass; Ruff is clean.
- **Changes:**
  - `projects/` (new): `models.py` (Project, RepositoryLink, WebhookDelivery; migration
    0001), `services.py`, `github.py`, `webhooks.py`, `views.py`, `forms.py`, `urls.py`,
    `strings.py`, `admin.py`, `apps.py`.
  - `accounts/limits.py` (new): `lock_member` and `LimitReached`, the pattern for every
    count-based limit.
  - `config/settings.py`: the app; SQLite `transaction_mode = "IMMEDIATE"`; a per-process
    file test database; `GITHUB_WEBHOOK_SECRET`, `GITHUB_PERMISSION_TTL` (60 s),
    `GITHUB_CALLS_PER_MEMBER_PER_HOUR`, `GITHUB_REPOSITORY_REFRESH`. `config/urls.py`:
    `/projects/`. `.env.example`: `GITHUB_WEBHOOK_SECRET`.
  - `accounts/strings.py`, `accounts/templatetags/app_shell.py`, `templates/app/shell.html`:
    the rail in sections (Hub: Projects; Account). `templates/partials/icon.html`: `folder`.
    `styles/source.css`: `.app-project`. `templates/projects/*` (new).
  - Tests: `test_projects.py`, `test_projects_github.py`, `test_projects_webhooks.py` (new),
    `fixtures/github/repository.json` (GitHub's documented example repository);
    `test_accounts_security.py` (the webhook is the one CSRF-exempt and public URL; the
    project URLs in the members-only walk), `test_accounts.py` (the rail),
    `test_browser_server.py` (the file test database).
  - Docs: `docs/architecture/projects.md` (new), `docs/ARCHITECTURE.md`, `docs/TESTING.md`,
    `docs/frontend/app-shell.md`; the plan's Phase 10 boxes ticked.
- **TDD:** (2) a sixth project is rejected, one at a time and with eight concurrent creations
  (exactly five succeed), other members' projects not counting; (3) the permission is resolved
  before each action, a check reused only while younger than 60 s, a downgrade or removal
  blocking it, and outages or a missing `permissions` failing closed; (1) only the link's own
  valid `X-Hub-Signature-256` is accepted, and the same delivery id or body is refused as a
  replay for that link but not for another.
- **Decisions:** The authorization model: the no-scope OAuth App stays as it is; the role comes
  from `GET /repos/{owner}/{repo}`'s `permissions` (GitHub's docs give that endpoint no scope
  note and "repository info" to no-scope tokens; the collaborator and hook endpoints need
  `repo`, `read:org` or `admin:repo_hook`); a missing or malformed `permissions` fails closed;
  owners add the webhook by hand; only public repositories can be linked; the undocumented
  `/repositories/{id}` isn't used. Per-link webhook secrets as HMAC(root, hook_id), shown only
  after an admin check. Link and the webhook page need admin; refresh needs read; unlink and
  delete never ask GitHub. Projects are owner-only until Phase 11. The slug follows the name;
  `new` and `hooks` are reserved. Webhook signature failures answer 403 (unknown hooks 404).
  No HTMX yet (Phase 12A).
- **Deviations:** The user changed the brief before building: replay uniqueness per link,
  the explicit 60 s permission rule and its documentation, the permission endpoint as a
  verified prerequisite with no silent scope expansion, and a concurrency-safe limit with
  its own test.
- **Sideways:** The concurrency test first failed with "database table is locked": SQLite's
  shared in-memory test database fails a waiting writer at once, so tests now use a file per
  process (11 s → 15 s, later 11 s); with the lock removed the test fails, confirming it
  catches the race. GitHub's docs don't say outright that `permissions` comes back to a
  no-scope token, so the check fails closed without it and the manual test confirms it live.
  The project templates' `copy` was shadowed by the app shell's own `copy` (renamed `text`).
  A blank name slipped past `clean()`, the name constraint's error landed on the form instead
  of the field, and `full_clean` added a duplicate slug error; all fixed. Page tests compared
  messages with apostrophes against escaped HTML (unescaped now). Two weak assertions (an
  `or True`, a clumsy mock swap) were tightened. The browser test pinning the in-memory test
  database's name was updated.

## 2026-11-24 — Phase 9 follow-up: GitHub keys, a local .env, and .env.example

### Prompts

1. "Ok I got the client id and client secret but where are the token keys"
2. "Ok the keys seemed to work and they linked my github, nwo how can I have these stored
   without having to run them each time"
3. "Ok everything looks good I was able to test it, can you add an env example file and
   commit the changes do not commit the .env file I created also make sure to append this
   session to PROMPT.md"

### Summary

- **Outcome:** Prompt 1: explained that `GITHUB_TOKEN_KEYS` isn't from GitHub; the member
  generates a Fernet key with `cryptography` and keeps reusing it. Prompt 2: a git-ignored
  `.env` loaded by `uv run --env-file .env …` (or `UV_ENV_FILE=.env` in the shell profile);
  no code or dependency change. The user linked their GitHub account and tested the phase by
  hand. Prompt 3: added `.env.example`, a test that keeps it complete, and docs; 1038 fast
  tests pass; Ruff is clean. The user's `.env` was never read, staged or committed.
- **Changes:**
  - `.env.example` (new): every variable `config/settings.py` reads, grouped (GitHub
    linking, Turnstile, email, the docs sync, production only), with no values, the key
    command, and how to load it with uv.
  - `tests/test_settings_production.py`: the example lists every variable settings reads,
    its live lines hold names only, and `.env` is git-ignored.
  - `README.md` (copying and loading `.env`; the GitHub variables), `docs/ARCHITECTURE.md`
    (settings intro), `docs/architecture/github-linking.md` (running with `.env`, keeping
    the key), `docs/TESTING.md` (the new test).
- **Decisions:** uv's built-in `--env-file` rather than adding python-dotenv (no new
  dependency, settings unchanged). `AXCENITY_ENGINE_DIR`'s example is an absolute, quoted
  path, because settings doesn't expand `~`.
- **Deviations:** None.
- **Sideways:** The first scan for the variables settings reads missed the two read across
  a line break (`DJANGO_EMAIL_BACKEND`, `AXCENITY_ENGINE_DIR`); the test's pattern allows
  whitespace after the parenthesis and checks both are found.

## 2026-11-24 — Axcenity Hub: Phase 9/17, GitHub account linking

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 9`.
2. "Looks good go ahead and move to TDD only stopping at RED" (approving the brief and
   both TDD behaviors; stop only at each RED, not after GREEN).
3. "Looks good move to next test" (approving TDD 1's RED test).
4. "Looks good move to development" (approving TDD 2's RED test).

### Summary

- **Outcome:** A member links one GitHub account from a new **Connected accounts** page
  (`/accounts/3rdparty/`), sees its state (linked, needs reconnecting, GitHub unreachable),
  reconnects, and unlinks after a fresh re-authentication. GitHub is a linked account only,
  never a sign-in. Tokens are stored by the Hub, Fernet-encrypted with keys from
  `GITHUB_TOKEN_KEYS`; allauth's plain-text token table stays empty. 1114 tests pass (the
  full suite, browser tests included); Ruff check and format are clean. Every Phase 9
  criterion is ticked.
- **Changes:**
  - `accounts/crypto.py` (new): Fernet/MultiFernet encryption with environment keys
    (first encrypts, all decrypt); `KeyMissing`, `Unreadable`; never echoes a value.
  - `accounts/models.py`, `accounts/migrations/0004_githublink.py`: `GitHubLink` (one per
    `SocialAccount`, cascade-deleted on unlink) with encrypted access and refresh tokens,
    `expires_at`, `needs_reconnect`, `checked_at`; `GitHubLink.objects.store`.
  - `accounts/github.py` (new): `check_link` (`GET /user` at most every 15 minutes; 401 →
    needs reconnecting, never asked again; other failures leave the link alone),
    `refresh_tokens` (rotation for GitHub App tokens), `mark_needs_reconnect`; token-free logs.
  - `accounts/adapter.py`: `SocialAccountAdapter`: apps from the environment only (SocialApp
    rows ignored), a 404 when linking is off, no providers on sign-in or sign-up pages,
    signup closed, and `pre_social_login` refusing anything but a connect by the signed-in
    member, a GitHub account linked elsewhere, or a second GitHub account; stores a
    reconnect's tokens. `signals.store_github_tokens` stores a new link's.
  - `accounts/views.py`, `accounts/urls.py`: `ConnectionsView` (replaces allauth's
    `socialaccount_connections`; unlink behind `reauthentication_required`) and
    `GitHubConnectView` (replaces `github_login`: members only, POST only, always connect).
  - `accounts/admin.py`: allauth's `SocialApp` and `SocialToken` admin pages unregistered.
  - `accounts/strings.py`, `templates/accounts/connections.html`,
    `templates/socialaccount/` (Hub copy for the cancelled and failed pages and the link
    messages), `templates/partials/icon.html` (a `link` icon for the rail item).
  - `config/settings.py`: `allauth.socialaccount` and its GitHub provider, the
    `SOCIALACCOUNT_*` policy, `GITHUB_CLIENT_ID`/`_SECRET`/`GITHUB_TOKEN_KEYS`; production
    refuses an app without a key, and any malformed key, without echoing it.
  - `pyproject.toml`, `uv.lock`: `cryptography` listed explicitly (already installed through
    allauth's MFA extra).
  - Tests: `tests/test_accounts_github.py` (new, 47), `tests/fixtures/github/user.json`
    (new), `tests/test_accounts_browser.py` (Connected accounts at 360 and 1280 px, dark and
    light), `tests/test_accounts.py` (the rail's new item), `tests/test_accounts_security.py`
    (allauth's public callback and error pages on `PUBLIC`, its deprecated `/social/`
    redirects, the new pages in the walk), `tests/test_settings_production.py` (GitHub key
    refusals; strips `GITHUB_*` from the subprocess environment).
  - Docs: `docs/architecture/github-linking.md` (new), `docs/ARCHITECTURE.md` (index row,
    layout, URLs, variables, external APIs), `docs/architecture/accounts.md` (pointer),
    `docs/TESTING.md`, `docs/frontend/app-shell.md`; the plan's Phase 9 boxes ticked.
- **TDD:** (1) Tokens are encrypted at rest: no column of the raw row holds either token,
  they read back only with the environment's key (another key raises `Unreadable`, none
  raises `KeyMissing`), and deleting the SocialAccount leaves no row. RED on the first
  assertion with a model that stored tokens as given. (2) A 401 marks the link as needing
  reconnection: `check_link` returns `NEEDS_RECONNECT`, saves the flag, keeps the token, and
  never asks GitHub again. RED with a scaffold that reported every failure as
  `UNAVAILABLE`. Both went GREEN with no change to the tests.
- **Decisions:** GitHub is a link only, never a sign-in (research question 1; it can't
  bypass two-factor). An OAuth App with no scopes, with the refresh path built and tested
  for a GitHub App. Re-authentication to unlink but not to connect (allauth's connect
  re-authentication would park the new token in plain text in the session). One GitHub
  account per Hub account as well as one Hub account per GitHub account. Unverified
  members may link. The link is checked when Connected accounts is viewed, at most every
  15 minutes. allauth's "last sign-in method" check is skipped on unlink, since GitHub never
  is one. A new topic file rather than growing `accounts.md`.
- **Deviations:** The user asked for TDD to stop only at RED, not after each GREEN.
- **Sideways:** Adding `allauth.socialaccount` broke 26 accounts tests until the
  `SocialAccountAdapter` the settings named existed. The Connected accounts template
  compared states against `states.NEEDS_RECONNECT`; Django calls callables in templates,
  an Enum class is callable, so the lookup came out empty and no prompt showed. Comparing
  against the string values fixed it. The refused-state tests expected a 200, but allauth's
  error page is a 401. The "never logged" test found nothing logged at all, so it proved
  nothing; `github.py` now logs (link id only), and the test requires records. Copy checks
  failed on HTML-escaped apostrophes until pages were unescaped. allauth's
  deprecated unnamed `/accounts/social/…` redirects answer 301, which the members-only URL
  walk didn't allow for.
- **Later phases:** Phase 10's repository calls and permission checks build on
  `accounts/github.py`; Phase 16's API must keep `GitHubLink` out of its serializers.

## 2026-11-24 — Fix: sign-up fails with "no such table: account_emailaddress"

### Prompts

1. (With a screenshot of `OperationalError at /accounts/signup/`, "no such table:
   account_emailaddress") "Alright when I try to sign up the user ada@axample.com
   according to the last guide it presents me with an error. Also please append any
   conversations to PROMPTS.md"
2. "ok I tried confirming the account and got" (a pasted 404 for
   `/accounts/confirm-emai%3Dl/MQ:1xVwum:…/`)

### Summary

- **Outcome:** No code change. The local `db.sqlite3` had never had Phase 8's migrations
  applied (`account` 0001–0009, `accounts` 0001–0003, `mfa` 0001–0003), so allauth's
  tables didn't exist. Ran `uv run python manage.py migrate`; a sign-up POST in a
  rolled-back transaction then returned 302 to `/accounts/confirm-email/` and created
  the user.
- **Deviations:** None.
- **Sideways:** The first smoke POSTs failed for reasons in the test, not the app: the
  shell's test client sent `Host: testserver` (400, not in `ALLOWED_HOSTS`), then the
  POST left out the required `username` field (200 with a form error). Fixed both in the
  test and the third run passed. Lesson: after pulling a phase that adds apps or models,
  run `migrate` before `runserver`.
- **Prompt 2 (no code change):** the 404 came from copying the link out of the console
  email. The body is quoted-printable (the link line is longer than 78 characters), so
  the terminal shows a soft line break, `=` at a line end, inside `confirm-email`, and
  the paste kept it as `confirm-emai=l`. With the `=` removed, the key's signature
  checks out (it decodes to Ada's email address, pk 1, within the 3-day expiry) and the page
  shows allauth's "Please confirm that ada@example.com…" with a Confirm button. The
  key was checked with GET requests only, so the user still confirms it.

## 2026-11-24 — Axcenity Hub: Phase 8/17, Accounts, security and two-factor sign-in

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 8`.
2. (On the brief) "Ok thre is one conflict that I want to resolve which involves email
   verification: allauth documentation states that mandatory prevents unverified users
   from logging in and optional permits unverified login while still sending verification
   emails. Enumeration prevention with optional verification can require allowing multiple
   accounts to share an email address when using strict prevention. Do not assume that
   changing the password-login step alone cheives the desird behavior. Also add in an
   additional test which will exercise the actuall allauth signup and password login flows
   with an existing email and newly registered unverified account. make sure that all five
   requirements hold to tis. If the alluths stage architecture cannot support this cleanly
   use a narrower scoped versin of this as to not weaken signup and login intergration or
   email uniqueness and enumeration protection."
3. (TDD 1, the verification gate, RED) "Looks good move to next red phase after passing
   this test"
4. (TDD 2, case-insensitive uniqueness, RED) "Looks good just one safegurad - make sure
   that migration checks for existing case-insensitive duplicated before creating indexes
   and reports the conflicting record clearly. Do not silently delete or merge accounts.
   Other than tat make this test pass and move to development"

### Summary

- **Outcome:** django-allauth (65.22.1, with MFA) gives the Hub sign-up, sign-in by
  email, sign-out, email verification, password reset and two-factor sign-in
  (authenticator app plus ten one-time recovery codes).
  - A Profile per member (display name, bio) and an editor-style **app shell** for
    signed-in pages; sign-in pages use a slim **entrance** layout. allauth's templates
    are all restyled through its layouts and elements.
  - The nav's Sign in is a real link; signed in, it reads Account.
  - Hardening: sessions (24 h idle, 14 days absolute, rotation on sign-in, password and
    two-factor changes, server-side sign-out); CSRF on every URL; one-hour single-use
    reset links; two rate-limit layers (cache, plus a database backstop); enumeration-
    safe sign-in, sign-up and reset; honeypots; Turnstile (off until keys are set, fails
    closed, never the only check); production settings that pass `check --deploy` with
    no warnings.
  - 1,061 tests pass (988 fast, 73 browser); Ruff is clean. All 12 acceptance criteria
    are ticked.
- **Changes:**
  - `accounts/` (new app):
    - `models.py`: `Profile`, `AuthAttempt`; migrations 0001–0003 (0002 adds the
      case-insensitive unique indexes after checking for duplicates)
    - `stages.py`, `adapter.py`: the signup-only verification stage, the signup message
      fix, the QR code with its own white paper
    - `access.py`: the contribution gate; `integrity.py`: the indexes and duplicate check
    - `forms.py`, `throttle.py`, `turnstile.py`, `middleware.py`, `signals.py`,
      `validators.py`, `admin.py`, `views.py`, `urls.py`, `strings.py`,
      `templatetags/app_shell.py`
  - `config/settings.py`: allauth and MFA settings, sessions, headers, the production
    block (secret key and hosts required, HTTPS, HSTS, shared cache, SMTP), `MAILERS` in
    place of the deprecated `EMAIL_BACKEND`, Turnstile keys. `config/urls.py`: `/accounts/`.
  - Templates (new): `app/shell.html`, `app/entrance.html`, `allauth/layouts/*`,
    `allauth/elements/*`, `accounts/*`, `partials/form_fields.html`, `messages.html`,
    `theme_switch.html` (taken out of `site_nav.html`). Five icons in `icon.html`; the
    `.app-*` and `.entrance` classes in `styles/source.css`.
  - `marketing/content.py`, `views.py`, `site_nav.html`: Sign in and Account links.
  - Tests (new): `test_accounts.py`, `test_accounts_security.py`,
    `test_accounts_mfa.py`, `test_settings_production.py`, `test_accounts_browser.py`,
    `gate_urls.py`. Changed: `conftest.py` (browser tests' database, below),
    `test_browser_server.py`, `test_shell.py` (Sign in is a link now),
    `test_theme_switch.py` (the renamed production flag).
  - `pyproject.toml`, `uv.lock`: `django-allauth[mfa]`.
  - Docs: `docs/architecture/accounts.md` and `docs/frontend/app-shell.md` (new); the
    ARCHITECTURE, FRONTEND and TESTING indexes.
- **TDD:** each test was written first and failed on an assertion:
  1. The verification gate: an unverified member signs in through allauth's login view
     but a contribution is refused (no action, redirect to verify, the link re-sent),
     and it goes through once verified. Failed with a 200 where a redirect was expected.
  2. Case-insensitive uniqueness: sign-up refuses `ALICE`, creates nothing for
     `Alice@Example.COM`, and the database refuses case-only duplicates in `auth_user`
     and `account_emailaddress`. Failed with "DID NOT RAISE IntegrityError".
- **Decisions:**
  - The verification conflict (prompt 2): allauth runs `mandatory`, so signup stays
    enumeration-safe and email-unique with no "strict" mode. The adapter's
    `get_login_stages()` hook swaps in a stage that applies mandatory handling only at
    signup, so an unverified password login goes through. A throwaway prototype against
    real allauth compared stock `mandatory` and the swap before any code was written: the
    only difference was the unverified login.
  - Narrowed scope: no adding or changing email addresses in this phase (allauth's
    add-email form accepts another account's address unverified). The Hub's own email
    page shows status and resend only.
  - Sign-in by email only; usernames 3–30 characters, stored as typed, with a reserved
    list. Sessions end after 24 hours idle or 14 days. Production cache: the database
    cache by default, Redis when `DJANGO_REDIS_URL` is set. Turnstile only on signup and
    the reset request, failing closed. Public profile pages wait for the forums.
- **Deviations:** the end-to-end policy test and the migration's duplicate safeguard
  (report every conflicting record, change nothing) were added at the user's request.
- **Sideways:**
  - The end-to-end test found a real enumeration leak in allauth's defaults: its
    verification cooldown is per address, so the "Confirmation email sent" message went
    missing on a signup with an address mailed minutes earlier. The adapter now drops
    that message at signup; the page itself still says an email was sent.
  - Browser tests were reaching the **development database** (`db.sqlite3`) when run on
    their own: `browser_server` asked for the test database too late. No data was lost.
    Every browser test is now marked for the test database at collection, and a guard
    fails any test that reaches `db.sqlite3`.
  - Django 6.1's `check --deploy` refused the console email backend in production;
    production now uses SMTP from the environment.
  - Two-factor enrolment didn't seem to rotate the session in tests: allauth sends that
    signal on commit, which a wrapped test never reaches. The test now uses real commits.
  - The migration test restored only to 0002 and dropped the 0003 table for later tests;
    it now restores to the latest migration.
  - Smaller fixes: a hard-coded white behind the QR code broke a theme rule (the white
    moved into the image); allauth's pages needed the app column's width and spacing;
    a lone untagged submit button is now the primary one.

## 2026-11-24 — Axcenity Hub: Phase 7/17 follow-up, download page layout, icons and license agreement

### Prompts

1. (The Phase 7 commit question) "Commit and push"
2. (With a screenshot of the Linux panel) "Ok we need to fix this layout issue with
   the linux build it is over extending making it not look too good"
3. "Ok I am thinking we can include some iconography for the different operating
   systems also to me this does not look very nice but the download buttons are not
   in line with eachother. There should also be someiconography for each of the other
   files and checksums. If not already these downloads should pull from the latest
   release so they should update dynamically when a new tagged release comes out."
4. (With screenshots of the Other files and Linux panels) "Ok I feel like there is
   some empty space within the download page that could look better, can you add or
   change the layout in a way to make these less empty also animation the icons
   would be cool as well."
5. "Ok one othe thing can you have a popup when downloading any file for a license
   agreement based on apache and my trademark where they have to agree betore
   downloading. Also please append this conversation to PROMPTS.md according to
   source formatting"
6. "We might as well have the full text to the rigth of the license agreement text
   for them to click on rather than having them navigate over to the GitHub page."
7. (While that was being built) "Ok when scroling through the license page it also
   scrolls the download page as well"
8. "Ok the text in the notice and the license files is wrapped weirdly can you fix
   this to make it look better."

### Summary

- **Outcome:** Phase 7 was committed and pushed (`1109030`). Then
  `/download/` was reworked:
  - **Layout:** Windows and macOS share a row; Linux spans it with its
    builds three to a row; commands wrap; Download buttons line up across
    every row.
  - **Icons:** line icons for each system and kind of file, animated as
    motifs.
  - **Filling the gaps:** tip cards fill the gaps in the Linux and Other
    files panels, and "Or build it yourself." sits beside the checksum
    commands.
  - **License agreement:** every download now goes through it, as a
    popup or, without JavaScript, a page. The engine's full LICENSE and
    NOTICE sit beside the terms in a tabbed, scrolling pane, so the
    GitHub links went away. They're set as prose: the files' hard wraps
    are joined, with headings, bold section titles and indented
    sub-items.
  - **New releases:** the page already updated on its own; that's now
    tested.
  - 958 tests pass (890 fast, 134 in `test_download.py`); Ruff is clean.
    Nothing from these rounds is committed yet.
- **Changes:**
  - `templates/marketing/download.html`, new `download/panel.html`,
    `download/build.html`:
    - the row layout and full-width panels
    - tip cards; the two-column `#verify` with `#source`
    - icons and the cards' pinned SHA-256 and button
    - Download links to `/download/agree/?file=…`; the agreement dialog;
      `download.js`
  - New `templates/marketing/download/agreement.html` (the shared terms
    and form, with the full-text pane and its LICENSE and NOTICE tabs)
    and `download_agree.html` (the page without JavaScript).
  - New `marketing/legal.py`: `reflow` turns a hard-wrapped plain-text
    legal file into headings, centred line blocks and paragraphs (bold
    section lead, sub-item level). A test checks it keeps every word in
    order.
  - New `marketing/legal/LICENSE` and `NOTICE`: the engine's, copied in
    unchanged from commit `cae2e6c`, and loaded as
    `content.ENGINE_LICENSE` and `ENGINE_NOTICE`.
  - `marketing/views.py`: `DownloadView._panel` (wide panels, tip span);
    `DownloadAgreeView` (GET terms; POST with CSRF and `agree=yes` → 303
    to the file; unknown file → 404).
  - `marketing/urls.py`: `marketing:download_agree` at `/download/agree/`.
  - `marketing/releases.py`: `BuildKind.icon`, `Build.icon`, `find_asset`.
  - `marketing/content.py`:
    - icons for every build kind, and `DOWNLOAD_SYSTEM_ICONS`
    - `DOWNLOAD_PAGE` gains `tips`, `from_source` (the engine's
      getting-started steps) and `agreement` (the engine README's
      "License and trademark" words and LICENSE section 7)
  - `templates/partials/icon.html`: 14 new icons (windows, macos, linux,
    installer, disk, app, package, archive, hash, manifest, key, history,
    file, files), each with parts that draw in or move.
  - `static/js/shell.js` / `home.js`: the motif player moved from Home's
    script to the shell's, so any page's motifs play.
  - New `static/js/download.js`: the agreement dialog. It opens on any
    Download link and keeps "Agree and download" disabled until the box
    is ticked; modified clicks fall through to the page.
  - `styles/source.css`:
    - the card column and its pinned foot; wrapping commands
    - the icon tile and its hover; the tip card
    - the dialog and its terms
  - `tests/test_download.py`:
    - layout: links through the agreement, icons and motifs, tip cards
      for 3–5 Linux builds, from-source steps against the docs snapshot
    - a new release replacing the old one; drafts hidden
    - the agreement: refusals, unknown and hostile file names, no
      release, CSRF, and the terms against the engine's README and
      LICENSE
  - `tests/test_home.py`: the motif test reads `shell.js`.
  - Docs:
    - `docs/frontend/download.md`: icons, the layout, the agreement
    - new `docs/architecture/github-releases.md`: choosing the release,
      the cache and new releases, moved out to keep the topic file under
      ~200 lines
    - the ARCHITECTURE index, URLs and External APIs; FRONTEND (the
      scripts); TESTING; `theme.md` (the primary button's uses);
      `home.md` (motifs now in `shell.js`)
- **TDD:** none. These were follow-up requests outside the `/implement`
  flow, built with ordinary tests.
- **Decisions:**
  - Icons:
    - The system icons are drawn for the Hub (a four-pane window, an
      apple, a penguin) rather than copying the Windows, Apple or Tux
      trademarks.
    - The icons reuse Home's motif system rather than a second animation
      mechanism.
  - Layout:
    - A wide panel's gap is filled only when there's tip copy for that
      system, spanning one or two columns as needed.
    - New releases still appear within the hourly cache rather than
      faster, to stay under GitHub's 60 unauthenticated requests an hour.
      Webhooks (Phase 10) could clear the cache instantly.
  - The agreement:
    - It quotes the engine's own README and LICENSE rather than new legal
      text.
    - It's asked on every download.
    - It works without JavaScript as its own page.
    - The full texts are copied in (the engine repo is read only) rather
      than fetched. A test fails when the engine's copies change. The
      tabs are radios with `:has()`, so they need no script.
    - Its POST takes a file's name, never a URL, so the redirect can only
      reach the current release's files.
- **Deviations:** none. Every change was the user's request; the user
  didn't redirect any recommendation.
- **Sideways:**
  - My unlayered `margin: 0` on `.dl-terms` beat Tailwind's `mt-6`, the
    same mistake as earlier in Phase 7. The dialog screenshot caught it.
  - A scripted docs edit cut the Icons section in the wrong order and
    duplicated it; the next line count caught it, and the section was
    rewritten.
  - Scrolling to the end of the license pane carried on scrolling the
    page behind the dialog, and a modal `<dialog>` doesn't lock the
    page's scroll either (prompt 7). Fixed with `overscroll-behavior:
    contain` on the pane and the dialog, and `overflow: hidden` on
    `html:has(.dl-dialog[open])`. Verified with wheel events in
    Playwright: the page stays put; it scrolls again once the dialog
    closes.
  - The full texts first showed raw in a `<pre>`. Their 75-column hard
    wraps re-wrapped in the narrower pane and left stray one-word lines
    (prompt 8), so `legal.reflow` now sets them as prose. Two of my test
    inputs were wrong, not the code:
    - a double space in the source ("brackets!)  The") made the copy check
      miss, so joined paragraphs now have single spaces
    - an edge-case test used short lines, which keep their breaks by
      design; its input was fixed
  - Killing the dev server with `pkill -f` matched the shell running it
    (exit 144); later runs stopped it by process ID instead.
  - Screenshots and a Playwright run of the dialog checked the work at
    375 and 1440 px: it opens with the file, the button is disabled until
    the box is ticked, agreeing goes to the exact GitHub file and closes
    the dialog, and Escape closes it. GitHub was intercepted, so nothing
    downloaded.

## 2026-11-24 — Axcenity Hub: Phase 7/17, Download page

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 7`.
2. "Looks good move to TDD only stopping on red"
3. (TDD 1, release selection, RED) "Looks good move to next"
4. (TDD 2, failure fallbacks, RED) "Looks good move to next"
5. (TDD 3, the 304 and ETag, RED) "Move to next red phase only stop at red"

### Summary

- **Outcome:** `/download/` serves the engine's newest release from
  GitHub's release list. It shows the version, an Alpha badge, the date
  and title, and every file grouped by system with its size, SHA-256 and
  install hint. The visitor's system gets a "Download for <system>"
  button.
  - ETag requests; data is fresh for an hour and kept seven days as the
    fallback, with a backoff after failures.
  - When GitHub fails, the page serves the cached list with its date,
    then a plain GitHub Releases link. It never shows an error page.
  - The nav, Home's two CTAs and the footer now link to `/download/`.
  - 912 tests pass (844 fast, 92 of them in `test_download.py`); Ruff is
    clean. All four acceptance criteria are ticked.
- **Changes:**
  - `marketing/github.py` (new): the one GitHub request: User-Agent,
    pinned API version, `If-None-Match`, a timeout. Every failure comes
    back as a `Fetched` result instead of an exception.
  - `marketing/releases.py` (new):
    - choosing the release, with validation of every GitHub field
      (digests, download URLs, names, sizes, dates)
    - `group_builds`, `detect_system`
    - `current_release`: cache, ETag, fallbacks and backoff
  - `marketing/content.py`:
    - `DOWNLOAD_PAGE` and `DOWNLOAD_BUILDS`, taken from the engine's
      release-notes template
    - Download links switched to `marketing:download`
    - `ENGINE_REPO_URL` now comes from `github.py`; the `ENGINE_VERSION`
      comment corrected
  - `marketing/views.py`, `urls.py`: `DownloadView` at `/download/`,
    varying on `User-Agent` and `Sec-CH-UA-Platform`.
  - `templates/marketing/download.html`, `download/build.html` (new); the
    `.dl-*` classes in `styles/source.css`.
  - `templates/partials/site_nav.html`, `home/hero.html`,
    `home/final.html`: `rel="noopener"` only on external links; the nav's
    Download is marked current on `/download/`.
  - `tests/test_download.py`, `tests/fixtures/github/releases.json` (new):
    the real release list, trimmed. `test_shell.py` and `test_home.py`
    expect `/download/`.
  - `pyproject.toml`, `uv.lock`: `requests`, and `responses` (dev).
  - Docs: `docs/frontend/download.md` (new); ARCHITECTURE (layout, URL,
    External APIs); the FRONTEND table; TESTING (file row, Mocking);
    `theme.md` (the primary button's uses); `home.md`; README status and
    stack.
- **TDD:** each test was written first and failed on an assertion:
  1. Selection: the newest non-draft wins, prereleases are marked alpha,
     and a newer stable release counts.
  2. Fallbacks: a 500, 503, timeout, 403 rate limit or 429 serves the
     cached release with its date, then "unavailable", never raising.
  3. A 304 to the stored ETag reuses the cached release and resets the
     hour.
- **Decisions:**
  - "Newest" means the latest `published_at`.
  - Data is fresh for 1 h and kept 7 days; the backoff follows
    `Retry-After` or the rate-limit reset, else 5 min, bounded to 1 min–1 h.
  - Any non-200/304 status or non-JSON body counts as a failure.
  - The main builds are the `.exe`, the `.dmg` and the AppImage.
  - Update zips, checksums, the manifest, its signature and the history
    file go under "Other files", so every file stays reachable.
  - System detection uses the client hint first, then the User-Agent;
    phones, tablets and ChromeOS count as unknown.
  - No GitHub token, and Home's badge stays the fixed `ENGINE_VERSION`.
- **Deviations:** none; the user approved the plan and each red test as
  written.
- **Sideways:**
  - The third TDD test first failed with a `KeyError`, not an assertion.
    Reading the header with `.get()` fixed it; what it checks didn't
    change.
  - An ordinary test caught a real bug: a fresh cached list with no
    release was reported "live". It's now "unavailable".
  - `NOT_COPY` in the Home tests skips a key named `source`, so the
    page's data note was renamed `data_note` to keep it in the copy check.
  - Screenshots of the page at 375 and 1440 px against the live GitHub
    list showed three problems: the title bars hid the panels' outlines,
    the shorter panels stretched, and unlayered `margin: 0` rules beat
    Tailwind's `mt-*`. All three were fixed. A first re-check looked
    unchanged because the `--noreload` dev server still served the cached
    old template.
  - One live GitHub request was made outside the tests to capture the
    fixture.

## 2026-11-24 — Axcenity Hub: Phase 6C/17, API reference

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 6C`.
2. "Looks good go ahead and move to implementation, stoping only at red
   phases"
3. (TDD 1, parsing an API page, RED) "Lookgs good move to next red phase"
4. (TDD 2, search ranking and query handling, RED) "Looks good move to next
   red phase after making this one pass"
5. (After the commit, with a screenshot of the sidebar's search box) "Ok so
   there are a few things I want to change first the API reference is huge
   so I feel like it should get its own seperator not an infinite looking
   tab list. additionally the search bar is fairly small with some of the
   searches that might be occuring on this page, can we make it a but
   bigger while still holding up the pages integrity. The sweach button
   should also be improved as it looks squished and cropped out of place."
6. "Go ahead and adjust the PROMPTS.md and commit and push the changes"

### Summary

- **Outcome:** the engine's generated API reference (144 classes, 46 data
  types, 53 enums, the `task` library and 5 globals) is a browsable
  reference, and the docs have search. 813 tests pass (fast and browser);
  Ruff check and format are clean.
  - `/docs/api/`: a panel each for Classes, Data types, Enums, Libraries and
    Globals, with a progressive filter.
  - Class, type, library and globals pages: the constructor and intro, a
    summary table per kind with linked signatures, Instance's members in a
    collapsed group, the members in full, and a rail of members by kind.
  - The enums page: an anchor per enum, items as chips.
  - `/docs/search/?q=`: ranked, paginated results with marked snippets.
- **Changes:**
  - `documentation/api.py` (new): `parse()` reads an API page into an
    `ApiPage` of `Member`s, pairing its headings with the rendered ids;
    `page_kind()`; `first_sentence()`.
  - `documentation/search.py` (new): `build_index()`, `clean_query()`,
    `search()` (the ranking), `mark()`.
  - `documentation/rendering.py`: `parse_body()` and `plain_text()` made
    public; `Rendered.lead`/`body` (split at the first heading);
    `type_links` link the type names in API signatures and record them as
    internal links for the build check.
  - `documentation/highlight.py`: `type_names()` and a `links` argument to
    `highlight()`, keeping each piece's Luau colour.
  - `documentation/library.py`: `type_links`, `api_page()`, `api_pages()`,
    `search_index`; the build check parses every API page and refuses a page
    at `/docs/search/`; the new ids are reserved from headings.
  - `documentation/views.py`, `urls.py`, `strings.py`: per-kind API
    templates, `api_context`/`api_home_context`, `DocsSearchView` at
    `documentation:search`, and their words.
  - `templates/documentation/api/` (`members`, `enums`, `home`),
    `search.html`, partials `api_table`, `api_rail`, `search_form` (in the
    sidebar column).
  - `static/js/docs.js`: the API home's filter. `styles/source.css`: the
    `.api-*` and `.search-*` rules.
  - Tests: `tests/test_documentation_api.py` (new, 36 tests); the browser
    test now targets the longest class page and checks the filter; the
    theme tests gain the search box and match pairs and the new pages.
  - Docs: `docs/frontend/documentation.md` (API layout and search),
    ARCHITECTURE (modules, the search URL), FRONTEND, TESTING; plan Phase 6C
    ticked.
- **TDD:** (1) parsing a class page into its constructor, inheritance and
  members by kind, with first-sentence summaries and the renderer's own
  anchors; (2) search ranking (exact name, title, heading, member,
  description; prefix then reading order; one result per URL) and query
  handling (trim, collapse, empty and over-long refused).
- **Decisions:** member kinds keep the engine's words (Properties, Events,
  Functions, not "Methods"); anchors come from the rendered headings, never
  recomputed; owners, members, strings and comments are never linked as
  types; the API home uses stacked panels, not tabs; the search form sits
  at the top of the sidebar column, outside the phone disclosure; queries
  over 100 characters get a message; the enums page is fully structured
  (its prose is only each enum's description and items); `classes.md` and
  `types.md` stay plain pages.
- **Follow-up (prompt 5):** the sidebar's API reference was ~190 nested
  links. It's now set apart below the guide by a rule and its own title:
  Overview, Classes (144), Data types (46), Enums, Libraries, Globals, with
  only the current class or type listed under its group
  (`views._api_section`). The search box became one full-width field (44 px)
  with a magnifier and an arrow submit button inside it. Its focus ring is
  drawn inside (`:focus-within`) because the sidebar's scroll box was
  cropping the outline. The results page drops the sidebar copy for a large
  field under its title. Three new tests; the "every page in the sidebar"
  test now leaves out class and type pages. 816 tests pass, Ruff clean.
- **Deviations:** none in the build; the user approved the brief and both
  tests as written, and asked to stop only at red phases. After the commit
  they asked for the sidebar and search-box changes above.
- **Sideways:**
  - On the real snapshot, `TweenService` first found the
    `DataModel.TweenService` property, since every exact name tied. Added
    the brief's tie-break (a full name before a member's short name); the
    fixed-query acceptance test covers it, not the TDD test.
  - Two new tests assumed every API page has members. ReplicatedStorage
    (only Instance's) and DataRow (read by column name) have none. The test
    now checks member totals, and such pages hide the empty summary.
  - A test expected `Instance.new` as plain text; `Instance` is a Luau
    builtin and sits in a colour span.
  - A `pkill -f` meant for the screenshot server matched its own shell and
    ended the command; the server was stopped another way.

## 2026-11-24 — Axcenity Hub: Phase 6B/17, Documentation site

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 6B`.
2. "Looks good just incorporate some of these safeguards: Snapshot sync must
   be atomic - Build and valiudate the replacement snapshot in the temp
   director and replace the commited snapshot after success a failed sync
   should never leave documentation/content partially update. Validate
   source control - Refuse dirty documentation changes is good, verify that
   the recorded commit exists and that snapshots coorespond to that commit.
   Keep sync deterministic and indepotent. Treat markdown rendering as a
   security boundary, keep raw HTML disabled sanitize or reject unsafe URL
   schemes and ensure rewritten iage and page paths cannot esape the
   snapshot. Make the heading ID deterministic and collision safe Other than
   that move to development"
3. (TDD 1, link rewriting, RED) "Looks good just one small addition include
   additional tests for https:// and mailto: with query strings and
   fragments making sure they do not change. Make sure that encoded or
   unsafe schemes or distorted scheme forms cannot bypass validation Query
   strings on valid relative markdown links ensure they are preserved
   appropriately. Otherwise make this test pass and move to the next red
   phase"
4. (TDD 2, navigation, RED) "Looks good just include one small change an
   empty section or sections containing only nested entries should not
   cause parsing or ordering errors if the real engine SUMMARY.md does not
   contain either case this can be ordinary robustness. Other than that
   make this test pass and move to the next red phase"
5. (TDD 3, sync, RED) "Looks good go ahead and continue to development make
   sure that tree_hash(dest) reproduces gits actual tree hash including file
   modes and github object semantics"

### Summary

- **Outcome:** `/docs/` serves the engine's documentation in the marketing
  shell from a committed snapshot of the engine's `documentation/` folder
  (236 pages, 7 diagrams, engine commit `cae2e6c`, tree `b5fc734`).
  - Rendering and layout: markdown-it-py with raw HTML off, Luau
    highlighted as the editor does, a three-column layout with a
    SUMMARY.md sidebar, breadcrumbs, "On this page", heading permalinks,
    previous/next, status badges, the Alpha notice, View source at the
    snapshot commit, and a provenance footer.
  - Landing page: the docs' README, then one panel per section.
  - Site links: the nav's Docs, Home's "Read the docs", and the footer's
    Docs and Getting started now point at `/docs/`.
  - Tests: 700 fast tests pass (133 of them new in
    `test_documentation.py`), and one new browser smoke test passes.
    The full browser suite passes (67). Ruff is clean.
- **Changes:**
  - `documentation/` (new app):
    - `sync.py` and `management/commands/sync_engine_docs.py`: an atomic,
      commit-verified copy and git's tree hash.
    - `navigation.py`: SUMMARY.md's tree, reading order, previous/next,
      trail and orphans.
    - `links.py`: the link gate.
    - `highlight.py`: a Pygments lexer copying `lua_syntax.rs`.
    - `rendering.py`: front matter, Markdown, heading ids, code, tables
      and figures.
    - `library.py`: the snapshot as served, plus the build check.
    - `diagrams.py`: manifest entries for the 7 diagrams.
    - `strings.py`: the frame's copy.
    - `views.py` and `urls.py`.
    - `content/`: the snapshot and `SOURCE.json`.
  - `templates/documentation/`: the layout, page and landing templates,
    and partials for the sidebar (recursive), header, outline, pager and
    provenance.
  - `static/js/docs.js`: the copy buttons, the sidebar disclosure, and
    scrolling the current page into view.
  - `styles/source.css`: the docs styles. Tailwind no longer scans the
    snapshot.
  - `config/settings.py`: the app; `DOCS_SNAPSHOT_DIR`;
    `AXCENITY_ENGINE_DIR`; the snapshot's images served at
    `/static/docs/images/`.
  - `config/urls.py`: `/docs/`.
  - `.gitattributes`: the snapshot is `-text`, so its bytes, and so its
    tree hash, survive any checkout.
  - `pyproject.toml` and `uv.lock`: markdown-it-py, Pygments, PyYAML.
  - `templates/base.html`: a `full_title` block, so the docs can set
    "Page · Axcenity Docs".
  - `templates/partials/nav_link.html`: `section` marks Docs current
    across `/docs/`.
  - `marketing/content.py`: `Link` takes `args` and `section`;
    `GETTING_STARTED`; the docs links. The GitHub docs URLs are removed.
  - `templates/marketing/home/hero.html` and `final.html`: `rel=noopener`
    only on external secondary links.
  - Tests:
    - `tests/test_documentation.py` and
      `tests/test_documentation_browser.py` (new).
    - `test_home.py` and `test_shell.py`: the docs link and `Link`'s
      args.
    - `test_theme.py`: docs pages in the text-colour check, plus contrast
      rows for the docs.
  - Docs:
    - `docs/frontend/documentation.md` (new).
    - ARCHITECTURE: the app, URLs, the snapshot rule and settings.
    - FRONTEND, TESTING, `media.md`, `theme.md`.
    - `README.md`: status, stack, layout.
  - `plans/axcenity-hub.md`: all nine Phase 6B criteria ticked.
- **TDD:**
  1. **Link rewriting:** 48 cases, covering relative pages and images,
     README folders, queries, anchors, external links kept byte for byte,
     missing targets, snapshot escapes and disguised schemes.
  2. **The navigation tree:** sections, nesting, reading order,
     previous/next across sections and nesting, and orphans.
  3. **sync against a fake git engine:** an exact copy, `SOURCE.json`
     with commit, tree and date, the engine untouched including `.git`,
     and a second run changing nothing.

  Each test was approved at RED and passed without changing what it
  asserts. TDD 3 needed one mechanical repair: git 2.56 prints a UTC date
  as `Z`, so the test compares the parsed time.
- **Decisions:**
  - URLs: a README maps to its folder (`/docs/`, `/docs/api/`).
  - Highlighting: a Pygments lexer porting the editor's own rules, not
    Pygments' stock Luau lexer (it marks different builtins). It reuses
    `marketing/drawings.py`'s sets and the existing `.luau-*` colours.
  - Diagrams:
    - They're served as their 1200 px PNGs at no more than 600 CSS px, so
      they're never upscaled.
    - They have their own manifest entries in `documentation/diagrams.py`.
    - The caption is a "Diagram" label plus each page's alt text.
    - The images are served from the snapshot through a static prefix,
      not copied a second time.
  - Layout:
    - The sidebar appears from 1024 px and the rail from 1280 px.
    - Below 1024 px, one `<details>` element is the disclosure, closed by
      an inline script; without JavaScript it stays open.
    - The landing page's API panel lists only its top two levels.
  - Front matter: `icon` is parsed but not shown. `status: partial` shows
    as "Partly built".
  - Front matter is read one `key: value` per line, quoted values and
    lists as YAML, because the engine's descriptions contain unquoted
    `: `.
  - Sync is accepted only for regular `.md` and raster images (no SVG,
    symlinks or executables). The snapshot and the engine must not
    overlap.
  - Plain `http:` links are allowed (the plan keeps external links as
    written); everything else off the https/http/mailto list is refused.
  - A relative path whose decoded form contains a space is refused.
- **Deviations:** The user approved the plan, adding the four safeguards
  in prompt 2:
  - Atomic sync built in a temporary folder.
  - Reading from the commit's objects, with the tree hash recorded,
    verified on sync and rechecked by a test.
  - The rendering gate.
  - Reserved, collision-safe heading ids.

  At TDD 1 the user added cases (external links with queries and
  fragments, disguised schemes, queries on relative links). At TDD 2,
  robustness for empty or nested-only sections, as ordinary tests. At
  TDD 3, `tree_hash` checked against real git, including modes; it's now
  tested on sha1 and sha256 repos with executables, symlinks, empty
  folders and git's `name/` sort order.
- **Sideways:**
  - The first real sync refused the engine's front matter: three
    descriptions hold an unquoted `: `. The atomic design worked as
    intended, since nothing was written, and the parser became
    line-based.
  - The wide-screen rule hiding "Browse the docs" sat before its base
    rule, so the toggle showed at 1440 px. Screenshots caught it.
  - The breadcrumbs repeated "API reference". Screenshots caught it.
  - The smoke test first picked `api/classes.md`, the longest file but an
    index with no code. It now takes the longest class or type page.
  - Two tests asserted the wrong thing (an error message's wording, and
    the text of a refused autolink); the code was right.
  - A `sizes` attribute without a `srcset` was dropped.
  - Heading-id reservations missed the landing page's panel ids. A new
    test now checks that every id outside the article is reserved.
  - `pkill -f` matched its own shell while restarting the dev server, so
    the server ran as a background task instead.

## 2026-11-24 — Internal README styled after the engine's

### Prompts

1. "Alright I would like you to update the README page make it styled
   similarly off of the Axcenity Engine page this will eventually be for
   internal use so style it similar to that. ALso include what technology
   stack is being used how to set it up etc Append this session to
   PROMPTS.md according to source formatting."

### Summary

- **Outcome:** `README.md` rewritten in the engine README's style: a
  centred logo, title, tagline and link row, a status callout, captioned
  screenshots, then tables. Sections: project status (a phase summary
  pointing at the plan as the source of truth), technology stack, setup
  (prerequisites, `uv sync`, `migrate`, `tailwind runserver`, Chromium for
  browser tests), environment variables (the three `config/settings.py`
  reads), common commands, testing (the network guard and the browser
  tests' one opening), repository layout, the docs map, working rules, AI
  disclosure and licence/trademark. Added `docs/images/icon.png` (copied
  from the engine's `assets/branding/icon-256.png`) and two screenshots,
  `readme-home.webp` and `readme-toolbox.webp`, taken with Playwright from
  the development server at 1440 × 900 in dark mode.
- **Deviations:** None; no questions were asked. Choices made without
  asking: the audience is the Hub's own developers; the README says the
  repo has no licence yet (none exists) rather than copying the engine's
  Apache 2.0 text; planned stack pieces (allauth, DRF, HTMX) are listed
  as planned, not installed.
- **Sideways:** `screenshots/` is git-ignored, so the existing test
  screenshots couldn't be linked; new ones went into `docs/images/`. The
  first capture attempt timed out waiting for network idle (the hero film
  keeps streaming) and was retaken waiting for page load. A first draft
  said tests skip without the engine and Toolbox checkouts; only the
  Toolbox README comparison does, and the README was corrected. Phase 3's
  open DPR/60 fps box is noted in the status table rather than shown as
  done.

## 2026-11-24 — Axcenity Hub: Phase 6/17, Toolbox page

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 6`.
2. "Looks good just make sure that these are known to be demo credentials
   and in production releases they should have not priveleges. Use live
   provider contetn and record the actual capture data and source state,
   make sure that the screenshots remain usable if provider result or
   thumbnails change later. Commited screnshots should be treated as
   static assets not to be regenerated during tests. Other than that move
   to development"
3. At the commit question: "Commit and push but make one change for the
   editor I would like when the light mode is switched for the light mode
   images of the toolbox to also be updated so the site still looks
   cohesive"

### Summary

- **Outcome:** `/toolbox/` (`marketing:toolbox`) in the marketing shell:
  a hero with View on GitHub and Run it locally; Discover, Library and
  Packs, each a split panel beside a real 2560×1600 screenshot of the
  running Toolbox, with the three providers and their licences under
  Discover; then a terminal panel with the README's uv commands, what
  works offline, the labelled demo credentials and a README link. The
  nav, the footer and Home's "Explore the Toolbox" link to it. The
  screenshots were captured from a `git archive` copy of the Toolbox at
  `5b17c1d` with live ambientCG and Poly Haven content, and
  `toolbox-capture.json` records the source state, the capture settings
  and every result and thumbnail URL each one showed, with each file's
  SHA-256. Each screenshot has a light-theme twin, captured from the same
  copy in the Toolbox's light theme with the same results, shown instead
  whenever the site is light (a `<picture>` per scheme; CSS follows
  `html[data-scheme]`, live, and the hidden twin is never fetched). 541
  fast and 66 browser tests pass; Ruff is clean.
- **Changes:**
  - `marketing/content.py` — `TOOLBOX_REPO_URL`, `TOOLBOX_COMMIT`,
    `TOOLBOX_CAPTURE_RECORD`; `Media.subject` and `label` (captures of
    the Toolbox must be captioned "Toolbox screenshot", never "Engine
    capture"); three capture entries; `TOOLBOX_PAGE` (`ToolboxFeature`,
    `Provider`, `Command`); Toolbox links no longer "Soon"; `Media.light`
    and `is_light_twin_of`, with `_toolbox_screenshot()` building each
    dark screenshot and its light twin.
  - `templates/marketing/media/frame.html`, `picture.html` — a
    `<picture class="when-dark|when-light">` per scheme when a capture
    has a light twin.
  - `marketing/views.py`, `marketing/urls.py` — `ToolboxView` at
    `toolbox/`.
  - `templates/marketing/toolbox.html` — the page.
  - `styles/source.css` — `.tb-*` classes porting the Toolbox's shelf
    heads, title-bar chips and terminal, in the monochrome tokens.
  - `marketing/media_sources/toolbox-*-2560x1600.png` (dark and
    `-light`), `toolbox-capture.json` — the six screenshots and their
    record, each screen with its scheme.
  - `static/marketing/media/toolbox-*/` — 90 derivatives from
    `make_media`.
  - `tests/test_toolbox.py` (new) — URL, sections, links, copy as data,
    commands (and against the Toolbox README when its checkout exists),
    demo-credential labels, screenshots, the record's SHA-256s and the
    demo accounts' lack of privileges.
  - `tests/test_media_browser.py`, `tests/conftest.py` — the
    screenshots at 360–2560 px, dark and light, 1× and 2× (each scheme
    shows its own twin and never fetches the other), a live switch to
    light; `open_home` takes a `path`.
  - `tests/test_home.py`, `tests/test_shell.py`, `tests/test_theme.py` —
    caption prefixes by subject, the Toolbox repo allowed in link checks,
    the text-colour check over `/toolbox/` too.
  - `docs/frontend/toolbox.md` (new), `FRONTEND.md`, `ARCHITECTURE.md`,
    `TESTING.md`, `frontend/media.md`, `frontend/home.md` — the page,
    the record, how to capture again, the new URL and tests.
  - `plans/axcenity-hub.md` — Phase 6 ticked; Phase 17 gains a
    demo-accounts criterion (never seeded in production, never
    privileged).
- **TDD:** Skipped, as the plan says: a content page reusing Phase 5's
  media checks, with no new rule to drive.
- **Decisions:** A capture's `subject` sets its caption prefix, keeping
  the plan's two kinds. The screenshots are 1280×800 at 2×, the frames'
  own 16:10, so they're never cropped or upscaled; dark scheme, reduced
  motion, signed in as `demo_mira`. The capture script stayed in the
  scratchpad; the record and `docs/frontend/toolbox.md` give every
  setting needed to capture again. The README comparison test reads the
  local Toolbox checkout and skips where it's absent. The page shows only
  the README's public demo password, labelled local-only and
  unprivileged, never the README's personal test account.
- **Deviations:** At the commit question the user asked for light-mode
  screenshots too, so the page stays cohesive when the theme switches;
  they were captured, wired in and tested before committing. At the user's request, the demo credentials are
  labelled as demo, local-only and unprivileged on the page; the record
  proves the demo members had no staff, superuser, group or permission;
  and the plan's Phase 17 now requires that in any release. The
  screenshots are committed static sources checked by SHA-256, never
  regenerated by tests.
- **Sideways:** The first capture's sign-in clicked the Toolbox title
  bar's theme form (also a POST form), which left it signed out and
  switched to System; the selector now targets `.auth-form`. The Toolbox
  scrolls inside `main#content`, not the page, so full-page captures
  showed only the top; the work area is scrolled instead. The pack
  rows' titles weren't read into the record at first, and the run was
  redone so images and record come from one capture. On the page,
  `pt-16` overrode `.under-nav`'s padding and put the eyebrow under the
  nav; the terminal's background hid the panel's 1px outline; long
  captions wrapped over the phone screenshots (shortened). The test
  fixture named `page` collided with pytest-playwright's own fixture
  and was renamed.

## 2026-11-24 — The Logic loop shows the Scratch-style Blocks view as well as the Graph

### Prompts

1. "Ok one other thing that I noticed was the the blocks or lua section
   only included lua and the graph axcenity has an actual scretch style
   block editor as well can you includ e that in the animation as well."
2. "Go ahead and add it to PROMPTS.md"

### Summary

- **Outcome:** The Logic pillar's loop now runs 16 s and starts in the
  block editor's Blocks view. Above it is the script's real mode bar
  (`scripts.rs` `mode_bar`: Code, Blocks, Graph and its hint "Switch any
  time: the script runs the same either way."). An amber "when [Pad] is
  touched [Any Part]" hat pops in, and a violet "spawn decal
  [assets/textures/scorch.png] at (Position of (touching part)) facing
  [0 1 0]" / "size [2.5] fading after [4] seconds" block springs up and
  snaps on under it. The rows, reporter and values follow
  `block_editor.rs` `sections()`, and the values are the Graph's and the
  Luau's. The Luau types out below. The bar then slides to Graph, the
  nodes wire up and the pulse runs, and it slides back to Blocks before
  everything fades to the empty first frame. Phones show one view at a
  time: Blocks (panning across the wide block), Graph, then Code. New
  `static/reel/drawing/stacks.js` draws the Blocks view at the editor's
  sizes (40-point rows, 12-point padding, the hat's 14-point top and
  band, the tab under each block, 24-point fields, reporters, the dot
  grid). Nine new content tokens hold the editor's category fills with
  Increase contrast (Events, Looks, Sensing), their edges (the hue at
  78 %), its typed field colours and the black its menus are shaded
  with. Tests derive each fill and edge from the `Hue` bases, check the
  block words against the editor's, and add the contrast pairs. The
  manifest's alt text and provenance, `canvas.md`, `media.md`,
  `theme.md` and `home.md` are updated. 480 fast and 45 browser tests
  pass (including the 16 s loop's seamless wrap); Ruff is clean. Not
  committed.
- **Deviations:** None asked. Two judgement calls: the editor's base
  hues give white text under 4.5:1 (Amber is about 3:1), so the blocks
  use the editor's own Increase contrast fills; and the block icons
  (pointing hand, sparkle) are drawn stand-ins, since the engine's icon
  font isn't on the site (the provenance says so).
- **Sideways:** At first the empty end state drew its dot grid at the
  frame's unit and the Blocks view at the stack's zoom, which would have
  shown a jump at the wrap; both now use the frame's unit. Moving
  "facing" onto the block's second row to save width was undone, since
  the engine has it on the first. The taller script panel pushed the
  last Luau line under the frame's caption, so the split went from 60 %
  to 55 %. On phones the mode bar's hint was cut mid-sentence; it now
  shows only where it fits whole. The test palette rejected Violet's
  base until #7658E0 was allowed (it already reads at 4.95:1, so
  Increase contrast leaves it unchanged).

## 2026-11-24 — Hero becomes the Desert Homestead film; the reel's scenes move into the lower sections

### Prompts

1. "Alright I have a video I would like for you to use on the site page
   behind all of the other animations it is stored at
   /home/pauljanota/Videos/Axcenity/desert-homestead-cinematic-1080p-v3.mp4.
   Choose the best shots for the video make it flow cohesively with the
   theme. Crop the video to not include the text unless you feel it can
   add to the design in some way."
2. (Sent while the first was in progress) "Ok I am starting to think the
   video can speak for it self lets go ahead and remove the window
   animations and place them on other parts of the front page that may
   look sparse."
3. Answer to a question (where the reel's animations should go): "Split
   into sections (Recommended)": the Toolbox scene to the Toolbox
   banner, the renderer wipe to Community, the Animation scene to
   "Start building.", dropping the scenes the pillars already show.
4. "Ok the home page overall looks good but we got to do something about
   these two bottom secions and how they are setup, they look a little
   out of place an incomplete/ Can we style these a bit differently and
   make it look more cohesive with the rest of the site. Also go ahead
   and append the conversations to PROMPTS.md according to source
   formatting." (with screenshots of Community and "Start building.")

### Summary

- **Outcome:** The hero is now the Desert Homestead film alone, with no
  reel. The film is a 53 s seamless loop cut from the engine's own film
  (its end card: every frame drawn by the Axcenity Engine renderer, so
  it's captioned "Engine capture · Desert Homestead film"). Only the
  2.39:1 picture is kept, so there's no title, captions or end card.
  Eleven shots run spring → porch → drapes → truck → windmill → storm →
  rain → lamplight → snow → lit door → dawn thaw, back into spring. The
  five lightning strikes are left out, the 1–1.5 s dissolves are the
  only change, and there's no grading. It ships as AV1 (8.2 MB) plus an
  H.264 fallback at 1280×536 (11.4 MB) and a poster. `home.js` plays it
  only when the visitor hasn't paused it, it's on screen and the tab is
  visible; reduced motion shows the poster. The scrim covers only where
  text sits, and the version badge sits on the page colour.
  `BackdropVideo` now takes ordered `VideoSource`s with codecs. The
  reel's player, timeline, scenes, template, `MEDIA["reel"]`, tests and
  docs are deleted. Three new loops built from its drawing modules are
  `toolbox` (Toolbox banner), `wipe` (Community) and `animation` (Start
  building), each with a phone layout, a fallback drawing and a
  seamless wrap. The loop player can now load a capture and picks the
  smallest WebP that covers its frame. After the follow-up, all three
  sections share one split panel (`.split`, `.section-media`,
  `.panel-list`) with the loop alternating sides. Community sets the
  wipe beside the three cards, and Start building sets the pitch,
  buttons and the guide's first three steps (Install, New Project, Play)
  beside the Animation loop. The wipe now holds the built grey room,
  wipes to the capture and sweeps back, so its frame is never empty.
  New `tests/test_canvas.py`, `test_hero.py` and `test_hero_browser.py`
  replace `test_reel.py` and `test_reel_browser.py`; new
  `docs/frontend/canvas.md` replaces `reel.md` and `reel-scenes.md`. 463
  fast and 45 browser tests pass; Ruff is clean. Not committed.
- **Deviations:** The second prompt changed the plan mid-task, from the
  video behind the reel to the video alone. A question settled where
  the animations go, and the user took the recommended split. The
  reel's World, Logic and docking scenes and its logo outro were
  dropped rather than moved, since the pillars already show them. The
  plan and PRD still describe the hero reel; they were left as history.
- **Sideways:** The first screenshots showed the backdrop's caption
  stuck under the reel's: an equally specific `.reel .media-cap` rule
  later in the file overrode its offset, a latent bug from the slot
  commit, fixed then made moot. The light-mode headline was hard to read
  over the truck. This machine's FFmpeg has no libx264 and its VAAPI
  H.264 encoder fails, so the fallback is OpenH264 at 1280 wide. The
  wipe's wrap first failed the seamless test (0.27 % of pixels) because
  its last frame went through `layer()`; it now draws the start state
  directly. `open_home` had to wait for the loops to mount, since it had
  relied on the reel loading after them. Seeking the film in screenshots
  didn't work: Django's dev server answers range requests with a plain
  200, so the video can't seek. Safari won't play `<video>` without range
  support, so production static serving must provide it (noted in
  `media.md`). The user's Community screenshot showed a stale caption
  and an empty wipe frame, because the loop began before the grey room
  had built. In the restyle, `.panel-list { margin: 0 }` overrode
  Tailwind's `mt-auto` and left a 48 px gap under Start building's
  steps; measuring the boxes in Chromium found it.

## 2026-11-23 — Reel outro: centred logo, and a backdrop-video slot behind the hero

### Prompts

1. "Ok my thing now with the top animation is its ending clip I feel that
   I am not a huge fan of the axcenity logo playing out on the bottom
   right I would like it to be centered, additionally I will be having a
   demo video playing in the background, so if we an style it to where it
   can allow the video to show fully and well in the background that
   would be great as well. Please append this session to PROMPTS.md
   according to source formatting."

### Summary

- **Outcome:** The outro's wordmark is centred across the hero, in the
  clear band between the nav and the top of the hero's copy, and shrinks
  when that band is short. The player measures the copy's top and passes
  it to the scenes as `size.copyTop`. The hero has a slot for a demo
  video behind the reel: `HOME_HERO["backdrop"]` (a `BackdropVideo` with
  a file, kind, caption, provenance and poster) is `None` until the file
  is added. When it's set, a muted, looping, `aria-hidden` video fills
  the hero under the canvas with its own caption, the scrims thin to a
  band under the nav and a pool behind the copy, and the player plays
  and pauses the video with the reel (Pause, reduced motion, off screen,
  hidden tab). New tests cover the centring and clearance in Chromium at
  1280×720, 1920×1080 and 390×844, the video markup and its rules, and
  the manifest refusing a mislabelled or unplayable video. 472 fast and
  46 browser tests pass; Ruff is clean. `reel.md` and `reel-scenes.md`
  are updated. Not committed.
- **Deviations:** None asked. The request didn't say where the video
  comes from or what it shows, so it's an empty, documented slot rather
  than a placeholder file; its caption must say whether it's an engine
  capture or illustrative.
- **Sideways:** The first fix centred the logo horizontally at the
  stage's height. Screenshots showed it nearly touching the badge at
  1440×900, and measuring showed the copy starts 200 px down at
  1280×720, so it would have sat on the headline. The logo now follows
  the copy's measured top. A `pkill -f` that matched its own shell ended
  one screenshot command early; the server was stopped separately.

## 2026-11-23 — Axcenity Hub: Phase 4/17, a moving reel (Toolbox, Animation, Renderer, World, Logic) and animated icons

### Prompts

1. "Ok I still think that the top window animations are lacking, primarily
   because the first part contains a lot of movement and action, and the
   second part does not contain much at all. I think we can get away with
   showing more engine based features such as character animation or the
   built in toolbox, I want to have maybe a few ares that pause but
   overall I want movement throughout the animation. Next for the text
   Build Script Test Export and Free Rust 3 OS and Alpha I would like to
   add some subt animated icons that show while scrolling. Please append
   this sessions to PROMPTS.md according to source formatting"
2. (Asked which storyboard to build, since the plan's renderer wipe needs
   a graybox capture that doesn't exist) "~26 s: add all of them"
3. "Ok so a few things with these icons I would like them to be bigger
   and to the left  of the text and to the right of the numbers also I
   want them to re-animate when scrolled back to"
4. (With a screenshot of the Test and Export steps) "Ok the three and the
   4 look messed up but other than that go ahead and commit and push the
   repository and append the conversations to PROMPTS.md."

### Summary

- **Outcome:** The reel's back half moves throughout. It now runs 26 s
  with six scenes (Workspace, Toolbox, Animation, Renderer, World, Logic)
  and the logo lockup. Each scene picks up the workspace exactly where
  the last one left it, with short holds between bursts of pointer
  action. The Workflow steps and the stat band have line icons that draw
  in when they scroll into view, then make one small move each. 469 fast
  and 35 browser tests pass; Ruff is clean. This builds Phase 4,
  re-scoped, and its boxes are ticked.
- **Changes:**
  - Two read-only agents gathered the engine facts first: the Toolbox
    (`crates/editor-toolbox`) and the Animation pane
    (`crates/editor/src/animation/`, the humanoid rig and Wave state).
  - `static/reel/scenes/`:
    - New `toolbox.js`: the Assets pane's Toolbox button, a "rock"
      search, the cards popping in, a card dragged onto the Pad, the
      Console's download lines, and the Pad textured.
    - New `animation.js`: Clips & Rigging, Record, the pointer posing
      the hand while key columns pop into the dope sheet, then two
      passes at 1.5× as the character waves.
    - New `renderer.js`: a drawn grey room building up, wiped by an
      accent scan line into the real capture, with a slow push-in.
    - New `world.js`: Raise / Lower brushing hills, then Scatter
      painting plants.
    - New `logic.js`: a Script tab in Graph view, the pointer dragging
      the exec wire, the Luau typing out, a pulse.
    - `workspace.js`: `drawWorkspace` takes a `view` (the `REST` state
      later scenes change), plus `viewWorkspace` and `pointerPath`.
      Each scene exports its end view, and the next one builds on it.
    - `lockup.js` takes away the Logic scene's last frame. The old
      placeholder scenes are gone.
  - `static/reel/drawing/`:
    - New `toolbox.js`, `animation.js` (the Wave clip, the mannequin,
      the dope sheet, the transport) and `renderer.js` (the grey room
      laid out over the capture's 1280 × 720 space, and the wipe).
    - `editor.js`: a textured Pad, the Assets pane's Toolbox button, a
      chosen Terrain tool, Console lines that arrive and scroll, and
      exported primitives.
    - `layout.js`: a movable bottom split, compact widening and
      `innerOf`.
    - `blocks.js`: `pinAt`.
  - `timeline.js`: six scenes, `DURATION` 26, `LOCKUP_FRAME` 25.
  - `canvas.js`: the accent token, for the scan line only.
  - `player.js`: loads the renderer capture's 1920 px WebP into
    `images.capture`. The template passes it as `data-capture`.
  - `marketing/content.py`:
    - `TERRAIN_LABELS` and `LOGIC_LABELS` are now shared by the pillar
      loops and the reel.
    - New `REEL_TOOLBOX`, `REEL_TOOLBOX_LOG`, `REEL_ANIMATION` and
      `REEL_SCRIPT`.
    - A rewritten reel description and provenance, and segment names
      for all six scenes.
    - `Item.icon` for the workflow steps and stats.
  - Icons:
    - `partials/icon.html`: eight motifs (build, script, test, export,
      free, rust, os, alpha), drawn on `pathLength="1"`.
    - `workflow.html` and `facts.html` place them.
    - `source.css`: the Motifs rules. Every hidden stroke and every
      animation waits behind `html[data-reveals] [data-reveal][data-in]`,
      and reduced motion shows them drawn.
  - Tests:
    - `test_reel.py`: the new registry, the description walks the
      scenes in order, segment names, the wipe's capture is a real
      derivative that's never upscaled, and only the scan line draws
      with the accent.
    - `test_reel_browser.py`: six markers, 26 s, the lockup at 25 s.
    - `test_home.py`: every step and stat has a decorative motif, and
      the motif CSS is reveal-gated and at rest under reduced motion.
  - Docs:
    - New `docs/frontend/reel-scenes.md`: each scene, the view chain and
      the pointer. Scene 1's section moved there, so `reel.md` stays
      under 200 lines.
    - Updated `reel.md`, `home.md` (Motifs), `theme.md` (the accent's
      uses), the `FRONTEND.md` index, the PRD storyboard and Phase 4 in
      the plan.
- **Deviations:**
  - Recommended keeping 18 s with Toolbox, Animation and Logic. The user
    chose the ~26 s loop with all of them, which goes past the PRD's
    15–18 s, so the PRD and the plan were updated to match.
  - The renderer wipe's grey end is drawn rather than captured: no
    same-camera graybox capture exists.
- **Sideways:**
  - On the first browser check the reel fell back to the still image. A
    new parameter named `bottom` clashed with a `bottom` rectangle in
    `workspaceLayout`. A Playwright error probe caught it.
  - `test_home` failed on "Clips & Rigging". It didn't allow for
    `json_script` escaping `&` as `&`, so the test was fixed, not
    the engine's label.
  - The first icon screenshots showed no icons. The dev server ran with
    `--noreload` and served stale templates; a restart fixed it.
  - Review of the rendered frames found three problems, all fixed:
    - The floating Properties window covered the Scatter tab and Paint
      button the pointer clicks, so it now aims at their left edge.
    - The mannequin's limbs nearly vanished against its preview, so
      they got more contrast.
    - At 360 px the compact Logic scene's fourth tab was clipped, so
      Script takes the Toolbox tab's place there.
- **Follow-ups (prompts 3 and 4):**
  - The icons were enlarged and moved:
    - Workflow icons sit right of the numeral (`.flow-head`, 40–64 px).
    - Facts icons sit left of the title (`.stat-title`, 0.8 em, about
      58 px at the large size).
  - The icons now replay. `home.js` sets `data-on` once an icon is 60 %
    in view and clears it only when it's fully off screen
    (`html[data-motifs]`), so scrolling back plays it again. Before its
    first play an icon is hidden, so it's never seen half-drawn.
  - The "left of the text, right of the numbers" request was read as:
    Workflow icons go right of the numerals, Facts icons left of the
    titles (Facts has no numbers).
  - With an icon beside them, "Alpha" and "3 OS" overflowed their
    columns at 360, 768 and 1024 px (measured in Chromium). The stat band
    now uses one column on phones, two from `sm` and four from `lg`, and
    its titles reach `text-7xl` only from `xl`.
  - New `tests/test_home_browser.py`: replay on return, reduced motion,
    and no overflow at six widths. Total: 469 fast and 43 browser tests.
  - The broken outlines on the 3 and 4 numerals came before this
    session's changes. The display face builds those glyphs from
    overlapping shapes, and `-webkit-text-stroke` outlined every seam.
    The stroke is now 2px, painted under a fill in the page colour
    (`paint-order: stroke fill`), which leaves a clean 1px outline;
    checked in dark and light.
  - Committed and pushed to `main`, as earlier phases were.
  - Sideways: a CSS test treated the Test icon's ripple ring as a leak.
    The ring is meant to be invisible at rest, so the test exempts it by
    name.

## 2026-11-23 — Axcenity Hub: Phase 5/17, Feature media

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 5`.
2. (Approval of the brief) "Approved, build all of Phase 5"

### Summary

- **Outcome:** Final media for every Home pillar, built before Phase 4,
  as asked. The Renderer pillar shows the 2560×1440 ray-traced capture as
  a `<picture>` of AVIF, WebP and JPEG derivatives. World, Logic and
  Editor show animated canvas recreations drawn from the engine's UI
  sources, with their old drawings as no-JavaScript fallbacks. The
  manifest records kind, provenance, source size and display sizes per
  breakpoint. 485 tests pass (450 fast, 35 browser); Ruff is clean.
- **Changes:**
  - `marketing/media.py`, `marketing/management/commands/make_media.py`:
    the media pipeline. Widths 640–2560 that never exceed the source;
    AVIF 80, WebP 90 and JPEG 88; idempotent, with `--force`; refuses a
    source whose size disagrees with the manifest.
  - `marketing/media_sources/renderer-2560x1440.png`: the capture, moved
    out of `static/` so it's never served; `static/marketing/media/renderer/`
    holds its 15 derivatives.
  - `marketing/content.py`:
    - `Media` now has `source`, `display` (`Display` with `sizes` and
      breakpoints), `loop` and `fallback_alt`, with validation.
    - The editor's words are shared constants for the reel and the
      Editor loop.
    - Labels and provenance for the three loops; `LOOP_CONTROLS`.
  - `marketing/drawings.py`: `luau_lines` now follows the editor's
    `lua_syntax.rs` (keyword, literal, builtin, number, string, comment,
    and the rule that a name after `.` or `:` is a field).
  - `templates/marketing/media/`: new `picture.html`. `frame.html`
    renders a capture or a loop (canvas, description, fallback, pause
    button). `reel.html`'s fallback uses `<picture>`. The fallback
    drawings use `fallback_alt`, and the Luau one is in syntax colours.
  - `static/reel/loops/`: `main.js`, `player.js` (plays only on screen,
    visible and current; reduced motion shows the still; `loop-seek`
    event), and `editor.js`, `terrain.js` and `logic.js` (12 s each,
    seamless, each with a layout below 480 px).
  - `static/reel/drawing/`: `blocks.js` (block Graph view), `code.js`
    (typed Luau) and `terrain.js` (heightfield, brush ring, plants,
    Terrain Studio and Scatter panes), ready for Phase 4's Scenes 3–4.
  - `static/reel/canvas.js`:
    - `groupLayer`, shared by the reel player and the loop player.
    - `logicalSize` measures the layout box, ignoring transforms.
    - New content tokens.
  - `styles/source.css`:
    - Luau syntax tokens; dark values are the editor's, light values are
      darkened to 4.5:1 on the site's grey.
    - Node header and pin tokens.
    - Rules for the picture, the loop frame and button, and the capped
      hero fallback.
  - `templates/marketing/home/facts.html`: the stat titles step up to
    `text-7xl` only from `lg` (they overflowed by 2 px at 768).
  - Tests:
    - New `tests/test_media.py` and `tests/test_media_browser.py`.
    - `test_home.py`: derivatives at real size, no upscaling on 2×
      screens, picture markup, Luau token kinds.
    - `test_theme.py`: content colours derived from the engine's values
      and rules, new contrast pairs.
    - `test_reel.py`: the purity rules now cover the loops.
    - `open_home` and the browser helpers moved to `conftest.py`.
  - Docs: new `docs/frontend/media.md`. Updated `home.md`, `reel.md`,
    `theme.md`, `FRONTEND.md`, `ARCHITECTURE.md`, `TESTING.md`, and
    `CLAUDE.md` (the `make_media` command and a "Read before…" row).
    `.gitignore` now covers `screenshots/`.
- **TDD:** Skipped, as the plan says for this phase: the media is visual,
  and the manifest checks test data rather than drive code. Everything
  got ordinary tests, including a seamless-wrap check for each loop.
- **Decisions:**
  - Recreations are canvas loops sharing the reel's contract and
    helpers, so Phase 4 can reuse them.
  - The static drawings stay as finished no-JavaScript fallbacks.
  - The hero fallback is capped at 1280×720 CSS pixels (half the
    source).
  - A capture's display sizes record its drawn size: 10/9 of the frame,
    since 16:9 covers 16:10.
  - Compact layouts apply below 480 px.
  - Each loop has a pause button (WCAG 2.2.2).
  - The brush ring and drop preview are drawn in ink, not the editor's
    accent.
  - Pin colours stay the editor's in both schemes. They're exempt from
    contrast tests because each row is labelled.
- **Deviations:** None. Phase 4 isn't built; the user asked for Phase 5
  first.
- **Sideways:**
  - The block nodes were first assumed to be the generic node graph's
    (red Events, blue Actions). A background search of the engine found
    that the block editor's Graph view uses "When Touched" (Events,
    Amber) and "Spawn Decal" (Looks, Violet), so the nodes follow that.
  - AVIF at quality 60 smeared the capture's dark wall panels (seen in
    a side-by-side crop), so quality went up to 80.
  - The keyword colour's derivation differed by one unit until the test
    used Rust's round-half-away rounding (`#8900AB`).
  - The browser tests caught three real bugs:
    - A negative canvas radius when hidden inline frames measured 1×1.
    - Stage canvases 3 % too small, because the size was measured
      mid-transform.
    - A 2 px sideways scroll at 768 px from the stat band.
  - A check by eye with no canvas found the hero fallback's caption
    over "Read the docs"; it moved to the top right.
  - Found and not fixed (out of phase): at 768–~860 px the nav's links
    don't fit, "Sign in" wraps and the Download button sits off screen.

## 2026-11-23 — Axcenity Hub: Phase 3/17, Reel engine and Scene 1

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 3`.
2. (Approval of the brief, with changes) "Ok looks good but I would just
   make sure of a few things: resolve the inconsistency between scene
   boundaries and segment transitions. The controls should distinguish
   between four scene markers and the beginning and end of the timeline.
   Make sure that seeking has 18 seconds wraps or resolves consistently to
   the loops first frame. I like drawng the panels on a canvas rather than
   using the DOM/SVG but I think it would be a good idea to enforce
   deterministic scene rendering. make sure that rendering does not mutate
   a scene, seeking should not depend on previous freams, resizign should
   not change the animation timing, all scene coordinates must device from
   logical dimensions not physical canvas pixels, scene transitions should
   work when seeking directly in the middle of the scene. Also I would like
   you to improve accesiblity features with playback behavior, respect the
   reduced motion preference changes while the page is opened, do not
   autoplay when the brower is hidden, ensure that the keyboard controls do
   not interfere with range-input navigation, provide a meaningful fallback
   when the canvas is not supported and ensure that the screen reader
   description explains teh workspace and its undocking behavior not just
   that the animation is playing. Keep scenes 2-4 but make sure they are
   actual registered scene implementations rather than special timeline
   cases each should satisfy the same scene contract start duration,
   render(context,time,size) this is so that phase 4 can replace the
   implementaition without changing the engine."
3. (After the commit) "Ok I like the animations a lot now I just feel like
   there could be more stuff on the left where the page is somewhat empty
   maybe dragging around windows and making the actual properties windows
   look more like my engine. Also when it fades into the Axcenity logo it
   looks a little bit glitched but not toobad if that caould be adjuststed
   slightly as well. Essentially expand the amount of windows and dragging
   to make it look cooler."

### Summary

- **Outcome:** The showcase reel now runs behind the hero, in place of the
  renderer capture, which becomes its fallback. It has:
  - an 18 s timeline of five registered segments: Scene 1, placeholder
    Scenes 2–4 and the lockup outro
  - a master clock with seek and wrap
  - a HiDPI canvas capped at DPR 2
  - controls: play/pause, a scrubber with four scene markers, Space, and
    ←/→ jumps
  - autoplay only while 30% or more is on screen in a visible tab
  - reduced-motion handling that follows changes live
  - a compact phone layout
  - a no-canvas fallback
  - a screen-reader description of the workspace and the undocking

  Scene 1 shows kinetic panel names shrinking into tabs as the panels
  spring into the editor window, then Properties undocking onto a second
  monitor. 335 tests pass (325 fast, 10 `browser`), and Ruff check and
  format are clean. 7 of the 8 criteria are ticked. The ~60 fps criterion
  is left for a check on a real laptop.
- **Changes:**
  - `static/reel/main.js`: the entry. It checks for a 2D canvas, loads the
    player, and falls back on any failure.
  - `static/reel/player.js`: draws the frame for the clock's time in
    logical pixels. Also handles the controls, keyboard, visibility,
    reduced motion, theme and resize.
  - `static/reel/timeline.js`: the registered segments, checked against
    the contract on load. Also the scene markers (0, 4, 8, 12), `wrap` (18
    s is 0), `segmentAt`, the marker jumps and the clock.
  - `static/reel/easing.js`: pure helpers, including a closed-form spring.
  - `static/reel/canvas.js`: the pixel-ratio cap, the logical size, the
    logical-pixel transform, token reading and logo tinting.
  - `static/reel/scenes/`:
    - `workspace.js`: Scene 1, and the resting workspace.
    - `renderer.js`, `world.js`, `logic.js`: real scene modules that show
      the resting workspace until Phase 4 replaces them.
    - `lockup.js`: the outro, ending on the empty first frame.
  - `templates/marketing/media/reel.html`: the figure with its canvas,
    fallback capture, caption and description. Also the inline probe, the
    labels as JSON, the controls and the module script.
  - `templates/marketing/home/hero.html`: includes the reel (`.hero-copy`
    for the phone reserve).
  - `marketing/content.py`: `MEDIA["reel"]` (illustrative, with the
    description as its alt and the drawn words as labels),
    `REEL_CONTROLS`, and the hero's `reel`, `reel_controls` and
    `fallback`.
  - `styles/source.css`: the reel, its fallback and the controls.
    Changes:
    - The accent gains `.reel-fill`.
    - Hover sits behind the hover gate.
    - The phone copy reserve.
    - `.hero-backdrop` is removed.
  - `tests/test_reel.py` (new): markup, labels, fallbacks, the contract and
    the determinism rules as written, and the editor's pane names and Dark
    theme.
  - `tests/test_reel_browser.py` (new): 8 Playwright tests. Every request
    except the live server's is aborted.
  - `tests/test_home.py`: the visible-text parser skips `<script>`, and
    the hero image is now the lazy fallback.
  - `tests/test_theme.py`: the accent's uses, and the reel's contrast
    pairs and rules.
  - `pyproject.toml`, `uv.lock`: `pytest-playwright`.
  - `docs/frontend/reel.md` (new). Also updates to the FRONTEND index,
    `home.md`, `theme.md`, `TESTING.md` (rows and a Playwright section)
    and `ARCHITECTURE.md`.
  - `plans/axcenity-hub.md`: ticks.
- **TDD:** skipped, as the plan says. The behaviours show only in the
  browser, and the PRD rules out JavaScript unit tests. The Playwright
  tests and the fast contract tests cover them.
- **Decisions:**
  - **Canvas, not DOM/SVG.** The panels are drawn on the canvas, unlike
    the PRD. The user approved it.
  - **Colours from the tokens.** Colours come from the site's tokens at
    runtime, and the dark tokens are pinned by tests to the editor's Dark
    `ThemeTokens`.
  - **Panel names** come from `Pane::label`: Scene View, Explorer and
    Properties.
  - **Markers and the outro.** The lockup is an outro segment with no
    marker. ← within 0.3 s of a marker goes back to the one before it,
    and both arrows wrap.
  - **Logo.** The lockup draws the wordmark alone, since the image already
    includes the mark.
  - **Controls.** They stay visible while paused, so reduced motion's Play
    shows. The range keeps its native arrows (0.1 s steps).
  - **Fallback.** It is the lazy renderer capture, hidden before layout by
    an inline probe, so browsers that run the reel never download it.
- **Deviations:** In the brief, the scrubber ticks (4, 8, 12, 16) and the
  arrow stops (0, 4, 8, 12, 16) didn't agree. At the user's request they
  now use the same four scene markers, and the start and end of the
  timeline are told apart from them. The user also asked for stricter
  determinism, live reduced motion, no autoplay in hidden tabs, range
  arrows left alone, a canvas fallback, a fuller description, and Scenes
  2–4 as real registered modules. All are built and tested.
- **Sideways:**
  - The lockup first drew the mark next to the wordmark, which already
    contains it. Caught in screenshots.
  - On phones the copy covered the compact workspace. The fix reserves
    its height in CSS, less the section's nav padding. The first try
    missed that padding; screenshots caught both.
  - The dev server ran with `--noreload` and served stale templates for a
    round of screenshots.
  - The live reduced-motion test failed twice:
    - `prefers-reduced-motion`'s `MediaQueryList` was held only by its own
      listener and could be garbage-collected. `update()` now reads it.
    - The test switched the setting twice within one frame, so the
      switches cancelled out. It now waits on `data-motion`.
  - A test helper seeked with only an `input` event, which left the
    scrubbing flag on. The helper now also fires `change`, and marker
    jumps clear the flag.
- **Follow-up (prompt 3):** The work after the first commit.
  - **Scene 1 rebuilt** on the editor's real default dock (`layout.rs`):
    - Scene View | Animation | UI Designer, with Console | Assets |
      Profiler below.
    - Explorer above Properties | Terrain.
    - Tabs styled as egui_dock's.
    - The window is titled "Arena - Axcenity Editor".
  - **Two pointer drags.** Properties moves to "Monitor 2" on the right,
    and the Console to "Monitor 3" in the empty upper left. Each tears off
    to window size, lifts and bobs on drop. Terrain and Assets take over
    the docked places.
  - **Properties** now follows `properties.rs`:
    - the Pad/Part header and the filter field
    - the Data, Appearance, Behavior and Part sections, with chevrons,
      fields, checkboxes and a swatch
    - Part's real defaults
  - **Console** follows `output.rs`, `console.rs` and `session.rs`: the
    timed project-opened line, a `select` echo and the command-line hint.
  - **Lockup.** The workspace now fades as one picture through
    `context.layer` (an offscreen buffer). Before, every piece faded
    separately, so overlapping windows showed through each other; that
    was the "glitch". The wordmark now arrives once the workspace is
    mostly gone.
  - **Gradient.** The hero gradient now darkens only the bottom left,
    behind the copy.
  - **Code split.** Drawing moved into `static/reel/drawing/` (`layout.js`,
    `editor.js`), which falls under the same purity tests.
  - **Tests.** 350 pass (340 fast, 10 browser), and Ruff is clean. New
    tests cover:
    - the default dock
    - the Properties sections and values
    - the Console messages
    - every drawn font being preloaded
    - every token resolving in both schemes
  - **Sideways:**
    - The Terrain tool buttons drew as bright bars. Tailwind v4 drops
      `--color-control` in dark mode because no utility used it, so the
      canvas got an empty colour and kept its previous fill. The fix
      switches the theme to `@theme static`.
    - The determinism test caught Inter 500 being drawn before it had
      loaded, which made the first frame differ. It's now in `FONTS`.
    - The browser suite failed about one run in three. The `pause()`
      helper read `data-state` before the visibility observer had fired.
      It now uses `data-intent`, and six runs in a row pass.
    - In light mode the colour swatch was drawn dark while its value
      reads 163, 163, 163. It now uses the token nearest that grey in
      each scheme.

## 2026-11-23 — Plan a dedicated documentation site (Phases 6B–6C)

### Prompts

1. "Ok I noticed that the documentation page takes the users to my GitHub
   repo this is fine but my site should not rely on my GitHub page as the
   source of information as it is not styled for efficiency or use. Please
   add onto the plan to include a dedicated documentation page featuring
   all core engine features from the official repository guide and API
   references. These have all been documented in my engine for better or
   worse. Keep the stling similar to the rest of the site making it look
   cohesive, also append this conversation to PROMPTS.md according to
   source formatting."

### Summary

- **Outcome:** Planning only; no app code. Two phases were added to
  `plans/axcenity-hub.md` after the Toolbox page, so the first slice is now
  Phases 1–6C:
  - **Phase 6B, Documentation site:** a `documentation` app at `/docs/`
    in the marketing shell. It serves a committed snapshot of the engine's
    `documentation/` folder (the GitBook source: `SUMMARY.md`, 20 Learn
    chapters, the reference pages, seven diagrams) copied by a
    `sync_engine_docs` command that records the engine commit. It has a
    `SUMMARY.md` sidebar, an "On this page" rail, previous/next, Luau
    highlighting in the editor's colours, copy buttons, status badges,
    the Alpha notice and a "View source on GitHub" link per page. The nav,
    Home CTA and footer Docs links move to `/docs/`. TDD: link rewriting,
    the `SUMMARY.md` nav tree, and the sync command.
  - **Phase 6C, API reference:** the ~140 classes and ~45 data types and
    services, plus enums, libraries and globals, as a filterable API home,
    member tables, linked signatures and inherited members, and a
    `/docs/search/` over titles, headings and member names. TDD: API page
    parsing and search ranking.
- **Changes:** `plans/axcenity-hub.md` (the two phases; the
  `documentation` app, the `/docs/` URLs and a "documentation source"
  rule in the architectural decisions; the first slice is now 1–6C).
  `prd/axcenity-hub.md` (stories 74–79 under a new Documentation heading,
  a Documentation implementation-decisions section; Docs now points at
  `/docs/`, and the "until a docs area is planned" note was replaced).
- **Decisions:**
  - The engine repo stays the only source of truth: the Hub copies a
    snapshot and never edits or fetches pages at request time, keeping the
    reference-repos-are-read-only rule and the no-network test rule.
  - The docs got letter-suffixed phases (6B, 6C) instead of renumbering
    7–17, because commits, PROMPTS.md and the docs already cite those
    numbers. They come before Download because they are public, need no
    external API, and remove the site's main reliance on GitHub.
  - The guide and the API reference are separate phases: the guide ships
    first through a generic pipeline, then the ~190 generated API pages
    get their own layout and search.
  - The engine's seven diagrams (1200 px) are labelled "Diagram"
    (illustrative) per the honesty rule, shown no wider than their source.
  - The PRD was extended (stories 74–79) so the new phases have stories
    to cite; the request named only the plan.
- **Deviations:** None. No questions were asked; the placement and the
  6B/6C split were chosen by the agent and are open to change.
- **Sideways:** Nothing went wrong. The checks done while planning: the
  engine docs are plain Markdown with no GitBook `{% %}` blocks, raw HTML
  or nested lists (the engine's own checks refuse them), so a standard
  renderer is enough. Story 58 already asked for documentation search, and
  Phase 6C now covers that part.

## 2026-11-23 — Axcenity Hub: Phase 2/17, Home content

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 2`.
2. (Approval of the brief, with changes) "Looks good I would just change a
   few things: Replace OnTriggerEnter and SpawnDecal with When touched and
   Spawn decal and use the actual Luau translation:
   part.Touched:Connect(function(otherPart) … workspace:SpawnDecal(…))
   This should be consistent throughout the home page, reel and future
   docs. I like the idea of copies in content.py, but make sure that the
   test does not accidentaly reject legitimate accesibiliy labels. Test
   the acutal user facing prose and labels rather than making every test
   node orignate from the content module. Other than that move to
   development"

### Summary

- **Outcome:** The full Cinematic Home, rendered from `marketing/content.py`:
  - the hero: version badge, rotating headline, pitch and both CTAs, over
    the real ray-traced capture
  - four sticky-scroll feature pillars, the workflow strip, the stat band,
    the Toolbox banner, the coming-soon community row and the final CTA
  - expo-out reveals, and a media manifest with honest captions
  253 tests pass (251 fast, 2 `browser`). Ruff check and format are clean.
  All six Phase 2 criteria are ticked.
- **Changes:**
  - `marketing/content.py` — all Home copy (`HOME_*`), `ENGINE_VERSION`,
    `LUAU_SAMPLE`, the `Media` manifest (kind, caption, alt, provenance,
    file and pixel size or drawing template; refuses mislabelled items),
    and `Link.fragment` for the nav's new Features link (`/#features`).
  - `marketing/drawings.py`, `marketing/templatetags/home_tags.py` — the
    terrain wireframe geometry and the Luau tokenizer for the drawn media.
  - `marketing/views.py` — `HomeView` passes each section's content.
  - `templates/marketing/home.html`, `templates/marketing/home/*.html` —
    one partial per section.
  - `templates/marketing/media/` — the media frame and the drawn
    stand-ins (terrain SVG, monochrome Luau sample, editor docking layout).
  - `templates/partials/nav_link.html` — a fragment link is never marked
    as the current page.
  - `static/js/home.js` — rotation, reveals (gated so nothing hides
    without JavaScript), the pillars' sticky stage.
  - `static/marketing/media/renderer-2560x1440.png` — copied from the
    Showcase captures.
  - `styles/source.css` — the Home styles; the reduced-motion block forces
    reveals to their final state.
  - `tests/test_home.py` (new), `tests/test_shell.py` (Features in the
    nav; internal hrefs must resolve and fragments must exist),
    `tests/test_theme.py` (eleven new contrast pairs and their rules).
  - `docs/frontend/home.md` (new); FRONTEND, ARCHITECTURE, TESTING and
    theme.md updated.
  - `prd/axcenity-hub.md`, `plans/axcenity-hub.md`, `CLAUDE.md` — When
    touched → Spawn decal and its real Luau translation everywhere
    OnTriggerEnter → SpawnDecal was named (story 22, the reel storyboard,
    Phase 4); CLAUDE.md's Honesty rule now says so.
- **TDD:** Skipped, as the plan says: copy, data and layout. The link,
  media and honesty checks are ordinary tests.
- **Decisions:**
  - Checking the engine showed there is no OnTriggerEnter block; the real
    blocks are When touched and Spawn decal (the user then made this the
    rule everywhere).
  - Media until Phase 5: the real renderer capture, and drawn stand-ins
    captioned "Illustrative" for World, Logic and Editor. The Luau sample
    is monochrome because the editor's syntax colours aren't in the palette.
  - The renderer capture sits behind the hero until Phase 3's reel.
  - The Toolbox banner's CTA is "Soon" until Phase 6. Its repo is on a
    personal account, so it isn't linked yet.
  - The rotating headline stacks every phrase in one grid cell, so its
    height is the longest phrase's at every width with no measuring.
  - Each pillar got an id (`#feature-world`) for deep links.
- **Deviations:** The user changed the copy test: it checks the visible
  prose and labels a visitor reads, and lets screen-reader-only labels and
  attributes (aria-label, alt) be written in templates. It was
  mutation-checked: a hard-coded sentence fails it, and an sr-only label
  doesn't.
- **Sideways:**
  - Headless Firefox screenshots don't scroll to anchors, so sections were
    shot through iframes on a scratch server with framing allowed (the
    project's settings were untouched).
  - With `--noreload`, Django's cached template loader kept serving old
    templates; the server was restarted with auto-reload.
  - The stage didn't swap in screenshots, because the IntersectionObserver
    hadn't reported yet; `home.js` now picks the current pillar
    synchronously at start, which also fixes `#feature-…` links.
  - The terrain drawing was too flat at first; the relief and tree size
    were raised.
  - The test that every content string renders caught that the Luau
    sample's alt text never reached the page; it's now a screen-reader
    summary before the code.
  - Phone captions wrapped, so they were shortened.
  - Not watched live: the rotation itself. It's guaranteed by the shared
    grid cell (tested) and was checked as static layouts at 360 and
    1440 px.

## 2026-11-23 — Axcenity Hub: Phase 1/17, Skeleton, theme and marketing shell

### Prompts

1. The `/implement` skill, given `axcenity-hub.md phase 1`.
2. (Approval of the brief, with additions) "It looks good I would just add
   these things: Theme cookies set an explicit SameSite=Lax for secure in
   production and appropriate lifetimes, validate the incoming themes
   against the system, light nd dark. Never trust arbitrary values. Test
   the contrast aith the actual foreground/background combinations
   including buttons links focusing and indicators not just using the
   primary blue. Make the loopback exemption narrow in scope to test the
   browsers required address do not broadly exempt localhost or disable
   the netwrokguard for browser tests. Other than that continue to the
   build"

### Summary

- **Outcome:** A runnable Django 6.1 project (uv, Python 3.13) with:
  - the axcenity theme foundation ported from the Toolbox
  - the marketing shell: fixed nav that goes solid on scroll, a phone
    menu, the System/Light/Dark switch, and the four-column footer
  - a bare Home at `/`
  - the test layout, with a network guard that has one narrow
    browser-test opening
  - the four docs
  188 tests pass (186 fast, 2 `browser`). Ruff check and format are clean.
  All six Phase 1 criteria are ticked.
- **Changes:**
  - `pyproject.toml`, `uv.lock`, `.python-version`, `manage.py`: the
    project. Ruff and pytest config; `--strict-markers`; the `browser`
    marker; `--liveserver=127.0.0.1`.
  - `.gitignore`: ignores the built CSS and `.django_tailwind_cli/`.
  - `config/settings.py`: env-driven DEBUG, secret key and hosts. Lax
    cookies, Secure when DEBUG is off (`THEME_COOKIE_SECURE`). DaisyUI
    loads as the official plugin.
  - `config/theme.py`, `config/context_processors.py`: the validated
    `ax-theme` cookie (three exact values, Lax, one year, Secure in
    production).
  - `config/urls.py`, `wsgi.py`, `asgi.py`: root URLs and entry points.
  - `marketing/`:
    - `content.py`: nav, footer and Home copy and links as data, with a
      `Link` type that refuses ambiguous targets
    - `views.py`: `MarketingPageMixin`, `HomeView`, and `ThemeView` (the
      POST fallback; 400 on unknown values; same-site `next` only)
    - `urls.py`
    - `templatetags/shell_tags.py`: `versioned_static`
  - `templates/base.html`, `templates/marketing/shell.html` and `home.html`,
    and the `partials/` (`site_nav`, `site_footer`, `nav_link`, `icon`): the
    shared document with the pre-paint scheme script, the marketing shell,
    and the bare Home.
  - `styles/source.css`: tokens (dark and light storm grey), the accent
    as the `primary`/`accent` role, fonts, focus ring, buttons, nav and
    footer, the hover gate on every `:hover`, the spotlight, lift and
    blur-up primitives, and reduced motion.
  - `static/js/shell.js`: hover gate, the validated theme switch, nav
    scroll state, spotlight.
  - `static/fonts/` (copied from the Toolbox) and `static/brand/` (copied
    from the engine's `assets/branding/`).
  - `tests/`:
    - `conftest.py`: `NetworkGuard`, plus the `browser_server` fixture that
      opens exactly `127.0.0.1:<live port>`
    - `test_theme.py`: ported, plus contrast checks pair by pair in both
      modes, tied to their CSS rules
    - `test_shell.py`, `test_theme_switch.py`, `test_network_guard.py`
    - `test_browser_server.py`: marked `browser`
  - `docs/ARCHITECTURE.md`, `docs/FRONTEND.md`, `docs/frontend/theme.md`,
    `docs/TESTING.md`: the docs `CLAUDE.md` points to.
  - `plans/axcenity-hub.md`: Phase 1 criteria ticked.
- **TDD:** Skipped. The plan lists no TDD behaviours for Phase 1 (setup
  and a port of tested Toolbox rules). Tests were written alongside the
  code.
- **Decisions:**
  - **Accent:** `#19A0FF` / `#0B67B8` is DaisyUI's `primary` and
    `accent`. The dark-mode primary text is `#171717`, because white on
    the blue is 2.8:1.
  - **Nav links with no page yet:** Sign in, Toolbox and Community are
    "Soon" labels, never links. Features stays out of the nav until
    Phase 2.
  - **Docs link:** points to the engine repo's `documentation/` folder,
    since `axcenity.com/docs` isn't confirmed.
  - **Phone menu:** a `<details>`, so it works without JavaScript.
  - **Theme fallback:** the no-JavaScript view lives in `marketing`
    because `accounts` doesn't exist yet.
  - **Hover gate:** now covers buttons too.
  - **New packages:** none until a phase needs one.
  - **Visual polish:** menu links hug their labels, so the current-page
    underline doesn't read as a divider.
- **Deviations:** The user approved the brief and added three
  requirements, all built:
  - **Theme cookie:** explicit `SameSite=Lax`, `Secure` in production and
    a one-year lifetime. The value is validated against
    system/light/dark on every read and write, including in the inline
    script and `shell.js`. Hostile cookie and POST values are tested.
  - **Contrast:** tests cover the real pairs (text, links, both button
    types at rest and hovered, the focus ring, the badge dot, the
    current-page underline, icons) in both modes, rather than only the
    primary blue.
  - **Network guard:** the browser-test opening is an exact
    IP-literal-and-port allow-list, refused for unmarked tests,
    hostnames, non-loopback IPs and other ports.
- **Sideways:**
  - django-tailwind-cli 4.10 warned that the Toolbox's tailwind-cli-extra
    DaisyUI route is deprecated. Switched to the official plugin bundles
    before writing the theme tests.
  - The `browser` test passed alone but returned a 500 in the full run.
    Loading `live_server` lazily skipped pytest-django's automatic
    `transactional_db`. Fixed by requesting it first.
  - Python's cookie jar refused a control-character test value, so
    hostile-cookie render tests now send a raw `Cookie` header.
  - Headless Firefox screenshots ignore scroll state, so the solid nav and
    footer were checked on a copy of the page with `data-scrolled`
    preset. That copy used fallback fonts (a `file://` CORS limit, not a
    site bug).
  - Forcing dark mode in headless Firefox needed `ui.systemUsesDarkTheme`
    as well as the content override.

## 2026-11-23 — Plan re-check against the PRD (`/prd-to-plan`)

A new session after `/clear`, starting from `HANDOFF.md`.

### Prompts
1. "@HANDOFF.md /prd-to-plan @prd/axcenity-hub.md - Also please append
   this session and all conversations to PROMPTS.md according to source
   formatting."
2. (Plan quiz answers) Granularity: "Keep as is (Recommended)". Fixes: all
   four ("API before assets exist", "Reel doc + test count", "Report model
   ordering", "Verification gate"). Bug-report limit: "5 per day
   (Recommended)".
3. "Go ahead and run through the plan and use the TDD skill to determine
   which phases need TDD if absolutely necessary"
4. "yes, record them in the plan and update the test-first lines"
5. "yes, update PROMPTS.md then commit"

### Summary
- **Outcome:** `plans/axcenity-hub.md` already existed (approved last
  session), so the skill checked it against the PRD instead of redrafting
  it. Stories 1–73 were all covered. The 19-phase breakdown is unchanged.
  The `tdd` skill's selection step then ran over every phase: Phases 1–6
  and 12A have no TDD behaviors, and the other 12 phases have 1–3 each (25
  in all). Each phase now has a "TDD behaviors" section. The blanket
  "Phase 7 onward is test-first" wording was replaced across the plan, the
  PRD and `HANDOFF.md`: TDD covers only the listed behaviors, and everything
  else gets tests alongside the code.
  Fixes applied: Phase 16's API covers projects only, and Phase 17 adds the
  asset endpoints (assets only exist after the Toolbox port). Phase 12B
  introduces the `Report` model that Phase 14 builds on. The Phase 8
  email-verification gate is now tested in Phases 10, 12B, 13 and 14, and
  Phase 15's restrictions cover every create action. Phase 3 requires
  `docs/frontend/reel.md`. Phase 5's per-width screenshots are recorded as
  visual checks, not pixel comparisons, and they don't count toward the ~5
  reel smoke tests. Bug reports are limited to 5 per user per day (plan
  Phase 14 and the PRD's limits line).
- **Deviations:** None; every recommendation was accepted. The user asked
  for TDD only where absolutely necessary, which reversed last session's
  plan to build everything from Phase 7 onward test-first.
- **Sideways:** Nothing went wrong. The request ran a planning skill on a
  plan that already existed, so the session became a gap review rather than
  a new plan. The first log entry was written mid-session and extended
  here at the user's request.

## 2026-11-23 — Research, Home prototype, engine showcase captures, PRD and plan

Continues the grill-me session logged below (same day, same session).

### Prompts
1. "A" (run order: `/research` → `/prototype` → `/to-prd` → `/prd-to-plan`)
2. "I really love the cinematic style and animations I feel that it captures
   the site and how I want it built. There are a few thinkgs I would like to
   note. The grid animation is really cool but a bit short and if feels like
   it is not looping as seemlessly as I would like it to. Next the images
   look grainy and distorted please capture or recreate some better looking
   images as it does not really do with the asthetic I am looking for in the
   page. The workspace layout does not really have any animations at this
   point and does not look to much like my engine also the placeholder test
   is pretty cool but it does not see to blend well when transitioning to
   single to multi line text. Other than that this website looks awesome and
   I understnd that this is a prototype so I cant expect anything polished
   quite yet, just note my reccomendations to be added."
3. "C and blue - Also go ahead and create a test scene that actually looks
   decent in the engine"
4. "What I would like fo you to do is to finish all basic features needed
   for now. use the handoff skill to denote any useful steps taken and allow
   a seemless pass along. The next agent will take care of the actual
   building"
5. "I would say for now lets leave out the terrain image as to me it does
   not capture the full scope of features that the terrain toolkit has to
   offer, like actually decent trees and textures"
6. "I think this looks good I would split phase 3 into two phases if it
   feels like the reel implementation proves to be difficult. I would also
   strengthen the phase 5 acceptance criteria. Make sure there is no
   placeholder medi, all media must have documented source dimensions and
   intended display dimensions, real and illustrative captures must be
   distinguishable but still look nice. Make sure that the media remains
   clear and nice looking accross all devices. I would also add some
   additional security to phae 8 include session and cookie configurations,
   CSRF protections, password reset token behavior, email verification
   policy, authentication throttling, account enumeration protection, secure
   production settings, tests for unauthenticated access to private pages.
   Turnstile should be used to supplement not replace server-side
   protection. Also add in 2FA sign in as well. For the GitHub integration in
   phase 10 include OAuth state validation, token encryption and secure
   storage, revocation and expired token handling, GitHub API rate-limit
   handling, webhook signature verification, duplicate repository linking
   prevention, permission revalidation before unprivileged operations. I
   would also split phase 12 if the forum page becomes a large part of the
   project. Consider: Phase 12A: Forum posts, editing, deletion and
   ownership. Phase 12B: Comments, ratings, posting limits and moderation
   integration. Phase 12C: Search, filtering, sorting and pagination. Expand
   phase 17 Keep existing toolbox functionality, use existing data and
   models and have them handled through an explicit migration strategy, hav
   hub authentication integrated without breaking existing accounts, keep
   provider integrations, keep pack export and import compatability,
   preserve tests and make sure there are not reressions in standalone
   toolbox functionality until the migration has completed"
7. "update PROMPTS.md with the rest of the session then commit also"

### Summary
- **Outcome:** Research note on the proposal's external services
  (`docs/research/external-services.md`). A throwaway three-variant Home
  prototype (`prototypes/home-direction.html`); the user chose **A ·
  Cinematic**, engine-blue accent `#19A0FF`, and mixed feature media (animated
  recreations for Editor and Blocks + Luau, real captures for Renderer). The
  outcome and four fixes are in `prototypes/home-direction.md`. An engine
  showcase built as two new engine projects in
  `~/Projects/Axcenity Projects/Showcase/` with 2560×1440 player captures:
  renderer with ray tracing on, a same-camera graybox, and an Ultra capture
  without ray tracing (kept), plus a terrain capture (rejected). The PRD is
  `prd/axcenity-hub.md` (73 stories). The plan is `plans/axcenity-hub.md`:
  19 phases, with the first slice in Phases 1–6.
- **Deviations:** The user added four prototype fixes (a seamless longer
  loop; no grainy images; an animated, engine-faithful workspace; a
  fixed-height rotating headline), asked for the engine test scene
  unprompted, rejected the terrain capture, and substantially strengthened
  the plan: a Phase 3 split point, strict Phase 5 media rules, Phase 8
  security hardening plus 2FA, GitHub security items across Phases 9–10,
  Phase 12 split into 12A–C, and a migration-led Phase 17. Agreed run order
  was followed; the PRD did not wait for the captures.
- **Sideways:** Research findings overturned two plans. SendGrid's free plan
  is retired, so it's dropped. GitHub `releases/latest` returns 404 because
  every engine release is a prerelease; the web link only redirects, so
  Download points at `/releases`. No Chromium was available for prototype
  screenshots, so headless Firefox was used. The first render hid the B and
  C hero reels behind a scroll-reveal (fixed). The engine's own renders are
  fixed at 480×270, the source of the grainy images. The showcase agent ran
  about 19 and about 10 iterations, more than the ~8 per shot suggested. Its
  first capture test reset the user's `Hello Graphics` save `graphics.json`
  to defaults, and it added save folders for the showcase projects. Glass
  was dropped from the renderer shot because RT reflections skip it. The
  `/handoff` skill can only be run by the user, so it was left for them to
  run.

## 2026-11-23 — Grill-me design interview for the Hub's first slice (showcase + reel)

### Prompts
1. `/grill-me` Task: Build a responsive, modern showcase website for Axcenity
   Engine based on the requirements in the attached PDF document. Reference
   files: requirements PDF (meet every rubric item); design baseline
   `project-two-building-with-apis` (match layout, typography, CSS
   architecture); engine repo (pull real icons, branding, shaders,
   screenshots/videos); Axcenity Toolbox as its own standalone sub-page in
   the nav, content kept separate, consistent styling. Visual direction:
   modern game-engine landing page (Godot, Unreal, s&box); real engine
   footage, interactive previews or loops (raytracing renderer,
   terrain/foliage, visual node scripting); scroll-triggered animation,
   rotating hero text, subtle transitions, responsive. Second task: a
   60fps animated showcase reel. Step 1: inspect the engine repo and the
   Toolbox styling (1px borders, low-clutter panels, dark/light variables,
   typography, real assets). Step 2: self-contained responsive component
   (Canvas/SVG/GSAP or Framer Motion), autoplay loop, play/pause and
   scene scrubbing, no heavy video, timeline portable to Remotion. Step 3:
   15–18 s storyboard in 4 scenes — (1) engine boot and multi-monitor
   workspace, panels snap in with spring physics, 0–4 s; (2) raytracing and
   PBR shader wipe from wireframe/graybox to lit with reflections and AO,
   4–8 s; (3) terrain displacement then staggered foliage scatter, 8–12 s;
   (4) node graph OnTriggerEnter → SpawnDecal with glowing Bezier wires,
   live syntax-highlighted Lua typing, then collapse to the logo lockup,
   12–18 s. Rules: cubic-bezier(0.16, 1, 0.3, 1) for every panel snap;
   devicePixelRatio scaling; responsive. Before code: propose the stack
   from existing dependencies and confirm the file path.
2. (Attached `Final Project Proposal.pdf`) "Here is the PDF"
3. "A also the other projects for reference are located here: Axcenity
   Engine: /home/pauljanota/Documents/VSCode Projects/Axcenity-Engine;
   Toolbox Website: /home/pauljanota/Documents/VSCode
   Projects/project-two-building-with-apis"
4. "A"
5. "B - I want the feel to be different this is the main marketing page
   for the website so it should feel different, when we get through
   questioning I would like to use the prototype skill to determine what
   the site will look like, also use the research skill to identify the
   APIs I plan to use within this project and determine their feasability
   and use as well as other alternatives if there are any."
6. "A"
7. "A"
8. "A"
9. "C - use screenshots and actual engine code for reference. the actual
   shorts should not look too far off from what the engine actually looks
   like."
10. "B"
11. "B"
12. "A - Use references of actual game engines, DO NOT copy their code use
    the design choices from my choices but, use their designs as
    inspiration for some of the videos effects css styling etc to make a
    unique experience. Unity: https://unity.com/ Unreal:
    https://www.unrealengine.com/ S&box: https://sbox.game/ Godot:
    https://godotengine.org/"
13. "A for now but plan for B later on"
14. "B - Also explain how to use these tests and what I should look for,
    TDD implementation will come later but should also be planned for."
15. "A"
16. "A - please setup a CLAUDE.md file for progressive disclosure only
    pointing to absolutely necessary information optimizing token usage
    while developing. Also please append this sessions conversations
    including this one to PROMPTS.md according to source formatting."

### Summary
- **Outcome:** No app code yet; 14 design decisions settled. (1) This
  session's scope is a showcase slice inside a Django Hub skeleton, the
  rest of the proposal in later phases. (2) `/toolbox/` is an overview page
  linking out; porting the Toolbox apps is a later phase. (3) Port only the
  Toolbox's theme foundation (tokens, fonts, 1px panels, motion
  primitives, theme tests). (4) Two shells: marketing (built now) and an
  editor-style app shell (later). (5) Reel stack: vanilla JS, Canvas 2D +
  DOM/SVG, custom pure-function timeline, no dependencies (Framer Motion
  ruled out: needs React/Node). (6) Paths: `marketing/` Django app,
  `static/reel/` ES modules, one file per scene exporting
  `{start, duration, render(ctx, t, size)}`. (7) Reel is drawn, faithful
  to the real editor (sourced from `editor-kit` theme and Lua syntax,
  `editor-node-graph`, `blocks-runtime`, terrain and scatter panes);
  feature sections get swappable media slots plus a capture shot list.
  (8) Compact mode under ~640 px. (9) Autoplay only on screen; reduced
  motion shows the lockup frame with Play; keyboard and screen-reader
  support. (10) Full 7-section landing page, copy in `marketing/content.py`.
  (11) Download links to GitHub `releases/latest`; an API-backed
  `/download/` page is planned for later. (12) pytest plus ~5 Playwright
  smoke tests behind a `browser` marker; TDD planned for later phases.
  (13) `/toolbox/` is a compact product page with real screenshots.
  (14) Layered docs like the Toolbox; `CLAUDE.md` written.
- **Deviations:** All recommendations accepted. Additions from the user:
  the marketing page must feel distinct from the Toolbox (Q3); the reel
  must match the real engine's look and code (Q7); use Unity, Unreal,
  s&box and Godot as design inspiration only, without copying code (Q10);
  plan the GitHub download page (Q11) and later TDD (Q12). Asked for a
  how-to on running and reading the tests. Queued after the interview:
  `/research` on the proposal's APIs and alternatives, then `/prototype`
  for the look.
- **Sideways:** The PDF wasn't attached at first; the agent found the
  proposal in `~/Downloads`, and while searching it also opened an
  unrelated PDF there (not used). The first scope question went
  unanswered when the PDF arrived and had to be asked again. Findings that
  corrected the brief: the engine scripts in Luau, not Lua; the README's
  Releases link names an old account, though both URLs redirect to
  `Axcenity-Studios/Axcenity-Engine`; the repo's docs images are
  diagrams, not captures, and its real renders are only 480×270.
