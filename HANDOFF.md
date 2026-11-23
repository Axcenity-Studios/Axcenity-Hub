# Handoff — Axcenity Hub

**Status (2026-11-23):** planning is complete; no application code exists yet.
**Next session:** build **Phase 1** of [plans/axcenity-hub.md](plans/axcenity-hub.md)
(skeleton, theme foundation, marketing shell, bare Home, test layout, docs
indexes), then continue phase by phase.

## Read first (in this order)

1. [CLAUDE.md](CLAUDE.md): commands, rules that always apply, doc pointers.
2. [plans/axcenity-hub.md](plans/axcenity-hub.md): architectural decisions
   and the current phase's acceptance criteria. Tick boxes as they're met.
3. [prd/axcenity-hub.md](prd/axcenity-hub.md): only the stories and
   decisions the current phase names.
4. Only when a phase needs it:
   - [prototypes/home-direction.md](prototypes/home-direction.md): the
     chosen Cinematic direction, its four required fixes, the accent, and
     which captures to use or avoid (Phases 2–5). The visual reference is
     `prototypes/home-direction.html` (open it in a browser and keep
     variant A). It's throwaway: copy ideas, not code structure.
   - [docs/research/external-services.md](docs/research/external-services.md):
     Phases 7–10 and any external service.
5. [PROMPTS.md](PROMPTS.md): how the decisions were reached and what went
   sideways, if context is needed.

## Reference sources outside this repo (read-only)

- **Toolbox** (theme to port in Phase 1; app to port in Phase 17):
  `~/Documents/VSCode Projects/project-two-building-with-apis`.
  - The theme is in `styles/source.css`: the theme block, the `@theme`
    tokens, and the light set under `html[data-scheme="light"]`.
  - Its rules are in `docs/frontend/theme.md` and `docs/frontend/motion.md`.
  - The tests to port are `tests/test_theme.py` and `tests/test_shell.py`.
  - Fonts and brand images are in `static/fonts` and `static/brand`.
  - Settings show the no-Node Tailwind/DaisyUI setup
    (`TAILWIND_CLI_USE_DAISY_UI`, `TAILWIND_CLI_SRC_CSS`).
- **Engine** (branding, and the UI the reel recreates):
  `~/Documents/VSCode Projects/Axcenity-Engine`.
  - Branding: `assets/branding/`
  - Editor palette: `crates/editor-kit/src/theme.rs`
  - Luau highlighting: `crates/editor-kit/src/lua_syntax.rs`
  - Node styling: `crates/editor-node-graph/src/draw.rs`
  - Block names: `crates/blocks-runtime/`
  - Terrain and scatter UI: `crates/editor/src/terrain_studio.rs` and `scatter_pane.rs`
  - Ray-tracing shaders: `crates/render/src/ray_*.wgsl`
  - The engine repo has uncommitted work that belongs to the user. Never
    edit, build or commit there.
- **Showcase captures** (Phases 4–5): `~/Projects/Axcenity Projects/Showcase/captures/`.
  - Use `renderer-2560x1440.png` (ray tracing on) and
    `renderer-graybox-2560x1440.png` (same camera, no ray tracing) for the
    Scene 2 wipe.
  - **Don't use `terrain-2560x1440.png`.** The user rejected it.
  - The Showcase `README.md` documents how each was made, which the media
    manifest's provenance field needs.

## Gotchas learned this session

- No Chromium is installed. Headless Firefox works for quick screenshots
  (`firefox --headless --screenshot`). Phase 3's Playwright tests need
  `uv run playwright install chromium` once.
- Engine releases are all prereleases: link to `/releases`, not
  `/releases/latest` (the API 404s and the web link only redirects).
- Never upscale the engine's 480×270 test references. Phase 5 requires
  display size × 2 ≤ source size.
- Above-the-fold elements must not use the scroll-reveal fade (they start
  invisible). The prototype hit this.
- The engine scripts in **Luau**. Say "Luau" everywhere, even though the
  original brief said "Lua".
- Settings needed by later phases depend on open questions in the research
  note (GitHub sign-in vs. link, private repos, hosting, domain, MySQL
  requirement). Ask the user when the phase that needs one starts; don't
  guess.

## Repo state

- Branch `main` holds all planning work (merged from `plan/hub-first-slice`).
  Nothing is pushed.
- `PROMPTS.md` gets entries only when the user asks for the session log.

## Suggested skills

- **`/implement axcenity-hub phase 1`** (user-invoked): builds one plan
  phase end to end and decides whether to delegate to `tdd`. Each phase's
  "TDD behaviors" section in the plan lists what to build test-first
  (none for Phases 1–6 and 12A); everything else gets tests alongside.
- **`tdd`**: only for the behaviors a phase's "TDD behaviors" section lists.
- **`run`**: start the Django app and check pages in a browser, and run
  the Toolbox locally for Phase 6's screenshots.
- **`prototype`**: only if a visual question reopens (for example reel
  scene styling) before committing to production code.
- **`research`**: before Phases 7–10 if a service detail in the research
  note is unconfirmed (it lists which claims are).
- **`code-review`** / **`simplify`**: after each phase, before committing.
- **`handoff`** (user-invoked): at the end of each session.
