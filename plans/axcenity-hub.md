# Plan: Axcenity Hub

> Source PRD: [prd/axcenity-hub.md](../prd/axcenity-hub.md). Story numbers below refer to its User Stories.
> Supporting notes: [prototypes/home-direction.md](../prototypes/home-direction.md) (chosen Home direction and fixes),
> [docs/research/external-services.md](../docs/research/external-services.md) (external services).
> Ticked boxes are done. Phases 1–6 are the first slice (public marketing site). Phase 7 onward is test-first:
> write the failing tests for a phase's rules before its code.

## Architectural decisions

Durable decisions that apply across all phases:

- **Tooling:** uv only (no pip, Node or npm). Tailwind + DaisyUI via django-tailwind-cli. pytest + pytest-django;
  browser smoke tests use pytest-playwright behind a `browser` marker. Ruff for lint and format.
- **Apps:** `config` (settings, root URLs). `marketing`: public signed-out pages (Home, Toolbox overview, Download).
  `accounts`: Profile, auth glue, GitHub linking. `projects`: Project, ProjectMembership, repository link, webhooks.
  `forums`: ForumPost, Comment, Rating. `showcases`: Showcase, Tag. `reports`: BugReport, Report.
  `moderation`: ModerationAction, warnings and restrictions. `api`: the DRF surface. Ported Toolbox apps keep their
  own names (`catalog`, `packs`, `providers`) in Phase 17.
- **URLs** (all named and app-namespaced): `/` `marketing:home`, `/toolbox/` `marketing:toolbox`, `/download/`
  `marketing:download`, `/accounts/…` (allauth), `/projects/<slug>/…`, `/forums/…`, `/showcases/…`, `/reports/…`,
  `/moderation/…`, `/api/v1/…`. Projects and showcases use slugs; forum posts and reports use pks.
