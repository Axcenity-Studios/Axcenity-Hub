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
