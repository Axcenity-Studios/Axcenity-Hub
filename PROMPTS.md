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