- **Models and relationships:** User (Django's) 1–1 Profile. User 1–N Project (owner). User N–N Project through
  ProjectMembership (role: Owner, Maintainer, Viewer). Showcase N–N Tag. ForumPost 1–N Comment; Rating per
  user per post (unique together). BugReport with a status field and an allowed-transition table. Report
  (feedback or abuse) generic over its target. ModerationAction records actor, target, action and reason, and is
  append-only.
- **Auth:** django-allauth (accounts, GitHub social login, MFA). Members-only views use `LoginRequiredMixin`;
  anything the caller can't see returns **404, never 403**. Every write is CSRF protected, HTMX included.
- **Limits:** creation and posting limits are enforced as database count checks in model and service logic.
  Cache-backed throttles (allauth's) need a shared cache in production.
- **Secrets:** read from environment variables only, never stored in the database or admin.
- **Database:** SQLite in development and tests; PostgreSQL for production (pending confirmation that MySQL isn't
  a course requirement). Case-insensitive uniqueness is enforced explicitly.
- **Theme:** the ported axcenity tokens (dark and light), monochrome chrome, a single accent `#19A0FF` (darker on
  light) used only for the primary button, the reel's progress and scan line, and the badge dot. Easing
  `cubic-bezier(0.16, 1, 0.3, 1)`.
- **Shells:** a marketing shell (Phase 1) and an editor-style app shell (Phase 8).
- **Reel contract:** native ES modules, one per scene, each a pure `render(ctx, t, size)` with its own start and
  duration; play, pause and scrub only set the clock (this is the Remotion porting seam).
- **Media manifest:** every image or video on the site is declared in the marketing content module with its kind
  (`capture` or `illustrative`), provenance, source pixel dimensions and intended display dimensions.

---

## Phase 1: Skeleton, theme and marketing shell

**User stories**: 16, 17, 69

### What to build

A runnable Django project in the Toolbox's layout, with the axcenity theme foundation ported (tokens, fonts,
1px panels, buttons, focus, hover gate, motion primitives, reduced motion), the marketing shell (a sticky nav that's
transparent over the hero and solid on scroll; a theme switch for System, Light or Dark that's applied before first
paint; a four-column footer), and a bare Home page at `/`. Set up the test layout: the `tests/` folder, the autouse
network guard, the `browser` marker, and the ported theme tests. Start the layered docs that CLAUDE.md points to
(FRONTEND, ARCHITECTURE and TESTING indexes, plus a theme topic file). Sign in is hidden or marked coming soon, never
a dead link.

### Acceptance criteria

- [ ] `uv sync` then `manage.py tailwind runserver` serves `/` with the marketing shell in dark and light
- [ ] Theme choice persists and applies before first paint (no flash); System follows the OS
- [ ] Only axcenity tokens exist (Tailwind and DaisyUI palettes off); the ported theme tests pass
- [ ] The nav is transparent at the top and solid after scrolling; on phones it collapses with no horizontal scroll
- [ ] `uv run pytest -m "not browser"` is green; any attempt to reach the network fails the test; Ruff is clean
- [ ] Docs indexes and the theme topic file exist and match the code

---

## Phase 2: Home content

**User stories**: 2–8, 10–15, 29, 71

### What to build

All Home sections from the Cinematic direction, driven by a content module (copy, links, media manifest): the hero
copy with the version badge and CTAs; the rotating headline in a box sized to its longest phrase at each breakpoint;
sticky-scroll feature pillars (the media stage swaps per pillar on desktop; inline media on phones); the workflow strip
with outlined numerals; the stat band; the Toolbox banner; the coming-soon community row; the final CTA. Expo-out scroll
reveals. Under reduced motion, everything appears in its final state. Download links to the engine's GitHub Releases
list; Docs links to the engine's documentation. Media slots may hold Phase 5's final assets or provisional assets
already shaped like them; Phase 5 makes them final.

### Acceptance criteria

- [ ] Every section renders from the content module; no copy is hard-coded in the template
- [ ] The rotating headline never moves content below it at any breakpoint (switching between one-line and two-line phrases)
- [ ] Sticky media swaps per pillar on desktop; inline media on phones; no horizontal scroll at 360 px
- [ ] Reduced motion (OS setting) shows the final states with no reveal or rotation animation
- [ ] Tests: `/` returns 200; every link in the content module resolves (internal URLs reverse; external URLs are well-formed); every referenced media file exists
- [ ] Copy says alpha, Luau, free and open source, and Windows, macOS and Linux; nothing claims a feature the engine lacks

---

## Phase 3: Reel engine and Scene 1

**User stories**: 1, 19, 24–28, 30–32, 70, 72

### What to build

The reel's timeline and player around its first scene: the master clock with a ~18 s scene table and seek; expo-out
and spring helpers; HiDPI canvas setup (devicePixelRatio capped at 2) with resize handling; controls (play/pause,
scrubber with four scene ticks, Space and ←/→, fade on hover or focus, always visible on touch); autoplay only while
≥30% visible, pausing off screen and when the tab is hidden; reduced motion shows the lockup frame and a Play button;
a visually hidden text description and an aria-hidden canvas; compact mode below ~640 px. Scene 1 (0–4 s): kinetic
type, then Viewport, Explorer and Properties panels snapping into an undocked multi-monitor layout with springs,
styled from the editor's real theme and panel names. Scenes 2–4 are inert slots in the table. Add the Playwright
smoke tests.

**Split point (if this phase proves difficult):** 3A covers the timeline, controls, accessibility, reduced motion,
visibility pausing and smoke tests, with a trivial test scene. 3B covers Scene 1 and compact mode.

### Acceptance criteria

- [ ] Scrubbing to any time renders that exact frame (pure function of time); play/pause/scrub never desync
- [ ] Space toggles, ←/→ jump scene boundaries; controls are labelled buttons and a range input
- [ ] Reduced motion: no autoplay, the lockup frame is shown, and Play starts it
- [ ] Pauses off screen and in hidden tabs (no requestAnimationFrame work while paused)
- [ ] Crisp on DPR 2; holds ~60 fps on a mid-range laptop at 1440p; compact mode is readable at 360 px
- [ ] Scene 1 palette, panel names and layout match the engine editor (checked against the editor theme source)
- [ ] Browser tests (about 5): mounts with no console errors; play/pause toggles; arrow keys jump; reduced motion shows the lockup without autoplay; no horizontal scroll at phone width

---

## Phase 4: Reel Scenes 2–4 and logo lockup

**User stories**: 18, 20–23

### What to build

Scene 2 (4–8 s): a shader wipe inside the viewport from wireframe/graybox to lit PBR, using the real renderer capture
and its same-camera graybox capture as the end frames, with a scan line in the accent colour. Scene 3 (8–12 s): a
terrain grid displacing into hills, then staggered expo-out foliage scale-in. Scene 4 (12–16 s): OnTriggerEnter →
SpawnDecal nodes linked by glowing Bezier wires, with Luau typing out beside them in the editor's real syntax
colours. 16–18 s: panels collapse into the Axcenity logo lockup. The loop's final frame flows into its first with no
visible reset. Each scene has a compact layout.

### Acceptance criteria

- [ ] The full loop plays 15–18 s with no visible jump at the wrap point
- [ ] Scene 2 uses the real captures and never upscales them past their source resolution
- [ ] Node styling, block names and Luau highlighting match the engine sources; the reel's text and description say Luau
- [ ] Every scene is a pure function of time and passes the existing smoke tests; compact layouts are readable at 360 px
- [ ] Scene modules follow the documented contract (start, duration, render) so a Remotion port is mechanical

---

## Phase 5: Feature media

**User stories**: 9, 10, 73

### What to build

Final media for every Home slot (and the shared media pipeline Phase 6 reuses). Renderer: the 2560×1440 ray-traced
capture from the engine showcase project. Editor: an animated recreation of the docking workspace built from the
editor's UI code. Blocks + Luau: an animated node-and-code recreation. Terrain: a finished, animated illustrative
recreation of sculpting and scattering. The existing terrain capture is excluded, by user decision, until one with
decent trees and textures exists. Each asset gets responsive derivatives (WebP or AVIF with a fallback, sized
for 1× and 2× of its display size) and an entry in the media manifest.

### Acceptance criteria

- [ ] **No placeholder media anywhere:** no "capture pending" boxes, grey blocks, lorem, or test-reference images (the 480×270 engine references are never used)
- [ ] Every media item's manifest entry records kind (`capture` or `illustrative`), provenance (scene or project, command and settings, or source code it recreates), source pixel dimensions and intended display dimensions per breakpoint
- [ ] A test checks every manifest entry: the file exists, its real pixel size matches the recorded source size, and display size × 2 never exceeds the source size (no upscaling on 2× screens)
- [ ] Real captures and illustrative recreations are distinguishable (a consistent caption or badge: "Engine capture" vs "Illustrative") and both look finished and on-brand
- [ ] Media stays sharp and correctly framed at 360, 768, 1280, 1440 and 2560 px wide, in dark and light, on 1× and 2× screens (checked by screenshots in the browser tests at those widths)
- [ ] Images use `srcset`/`sizes` with intrinsic width and height (no layout shift); below-the-fold media lazy-loads; animated recreations pause off screen and respect reduced motion
- [ ] Captions and alt text are accurate; nothing illustrative is labelled as an engine capture

---

## Phase 6: Toolbox page

**User stories**: 33–36

### What to build

`/toolbox/` in the marketing shell: a hero line, the three core features (Discover across ambientCG, Poly Haven and
Openverse; private library; engine-ready packs), two or three real screenshots captured by running the Toolbox
locally, a "run it locally" block with its uv commands, and a GitHub link. It uses the Toolbox's panel styling
inside for continuity. The screenshots go through Phase 5's media pipeline and rules.

### Acceptance criteria

- [ ] Toolbox appears in the main nav and the Home banner links to it
- [ ] The screenshots are real captures of the running Toolbox with manifest entries; they meet every Phase 5 media criterion
- [ ] The run-locally commands match the Toolbox README; the GitHub link resolves
- [ ] Tests: 200, links resolve, media manifest checks pass

---

## Phase 7: Download page

**User stories**: 37–40

### What to build

`/download/` backed by the GitHub REST releases-list endpoint for the engine repository. It picks the newest
non-draft release (prereleases included, marked alpha), groups assets by OS, highlights the visitor's platform, and
shows version, date, sizes and GitHub's per-asset SHA-256 digests. Uses ETag conditional requests and about an hour
of caching. When GitHub fails it falls back to cached data, then to a plain link to GitHub Releases. Home's
Download CTA switches to this page.

### Acceptance criteria

- [ ] Tests first, with `responses` fixtures trimmed from a real release payload: OS grouping, newest non-draft selection, alpha marking, digest display
- [ ] A 304 response reuses the cache; a 5xx, timeout, or 403/429 rate limit serves cached data or the GitHub link, never an error page
- [ ] OS detection highlights the right build and every build stays reachable
- [ ] No test reaches the network

---

## Phase 8: Accounts, security and two-factor sign-in

**User stories**: 41–43, 45

### What to build

django-allauth registration, login, logout and password reset, plus a Profile, introducing the editor-style app
shell for signed-in pages. Harden it from the start: session and cookie settings; CSRF everywhere; password-reset
token behaviour; an email verification policy; authentication throttling; account-enumeration protection; secure
production settings; and two-factor sign-in (allauth MFA: authenticator-app TOTP with recovery codes). A honeypot
and server-side limits protect signup and reset. Cloudflare Turnstile is added on signup, password reset and any
anonymous form, to supplement the server-side protections, never replace them. Email uses the console backend in
development and locmem in tests.

### Acceptance criteria

- [ ] Tests first for every item below
- [ ] **Sessions and cookies:** HttpOnly session cookie; Secure session and CSRF cookies in production; SameSite=Lax; the session rotates on login and privilege change; sessions expire after a documented idle and absolute age; logout invalidates the session server-side
- [ ] **CSRF:** every state-changing view rejects requests without a valid token, HTMX included; no `csrf_exempt` outside the webhook endpoint (Phase 10)
- [ ] **Password reset:** tokens are single-use, expire after a documented window (≤ 1 hour), and are invalidated by any password change; the reset page doesn't leak the token through referrers
- [ ] **Email verification:** a documented policy. Default: unverified accounts can sign in but can't post, create projects or submit reports until verified; tests enforce it
- [ ] **Throttling:** failed logins, signups, reset requests and MFA attempts are rate-limited per IP and per account; the limit holds under the production cache (shared cache documented), and the database-count limits still apply if the cache is cleared
- [ ] **Enumeration protection:** login, signup and reset give identical responses and timing-safe behaviour whether or not the account or email exists
- [ ] **Two-factor:** users can enrol TOTP, get one-time recovery codes, sign in with either, and disable 2FA only after re-authentication; an MFA step can't be skipped by navigating directly
- [ ] **Production settings:** `manage.py check --deploy` passes under production settings (HSTS, SSL redirect, secure cookies, `X-Frame-Options`, content-type nosniff, referrer policy, `DEBUG` off, `ALLOWED_HOSTS` set, secret key from the environment)
- [ ] **Unauthenticated access:** a test walks every members-only URL and asserts an anonymous request is redirected to login (or gets a 404 for object URLs), never served content
- [ ] **Turnstile:** verified server-side with the official test keys; when Turnstile fails or is unreachable, the server-side protections still block abuse; it's never the only check
- [ ] Unique, validated registration (case-insensitive username and email uniqueness)

---

## Phase 9: GitHub account linking

**User stories**: 44

### What to build

Connect a GitHub account to an existing Hub account through allauth's GitHub provider (OAuth App with no scopes
by default; a GitHub App if private repos are confirmed). Covers OAuth state validation, encrypted token storage,
and handling of revoked and expired tokens.

