# CLAUDE.md

Axcenity Hub: the Django web app for Axcenity Engine users (CIDM final
project). Public marketing pages first; accounts, projects, forums,
showcases and reports in later phases.

- **What to build:** `prd/axcenity-hub.md`. **Build order:** `plans/axcenity-hub.md`
  (ticked boxes are done). If either is missing, planning isn't finished:
  ask, don't guess.
- **Stay in the phase.** Build only what the current plan phase asks for.

## Commands

```sh
uv sync                                     # uv only: no pip, no Node, no npm
uv run python manage.py tailwind runserver  # Django + Tailwind watcher
uv run pytest -m "not browser"              # fast tests; green before every commit
uv run pytest -m browser                    # Playwright film and media tests
uv run python manage.py make_media          # capture derivatives (after adding a capture)
uv run ruff check . && uv run ruff format .
```

## Rules that always apply

- **Stack:** Django, HTMX, Tailwind + DaisyUI via django-tailwind-cli,
  DRF, pytest. No Node toolchain; any JS library is a vendored file.
- **Access:** members-only views use `LoginRequiredMixin`; anything the
  caller doesn't own returns 404, never 403. Every write is CSRF protected.
- **Tests** live only in `tests/`, never reach the network, and mock
  external APIs (GitHub).
- **Honesty:** drawn or stylised visuals are captioned as illustrative,
  never as engine captures. The engine is alpha; copy says so. Scripting
  is **Luau**.
  Logic examples use the engine's real blocks, **When touched → Spawn
  decal**, and their real Luau translation (`part.Touched:Connect(function(otherPart)
  … workspace:SpawnDecal(…))`). There is no OnTriggerEnter block.
- **Reference repos are read-only:** the engine
  (`~/Documents/VSCode Projects/Axcenity-Engine`) and the Toolbox
  (`~/Documents/VSCode Projects/project-two-building-with-apis`). Copy
  assets in; never edit them.

## Read before…

Open the index for your area, then only the topic file it points to.
Files listed here that don't exist yet haven't been written; don't
invent their contents.

| Before you… | Read |
|---|---|
| add models, URLs, views, services | `docs/ARCHITECTURE.md` |
| touch templates, CSS, theme, motion | `docs/FRONTEND.md` |
| work on the animated loops' canvas kit (`static/reel/`) | `docs/frontend/canvas.md` |
| add or change media, captures, the hero's film or the loops | `docs/frontend/media.md` |
| write or change tests | `docs/TESTING.md` |

## Keeping docs lean

Indexes ≤ ~150 lines (rules + topic table); topic files ≤ ~200 lines,
one area each. Describe what the code does now; history goes in git and
`PROMPTS.md`. Update the doc in the same change as the code.

`PROMPTS.md` gets entries only when the user asks for the session log.
