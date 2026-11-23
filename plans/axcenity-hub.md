# Plan: Axcenity Hub

> Source PRD: [prd/axcenity-hub.md](../prd/axcenity-hub.md). Story numbers below refer to its User Stories.
> Supporting notes: [prototypes/home-direction.md](../prototypes/home-direction.md) (chosen Home direction and fixes),
> [docs/research/external-services.md](../docs/research/external-services.md) (external services).
> Ticked boxes are done. Phases 1–6C are the first slice (public marketing site and documentation). Each phase lists its
> TDD behaviors (at most three, built test-first with the `tdd` skill); everything else in a phase is built and
> tested normally, with tests written alongside the code.

## Architectural decisions

Durable decisions that apply across all phases:

- **Tooling:** uv only (no pip, Node or npm). Tailwind + DaisyUI via django-tailwind-cli. pytest + pytest-django;
  browser smoke tests use pytest-playwright behind a `browser` marker. Ruff for lint and format.
- **Apps:** `config` (settings, root URLs). `marketing`: public signed-out pages (Home, Toolbox overview, Download).
  `documentation`: the engine docs and API reference (Phases 6B–6C). `accounts`: Profile, auth glue, GitHub linking. `projects`: Project, ProjectMembership, repository link, webhooks.
  `forums`: ForumPost, Comment, Rating. `showcases`: Showcase, Tag. `reports`: BugReport, Report.
  `moderation`: ModerationAction, warnings and restrictions. `api`: the DRF surface. Ported Toolbox apps keep their
  own names (`catalog`, `packs`, `providers`) in Phase 17.
- **URLs** (all named and app-namespaced): `/` `marketing:home`, `/toolbox/` `marketing:toolbox`, `/download/`
  `marketing:download`, `/docs/` `documentation:index`, `/docs/<path>/` `documentation:page` (the snapshot's file
  path, lower-cased, without `.md`: `/docs/learn/scripting/`, `/docs/api/classes/part/`), `/docs/search/`
  `documentation:search`, `/accounts/…` (allauth), `/projects/<slug>/…`, `/forums/…`, `/showcases/…`, `/reports/…`,
  `/moderation/…`, `/api/v1/…`. Projects and showcases use slugs; forum posts and reports use pks.