### Acceptance criteria

- [ ] Tests first; no test drives real OAuth (SocialAccount rows are created directly; token endpoints are mocked)
- [ ] **OAuth state:** a callback with a missing, mismatched or reused `state` is rejected and links nothing
- [ ] **Token storage:** GitHub tokens are encrypted at rest with a key from the environment, never logged, never shown in the admin or API, and deleted on unlink
- [ ] **Revoked or expired tokens:** a 401 from GitHub marks the link as needing reconnection, prompts the user, and never crashes a page; refresh tokens (GitHub App) are rotated and stored encrypted
- [ ] One GitHub account can link to only one Hub account; unlinking requires re-authentication

---

## Phase 10: Projects and repository integration

**User stories**: 46–48, 52–53

### What to build

Create projects (slug URLs) and link a GitHub repository. Includes the 5-projects-per-user limit, case-insensitive
unique names, rate-limit-aware GitHub API calls, signed webhooks keeping repository info current, duplicate-link
prevention, and a check that GitHub permission is still valid before every repo-dependent operation.

### Acceptance criteria

- [ ] Tests first for each rule below
- [ ] The 6th project is rejected; names are unique case-insensitively; owners can edit and delete, others get 404
- [ ] **Rate limits:** GitHub calls read `X-RateLimit-*` and `Retry-After`, back off, use ETags, and are budgeted per user; exhaustion shows cached data with a clear notice, never an error page
- [ ] **Webhooks:** payloads are verified with `X-Hub-Signature-256` (HMAC-SHA256, constant-time compare) using a secret from the environment; unsigned, mis-signed or replayed deliveries (duplicate `X-GitHub-Delivery`) are rejected; the endpoint is the only CSRF-exempt view
- [ ] **Duplicate linking:** a repository can be linked to only one Hub project; a second attempt is refused with a clear message
- [ ] **Permission revalidation:** before every repo-dependent operation, the user's current repository permission is checked against GitHub (with a short cache); downgraded or removed access blocks the operation, and the Hub never grants more than GitHub does
- [ ] GitHub outages degrade gracefully (cached data, retry later); mocked failure tests cover 401, 403, 404, 5xx and timeouts

---

## Phase 11: Project teams

**User stories**: 49–51

### What to build

ProjectMembership with Owner, Maintainer and Viewer roles. Owners invite members and assign roles; only owners
manage memberships and permissions; Viewers get read-only access to what they're granted.

### Acceptance criteria

- [ ] Tests first: role matrix per action (view, edit, manage members, delete, rename)
- [ ] Non-members and insufficient roles get 404 for private resources
- [ ] A project always keeps at least one Owner; ownership transfer is explicit
- [ ] Invites are accepted or declined by the invitee only

---

## Phase 12A: Forum posts and ownership

**User stories**: 54 (posts), 59

### What to build

Create, view, edit and delete forum posts. Only the author can edit or delete (admins later through moderation).
The email-verification gate from Phase 8 applies.

### Acceptance criteria

- [ ] Tests first: CRUD, ownership (others get 404 on edit and delete), validation, unverified users blocked
- [ ] HTMX partial updates for edit and delete with CSRF

---

## Phase 12B: Comments, ratings, limits and moderation hooks

**User stories**: 54 (comments, ratings), 55

### What to build

Comments and ratings on posts, the posting limits (5 new posts per day, 5 comments per minute) as database count
checks, and hooks moderation will use (reporting a post or comment, hidden or removed states that Phase 15's
actions set).