- **Models and relationships:** User (Django's) 1–1 Profile. User 1–N Project (owner). User N–N Project through
  ProjectMembership (role: Owner, Maintainer, Viewer). Showcase N–N Tag. ForumPost 1–N Comment; Rating per
  user per post (unique together). BugReport with a status field and an allowed-transition table. Report
  (feedback or abuse) generic over its target. ModerationAction records actor, target, action and reason, and is
  append-only.
- **Documentation source:** the engine repository's `documentation/` folder is the single source of truth. The Hub
  serves a committed snapshot of it (copied by `sync_engine_docs`, provenance in `SOURCE.json`), never edits the
  pages, and never fetches them at request time. Fixes to the docs' text are made in the engine and re-synced.
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

### TDD behaviors

None: setup and a port of the Toolbox's theme, whose tests already exist.

### Acceptance criteria

- [x] `uv sync` then `manage.py tailwind runserver` serves `/` with the marketing shell in dark and light
- [x] Theme choice persists and applies before first paint (no flash); System follows the OS
- [x] Only axcenity tokens exist (Tailwind and DaisyUI palettes off); the ported theme tests pass
- [x] The nav is transparent at the top and solid after scrolling; on phones it collapses with no horizontal scroll
- [x] `uv run pytest -m "not browser"` is green; any attempt to reach the network fails the test; Ruff is clean
- [x] Docs indexes and the theme topic file exist and match the code

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

### TDD behaviors

None: copy and data; the link and media checks are tests in their own right, with no code to drive.

### Acceptance criteria

- [x] Every section renders from the content module; no copy is hard-coded in the template
- [x] The rotating headline never moves content below it at any breakpoint (switching between one-line and two-line phrases)
- [x] Sticky media swaps per pillar on desktop; inline media on phones; no horizontal scroll at 360 px
- [x] Reduced motion (OS setting) shows the final states with no reveal or rotation animation
- [x] Tests: `/` returns 200; every link in the content module resolves (internal URLs reverse; external URLs are well-formed); every referenced media file exists
- [x] Copy says alpha, Luau, free and open source, and Windows, macOS and Linux; nothing claims a feature the engine lacks

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

### TDD behaviors

None: the behaviors are visible only through the planned Playwright smoke tests, so writing them first gains little, and the PRD rules out JavaScript unit tests.

### Acceptance criteria

- [x] Scrubbing to any time renders that exact frame (pure function of time); play/pause/scrub never desync
- [x] Space toggles, ←/→ jump scene boundaries; controls are labelled buttons and a range input
- [x] Reduced motion: no autoplay, the lockup frame is shown, and Play starts it
- [x] Pauses off screen and in hidden tabs (no requestAnimationFrame work while paused)
- [ ] Crisp on DPR 2; holds ~60 fps on a mid-range laptop at 1440p; compact mode is readable at 360 px
- [x] Scene 1 palette, panel names and layout match the engine editor (checked against the editor theme source)
- [x] Browser tests (about 5): mounts with no console errors; play/pause toggles; arrow keys jump; reduced motion shows the lockup without autoplay; no horizontal scroll at phone width
- [x] `docs/frontend/reel.md` documents the scene contract, the timeline, compact mode and playback rules, and the FRONTEND index points to it

---

## Phase 4: Reel Scenes 2–4 and logo lockup

**User stories**: 18, 20–23

### What to build

Scene 2 (4–8 s): a shader wipe inside the viewport from wireframe/graybox to lit PBR, using the real renderer capture
and its same-camera graybox capture as the end frames, with a scan line in the accent colour. Scene 3 (8–12 s): a
terrain grid displacing into hills, then staggered expo-out foliage scale-in. Scene 4 (12–16 s): When touched →
Spawn decal blocks (the engine's real block names) linked by glowing Bezier wires, with their real Luau translation
(`part.Touched:Connect(function(otherPart) … workspace:SpawnDecal(…))`) typing out beside them in the editor's real
syntax colours. 16–18 s: panels collapse into the Axcenity logo lockup. The loop's final frame flows into its first with no
visible reset. Each scene has a compact layout.

### TDD behaviors

None: the scenes are visual; Phase 3's smoke tests cover them.

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

### TDD behaviors

None: the media is visual, and the manifest check is a check on data, not code to drive.

### Acceptance criteria

- [x] **No placeholder media anywhere:** no "capture pending" boxes, grey blocks, lorem, or test-reference images (the 480×270 engine references are never used)
- [x] Every media item's manifest entry records kind (`capture` or `illustrative`), provenance (scene or project, command and settings, or source code it recreates), source pixel dimensions and intended display dimensions per breakpoint
- [x] A test checks every manifest entry: the file exists, its real pixel size matches the recorded source size, and display size × 2 never exceeds the source size (no upscaling on 2× screens)
- [x] Real captures and illustrative recreations are distinguishable (a consistent caption or badge: "Engine capture" vs "Illustrative") and both look finished and on-brand
- [x] Media stays sharp and correctly framed at 360, 768, 1280, 1440 and 2560 px wide, in dark and light, on 1× and 2× screens (checked by screenshots taken in one parametrised browser test at those widths and reviewed by eye; these aren't pixel comparisons, and they don't count toward the ~5 reel smoke tests)
- [x] Images use `srcset`/`sizes` with intrinsic width and height (no layout shift); below-the-fold media lazy-loads; animated recreations pause off screen and respect reduced motion
- [x] Captions and alt text are accurate; nothing illustrative is labelled as an engine capture

---

## Phase 6: Toolbox page

**User stories**: 33–36

### What to build

`/toolbox/` in the marketing shell: a hero line, the three core features (Discover across ambientCG, Poly Haven and
Openverse; private library; engine-ready packs), two or three real screenshots captured by running the Toolbox
locally, a "run it locally" block with its uv commands, and a GitHub link. It uses the Toolbox's panel styling
inside for continuity. The screenshots go through Phase 5's media pipeline and rules.

### TDD behaviors

None: a content page that reuses Phase 5's media checks.

### Acceptance criteria

- [ ] Toolbox appears in the main nav and the Home banner links to it
- [ ] The screenshots are real captures of the running Toolbox with manifest entries; they meet every Phase 5 media criterion
- [ ] The run-locally commands match the Toolbox README; the GitHub link resolves
- [ ] Tests: 200, links resolve, media manifest checks pass

---

## Phase 6B: Documentation site

**User stories**: 6, 74–77, 79

### What to build

A `documentation` app serving the engine's guide at `/docs/` in the marketing shell, so the Hub no longer sends
readers to GitHub to learn the engine. Content comes from the engine repository's `documentation/` folder (its
GitBook source: `SUMMARY.md`, the Learn chapters, the reference pages, and seven diagrams). The engine repo is
read-only, so a `sync_engine_docs` management command copies that folder into a committed snapshot under
`documentation/content/` and records the engine commit and date in `documentation/content/SOURCE.json`. Pages are
rendered from the snapshot only: no request reads the engine repo or GitHub.

- **Rendering:** markdown-it-py (CommonMark plus tables, raw HTML off) with front-matter parsing for
  `description`, `icon`, `status` and `samples`. Fenced `luau` and `lua` blocks are highlighted server-side with
  Pygments in the editor's Luau syntax colours (the tokens Phase 4 adds for the reel, scoped to code blocks and
  covered by the theme tests). Every code block gets a copy button (small vanilla JS; the code reads fine without it).