### Acceptance criteria

- [ ] Tests first: the 6th post in a day and the 6th comment in a minute are rejected with a clear message
- [ ] One rating per user per post (changeable, not stackable); authors can't rate their own posts
- [ ] Users can report a post or comment; hidden or removed content is invisible to non-admins

---

## Phase 12C: Search, filtering, sorting and pagination

**User stories**: 58

### What to build

Server-side search, filters, sorting and pagination for forum lists, using a shared pattern that later lists
(projects, showcases, reports) reuse.

### Acceptance criteria

- [ ] Tests first: search terms, each filter, each sort order, page boundaries, invalid parameters handled safely
- [ ] HTMX updates the list without a full reload; URLs are shareable (state in the query string)

*(12A–12C may be merged back into one phase if the forum turns out small.)*

---

## Phase 13: Showcases and tags

**User stories**: 56–57

### What to build

Publish, edit, delete and interact with showcases, limited to 1 new showcase per day, with many-to-many tags,
browsing by tag, and the shared list pattern from 12C. Showcase media goes through Django's storage setting.

### Acceptance criteria

- [ ] Tests first: the daily limit, ownership, tag filtering, pagination
- [ ] Uploaded images are validated (type, size, dimensions) and processed with Pillow

---

## Phase 14: Bug reports and report management

**User stories**: 60–63

### What to build

Validated, rate-limited bug reports and feedback with supporting information. Project owners and admins review,
assign, comment on and update them. Status changes follow a permitted-transition table. Access is restricted to
the relevant project's authorities and admins.

### Acceptance criteria

- [ ] Tests first: every allowed and forbidden status transition; the access matrix (outsiders get 404); submission limits; required-field validation

---

## Phase 15: Moderation

**User stories**: 64–66

### What to build

Admin tools to review reported content, issue warnings, hide or remove content (through 12B's hooks) and restrict
accounts. Every action writes an append-only ModerationAction.

### Acceptance criteria

- [ ] Tests first: only authorised admins can act; every action is recorded with actor, target, reason and time; records can't be edited or deleted through the app
- [ ] Restricted accounts can't post, comment or submit while restricted

---

## Phase 16: REST API

**User stories**: 67

### What to build

A versioned DRF API (`/api/v1/`) exposing project and asset information for the engine, with token
authentication and the same permission rules as the web views.

### Acceptance criteria

- [ ] Tests first: unauthenticated requests are refused; users see only what they could see in the web app (404 otherwise); throttling on
- [ ] Tokens are never returned after creation; tokens can be revoked

---

## Phase 17: Toolbox port

**User stories**: 68

### What to build

Bring the Toolbox's `catalog`, `packs` and `providers` apps into the Hub under `/toolbox/…`, keeping every existing
feature and its data. Follow an explicit migration strategy that preserves the existing models and records, and
integrate Hub authentication without breaking existing Toolbox accounts. The standalone Toolbox stays fully working
until the migration is complete and signed off.

### Acceptance criteria

- [ ] **Feature parity:** Discover, library, packs, gallery, attribution and exports behave as in the standalone Toolbox
- [ ] **Data and models:** existing Toolbox models are kept (same fields and relationships). A documented, rehearsed migration moves existing data (users, library entries, packs, preferences, API tokens) into the Hub's database, with a dry run, row-count and integrity checks, and a rollback path
- [ ] **Accounts:** existing Toolbox users can sign in to the Hub with their existing credentials (password hashes carried over); accounts are matched or merged by verified email without duplicates or lost data; collisions are reported, not silently merged
- [ ] **Providers:** the ambientCG, Poly Haven and Openverse integrations keep their existing `search()` and `get_details()` behaviour and error handling
- [ ] **Packs:** pack export and import formats stay byte-for-byte compatible with what the engine imports; packs made before the port still import
- [ ] **Tests:** the Toolbox's test suite is ported and passes in the Hub unchanged in intent; the network guard stays on
- [ ] **No regressions in the standalone Toolbox** while the migration runs: its repository and test suite stay green, and both run side by side until cut-over is signed off
- [ ] The marketing `/toolbox/` overview page becomes the entry point to the live tool