- **Links:** relative `.md` links (with `../` and `#anchor`) are rewritten to Hub URLs, images to static paths,
  and external links are left as they are. A link to a page that isn't in the snapshot fails the build check.
- **Layout:** three columns on wide screens: a left sidebar built from `SUMMARY.md` (its sections as collapsible
  groups, the current page marked), the article at a readable measure (about 70ch), and an "On this page" rail
  from the h2 and h3 headings, each with a permalink anchor. Breadcrumbs above the title; previous and next links
  in `SUMMARY.md` order below it. Below 1024 px the sidebar becomes a disclosure at the top and the rail is
  hidden. Tables and code scroll inside their own box, never the page.
- **Page header:** the title, the front-matter description as the lede, a "Partly built" or "Experimental" badge
  from `status`, an "Alpha" notice consistent with the rest of the site, and a "View source on GitHub" link to the
  file at the snapshot's commit. `samples` show as "Try it in the editor" with each sample's name.
- **Landing (`/docs/`):** the engine docs' README as an intro, then one panel per `SUMMARY.md` section (Before
  you start, the four Learn groups, Architecture, Scripting, Systems, Assets and projects, Tools, API reference)
  listing its pages with their descriptions, styled like Home's panels.
- **Diagrams:** the seven engine diagrams (1200 px wide) are copied to static, entered in the media manifest as
  `illustrative` with the engine file as provenance, captioned from their alt text with a "Diagram" label, and
  shown no wider than their source size.
- **Site links:** the nav's Docs link, Home's "Read the docs" CTA, the footer's Docs and Getting started links
  point at `/docs/` pages. GitHub stays reachable from each page's "View source" link and the footer.

The API reference pages render through the same pipeline in this phase as plain pages; Phase 6C gives them
their dedicated layout and search.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Link rewriting: a relative `.md` link (sibling, `../` parent, with or without `#anchor`) becomes the right Hub
   URL; an image link becomes its static path; a link to a missing page is reported, not silently kept.
2. The navigation tree from `SUMMARY.md`: sections, nesting and order, with previous and next following that
   order; a page that `SUMMARY.md` doesn't list is reported as an orphan.
3. `sync_engine_docs` against a fake engine tree in `tmp_path`: it copies Markdown and images, writes
   `SOURCE.json` with the commit, never writes to the source tree, and a second run with no engine changes
   changes nothing.

### Acceptance criteria

- [ ] Every page `SUMMARY.md` lists returns 200 at its `/docs/…` URL, with `<title>` "Page · Axcenity Docs" and the front-matter description as its meta description
- [ ] Every internal link and image in the snapshot resolves (a test walks them all); no request reads the engine repo or the network
- [ ] Sidebar, breadcrumbs, "On this page", heading anchors and previous/next work, and the docs layout needs no JavaScript (the copy button and the mobile disclosure are progressive)
- [ ] Luau code is highlighted in the editor's syntax colours; the new colours pass the theme tests' contrast checks in dark and light
- [ ] Status badges, the Alpha notice and the "View source on GitHub" link (at the snapshot commit) appear on every page; provenance (engine commit and date) is shown in the docs footer
- [ ] The seven diagrams are in the media manifest as `illustrative`, captioned "Diagram", never upscaled
- [ ] The nav, Home CTA and footer docs links point at `/docs/`; the shell's link tests still pass
- [ ] One browser smoke test: a long API page at 375 px has no horizontal page scroll, and the copy button copies
- [ ] `docs/frontend/documentation.md` explains the layout and how to re-sync; ARCHITECTURE lists the app, its URLs and the snapshot rule

---

## Phase 6C: API reference

**User stories**: 58 (documentation), 75, 78

### What to build

The generated API reference (`documentation/api/`: about 140 classes, 45 data types and services, the enums,
libraries and globals) as a browsable reference rather than long plain pages.

- **API home (`/docs/api/`):** Classes, Data types, Enums, Libraries and Globals as tabs or panels, each a
  server-rendered list of names with their one-line descriptions, plus a filter box that narrows the list as you
  type (vanilla JS; without JavaScript the full list shows).
- **Class and type pages:** the page parsed into its members: the constructor signature, then a summary table of
  Properties, Events and Methods (name, type or signature, first sentence) linking to each member's anchor.
  "Inherits from Instance" links to Instance, with the inherited members in a collapsed group. Signatures render
  as code with type names linked to their own pages. The right rail lists members by kind.
- **Enums:** one anchor per enum, its items as a compact chip list; `Enum.Material` links straight to its anchor.
- **Search (`/docs/search/?q=`):** a GET form in the docs header searching page titles, descriptions, headings
  and API member names over an in-memory index built from the snapshot. Exact name matches rank first ("Part"
  finds Part before MeshPart), then titles, headings, members and descriptions. Results show the page, the
  matched member or heading and a snippet, 20 per page with Django's paginator. Empty, too-long or
  whitespace-only queries show the search page with a message, never an error.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Parsing an API page into a class with its signature and its members grouped by kind (property, event, method),
   each with its anchor, and the inheritance link.
2. Search ranking and query handling: exact name, then title, heading, member, description; the query is trimmed and
   length-limited, and an empty query returns no results without error.

### Acceptance criteria

- [ ] Every class, type, enum, library and global listed in `SUMMARY.md` has a page with its member table, and every member anchor resolves
- [ ] Type names in signatures link to their pages wherever such a page exists
- [ ] The API home lists every entry with JavaScript off; the filter narrows it with JavaScript on
- [ ] Search returns the expected first result for a fixed set of queries (`Part`, `Touched`, `TweenService`, `Enum.Material`, `task.wait`), paginates, and handles empty and over-long queries
- [ ] No horizontal page scroll at 375 px on the longest class page (covered by Phase 6B's smoke test pointed at it)
- [ ] `docs/frontend/documentation.md` covers the API layout and search

---

## Phase 7: Download page

**User stories**: 37–40

### What to build

`/download/` backed by the GitHub REST releases-list endpoint for the engine repository. It picks the newest
non-draft release (prereleases included, marked alpha), groups assets by OS, highlights the visitor's platform, and
shows version, date, sizes and GitHub's per-asset SHA-256 digests. Uses ETag conditional requests and about an hour
of caching. When GitHub fails it falls back to cached data, then to a plain link to GitHub Releases. Home's
Download CTA switches to this page.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Release selection picks the newest non-draft release, includes prereleases and marks them alpha.
2. Failures fall back in order: a 5xx, timeout, 403 or 429 serves cached data, then the plain GitHub link, and never an error page.
3. A 304 reply to a request that sent the stored ETag reuses the cached data.

### Acceptance criteria

- [ ] Tests use `responses` fixtures trimmed from a real release payload: OS grouping, newest non-draft selection, alpha marking, digest display
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

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. The email-verification gate: unverified users can sign in but can't post, create or report.
2. Usernames and emails are unique regardless of case.

### Acceptance criteria

- [ ] Every item below has tests
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

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Tokens are encrypted at rest: the stored value is never the plain token, it decrypts with the environment key, and unlinking deletes it.
2. A 401 from GitHub marks the link as needing reconnection instead of crashing the page.

### Acceptance criteria

- [ ] No test drives real OAuth (SocialAccount rows are created directly; token endpoints are mocked)
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

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Webhook verification accepts only a valid `X-Hub-Signature-256` and rejects unsigned, mis-signed and replayed deliveries.
2. A sixth project is rejected (the first count-based limit; later limits follow its pattern).
3. Repository permission is rechecked before repo-dependent actions; downgraded or removed access blocks them.

### Acceptance criteria

- [ ] Every rule below has tests
- [ ] The 6th project is rejected; names are unique case-insensitively; owners can edit and delete, others get 404
- [ ] Unverified accounts can't create projects (the Phase 8 email-verification gate)
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

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. The role matrix (Owner, Maintainer, Viewer) against each action, with a 404 where access is denied.
2. A project always keeps at least one Owner.

### Acceptance criteria

- [ ] Tests: role matrix per action (view, edit, manage members, delete, rename)
- [ ] Non-members and insufficient roles get 404 for private resources
- [ ] A project always keeps at least one Owner; ownership transfer is explicit
- [ ] Invites are accepted or declined by the invitee only

---

## Phase 12A: Forum posts and ownership

**User stories**: 54 (posts), 59

### What to build

Create, view, edit and delete forum posts. Only the author can edit or delete (admins later through moderation).
The email-verification gate from Phase 8 applies.

### TDD behaviors

None: CRUD where others get a 404 follows the ownership pattern that Phases 10–11 already settle.

### Acceptance criteria

- [ ] Tests: CRUD, ownership (others get 404 on edit and delete), validation, unverified users blocked
- [ ] HTMX partial updates for edit and delete with CSRF

---

## Phase 12B: Comments, ratings, limits and moderation hooks

**User stories**: 54 (comments, ratings), 55

### What to build

Comments and ratings on posts, the posting limits (5 new posts per day, 5 comments per minute) as database count
checks, and hooks moderation will use (reporting a post or comment, hidden or removed states that Phase 15's
actions set). This phase introduces the `Report` model (feedback or abuse, generic over its target) in the
`reports` app; Phase 14 adds BugReport and report management on top of it.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Time-windowed limits: the sixth comment within a minute is rejected, and one after the window passes is allowed.
2. Hidden or removed content is invisible to non-admins in every list and detail view.

### Acceptance criteria

- [ ] Tests: the 6th post in a day and the 6th comment in a minute are rejected with a clear message
- [ ] Unverified accounts can't comment, rate or report (the Phase 8 email-verification gate)
- [ ] One rating per user per post (changeable, not stackable); authors can't rate their own posts
- [ ] Users can report a post or comment; hidden or removed content is invisible to non-admins

---

## Phase 12C: Search, filtering, sorting and pagination

**User stories**: 58

### What to build

Server-side search, filters, sorting and pagination for forum lists, using a shared pattern that later lists
(projects, showcases, reports) reuse.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Invalid or hostile query parameters (a bad page, an unknown sort, a non-numeric filter) fall back safely instead of erroring.

### Acceptance criteria

- [ ] Tests: search terms, each filter, each sort order, page boundaries, invalid parameters handled safely
- [ ] HTMX updates the list without a full reload; URLs are shareable (state in the query string)

*(12A–12C may be merged back into one phase if the forum turns out small.)*

---

## Phase 13: Showcases and tags

**User stories**: 56–57

### What to build

Publish, edit, delete and interact with showcases, limited to 1 new showcase per day, with many-to-many tags,
browsing by tag, and the shared list pattern from 12C. Showcase media goes through Django's storage setting.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Image uploads are rejected for the wrong type, oversized files and out-of-range dimensions.

### Acceptance criteria

- [ ] Tests: the daily limit, ownership (others get 404 on edit and delete), tag filtering, pagination
- [ ] Unverified accounts can't publish showcases (the Phase 8 email-verification gate)
- [ ] Uploaded images are validated (type, size, dimensions) and processed with Pillow

---

## Phase 14: Bug reports and report management

**User stories**: 60–63

### What to build

Validated, rate-limited bug reports (BugReport) and feedback (12B's Report) with supporting information. Project
owners and admins review, assign, comment on and update them. Status changes follow a permitted-transition table.
Access is restricted to the relevant project's authorities and admins.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Status changes follow the permitted-transition table; every allowed and forbidden change is tested.
2. Access is limited to the project's authorities, admins and the submitter; everyone else gets a 404.

### Acceptance criteria

- [ ] Tests: every allowed and forbidden status transition; the access matrix (outsiders get 404); required-field validation
- [ ] The 6th bug report a user submits in a day is rejected with a clear message (a database count check)
- [ ] Unverified accounts can't submit reports (the Phase 8 email-verification gate)

---

## Phase 15: Moderation

**User stories**: 64–66

### What to build

Admin tools to review reported content, issue warnings, hide or remove content (through 12B's hooks) and restrict
accounts. Every action writes an append-only ModerationAction.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. ModerationAction is append-only: it can't be edited or deleted through the app, and every action records the actor, target, reason and time.
2. Restricted accounts are blocked from every create action.

### Acceptance criteria

- [ ] Tests: only authorised admins can act; every action is recorded with actor, target, reason and time; records can't be edited or deleted through the app
- [ ] Restricted accounts can't post, comment, rate, publish showcases, create projects or submit reports while restricted

---

## Phase 16: REST API

**User stories**: 67 (projects)

### What to build

A versioned DRF API (`/api/v1/`) exposing project information for the engine, with token authentication and the
same permission rules as the web views. Asset endpoints arrive in Phase 17, once the Toolbox's assets live in the
Hub.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. The API shows a user exactly what the web app would show them, and a 404 otherwise.

### Acceptance criteria

- [ ] Tests: unauthenticated requests are refused; users see only what they could see in the web app (404 otherwise); throttling on
- [ ] Tokens are never returned after creation; tokens can be revoked

---

## Phase 17: Toolbox port

**User stories**: 68, 67 (assets)

### What to build

Bring the Toolbox's `catalog`, `packs` and `providers` apps into the Hub under `/toolbox/…`, keeping every existing
feature and its data. Follow an explicit migration strategy that preserves the existing models and records, and
integrate Hub authentication without breaking existing Toolbox accounts. The standalone Toolbox stays fully working
until the migration is complete and signed off.

### TDD behaviors

Built test-first with the `tdd` skill; the rest of the phase is built and tested normally.

1. Accounts are matched by verified email: existing password hashes carry over, and collisions are reported instead of merged.
2. The migration dry run checks row counts and integrity and reports mismatches.

### Acceptance criteria

- [ ] **Feature parity:** Discover, library, packs, gallery, attribution and exports behave as in the standalone Toolbox
- [ ] **Data and models:** existing Toolbox models are kept (same fields and relationships). A documented, rehearsed migration moves existing data (users, library entries, packs, preferences, API tokens) into the Hub's database, with a dry run, row-count and integrity checks, and a rollback path
- [ ] **Accounts:** existing Toolbox users can sign in to the Hub with their existing credentials (password hashes carried over); accounts are matched or merged by verified email without duplicates or lost data; collisions are reported, not silently merged
- [ ] **Providers:** the ambientCG, Poly Haven and Openverse integrations keep their existing `search()` and `get_details()` behaviour and error handling
- [ ] **Packs:** pack export and import formats stay byte-for-byte compatible with what the engine imports; packs made before the port still import
- [ ] **Tests:** the Toolbox's test suite is ported and passes in the Hub unchanged in intent; the network guard stays on
- [ ] **No regressions in the standalone Toolbox** while the migration runs: its repository and test suite stay green, and both run side by side until cut-over is signed off
- [ ] **API:** `/api/v1/` gains asset endpoints (library and packs) under Phase 16's token auth and permission rules, with tests
- [ ] The marketing `/toolbox/` overview page becomes the entry point to the live tool
