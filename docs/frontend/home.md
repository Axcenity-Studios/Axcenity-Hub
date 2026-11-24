# Home: sections, copy as data, media and motion

The Cinematic Home at `/` (`marketing:home`). `tests/test_home.py`
enforces every rule here; the colour rules are in [theme.md](theme.md).

## Files

| Path | Holds |
|---|---|
| `marketing/content.py` | All copy (`HOME_HERO`, `HOME_FEATURES`, `HOME_WORKFLOW`, `HOME_FACTS`, `HOME_TOOLBOX`, `HOME_COMMUNITY`, `HOME_FINAL`), `LUAU_SAMPLE` and the media manifest (`MEDIA`, [media.md](media.md)) |
| `marketing/drawings.py` | `terrain_wireframe()` (SVG geometry) and `luau_lines()` (Luau tokens, as the editor colours them) |
| `templates/marketing/home.html` | Includes one partial per section from `templates/marketing/home/` |
| `templates/marketing/media/` | `frame.html` (a 16:10 frame: a capture's `picture.html`, or a loop's canvas over its drawing, and the caption), the loops' fallback drawings `terrain.html`, `luau.html`, `editor.html`, `toolbox.html`, `animation.html` and `wipe.html` |
| `static/js/home.js` | The hero's film, rotation, reveals and the pillars' stage. Loaded only by Home, deferred (the motifs play through `shell.js`, on every page) |
| `static/reel/loops/` | The animated recreations ([media.md](media.md), [canvas.md](canvas.md)), loaded as one module at the end of the page |
| `static/marketing/media/` | Capture derivatives written by `make_media` (sources in `marketing/media_sources/`), and the hero's film in `homestead/` |

## Sections, in order

`#hero`, `#features`, `#workflow`, `#facts`, `#toolbox`, `#community`,
`#start`. Each pillar is `#feature-<label>` (`#feature-world`). The nav's
Features link is `/#features` (`Link(fragment="features")`; a fragment
link is never marked as the current page). Every `[id]` in `<main>` has
`scroll-margin-top: 4rem`, so anchors stop below the fixed nav.

- **Hero:** the version badge (`ENGINE_VERSION`), "Axcenity Engine.",
  the rotating line, the pitch, Download alpha (`/download/`) and Read the docs, over
  the full-bleed Desert Homestead film ([media.md](media.md)) with its
  caption and pause button bottom right. The badge sits on the page
  colour so it reads over any frame. Nothing in the hero uses a reveal.
- **Features:** four pillars (Renderer, World, Logic, Editor). Below `lg`
  each shows its media inline (`.pillar-media`); from `lg` the text
  scrolls past one sticky `.stage` that shows the current pillar's media.
- **Workflow:** Build, Script, Test, Export, with outlined numerals
  (`.flow-num`, decorative and `aria-hidden`), each with its motif to
  the right (`.flow-head`).
- **Facts:** Free, Rust, 3 OS, Alpha, as a `<dl>`, each title with its
  motif to the left (`.stat-title`). One column on phones, two from
  `sm`, four from `lg`; the titles step up to `text-7xl` only from `xl`,
  so every row fits beside its motif (tested from 360 to 1280 px).
- **The split panel** (Toolbox banner, Community, Final CTA): a `.panel`
  in two halves (stacked below `lg`) ruled by `.split`, one holding a loop
  (`.section-media`), the other copy and a `.panel-list` (three in a row
  from `sm`, or `.panel-list-stack`, one under another). The loop
  alternates sides: right, left, right.
- **Toolbox banner:** the copy and its three features beside the Toolbox
  loop; Explore the Toolbox links to `/toolbox/` ([toolbox.md](toolbox.md)).
- **Community:** the heading, then the renderer wipe beside Forums,
  Showcases and Projects, each tagged Coming soon.
- **Final CTA:** "Start building." across the page, then the pitch,
  Download alpha, Getting started and the guide's first three steps
  (`HOME_FINAL["steps"]`: Install, New Project, Play) beside the
  Animation loop.

## Motifs

Each workflow step and fact names a line icon (`Item.icon`) from
`partials/icon.html`, drawn with `class="motif"` (decorative:
`aria-hidden`), sized with its numeral (`.flow-motif`) or its title
(`.stat-motif`, 0.8 em). It plays **each time it comes into view**:
`shell.js` sets `data-on` once it's 60 % in view and clears it only when
it's fully off screen (`html[data-motifs]` marks that it's running).
Until then it's hidden; then its `.m-draw` strokes draw in
(`pathLength="1"`, dash offset 1 to 0) and one other part makes a single
move, `--stagger` × 80 ms late like the reveals: the
cube drops onto its line (Build), the caret blinks (Script), Play pops
and ripples (Test), the arrow rises (Export), the padlock's shackle
lifts open (Free), the cog turns into place (Rust), three windows stack
in (3 OS) and bubbles rise in the flask (Alpha). All hiding and every
animation is behind `html[data-motifs]` (tested), so without JavaScript
or under reduced motion they're simply drawn.

## Copy is data

Every heading, paragraph, button label, caption and drawn label comes
from `content.py`. The test reads the text a sighted visitor sees inside
`<main>` and checks each piece is a content string. It doesn't police
accessibility labels: `.sr-only` text and attributes (`aria-label`,
`alt`) may be written in a template. Shared shell labels ("Soon") are
allowed by name. Code (`<pre>`) is checked on its own: it must render
`LUAU_SAMPLE` exactly.

**Honesty:** copy says alpha, Luau (never "Lua"), free, open source and
Windows, macOS and Linux, and claims no mobile, web or console export.
Logic examples use the engine's real blocks, **When touched → Spawn
decal**, and their real Luau translation
(`part.Touched:Connect(function(otherPart) … workspace:SpawnDecal(…))`).
There is no OnTriggerEnter block.

## Media

Each pillar's media is a manifest entry ([media.md](media.md)): the
Renderer pillar shows the ray-traced capture as a `<picture>`; World,
Logic and Editor show animated canvas recreations with their drawings as
fallbacks. Every frame is captioned "Engine capture" or "Illustrative".

| Pillar | Key | Media |
|---|---|---|
| Renderer | `renderer` | Capture, AVIF/WebP/JPEG derivatives |
| World | `terrain` | Loop: Raise / Lower hills, then Scatter plants |
| Logic | `logic` | Loop: When touched → Spawn decal as blocks, then as Graph nodes, with its Luau typing out |
| Editor | `editor` | Loop: split the Scene View, float Properties, Reset Layout |

Drawings use only the tokens through CSS classes: no hex values and no
`fill`/`stroke` colours in the templates (tested). The Luau fallback is
highlighted in the editor's syntax colours (`.luau-*`,
[theme.md](theme.md)), as the Logic loop draws it.

## The rotating headline

All four phrases sit in one grid cell (`.rotator > span { grid-area: 1 /
1; }`), so the line is always as tall as its longest phrase at every
width, and changing phrase never moves the pitch below it. One phrase at
a time has `data-on` (the first, server-side). `home.js` moves it every
2.8 s: the leaving phrase gets `data-out` and rises away, the next rises
in from below. The phrases are `aria-hidden`; screen readers hear
`rotating_summary` once, from a `.sr-only` span in the `<h1>`. It pauses
while the tab is hidden.

## Reveals

`[data-reveal]` elements rise out of an 8 px blur, `--stagger` × 80 ms
late. They're hidden only under `html[data-reveals]`, which `home.js`
sets after marking everything already on screen as shown (`data-in`).
Without JavaScript, or without IntersectionObserver, everything simply
shows.

## The pillars' stage

`home.js` watches each pillar with a band across the middle of the
screen (`rootMargin: -45% 0 -45% 0`). The pillar in the band gets
`data-on` (full strength; the others dim to 35 % once
`[data-pillars][data-live]` is set) and the matching `.stage-item` shows.
At start it picks the pillar already across the middle, so a
`#feature-…` link opens on the right media. Inactive stage items are
`visibility: hidden`, so assistive technology meets only the current one.

## Reduced motion

- `home.js` doesn't turn reveals on and doesn't rotate: the first phrase
  stays, and the motifs rest fully drawn.
- The stylesheet's reduced-motion block also forces any hidden reveal to
  its final state (if the setting changes while the page is open), and
  its blanket rule makes the stage swap instantly.
- The hero's film doesn't autoplay (its poster shows), and the loops
  each show their still frame; each has a Play button ([media.md](media.md)).

## Phone width

Nothing scrolls sideways at 360 px. The Luau fallback scrolls inside its
own frame (`tabindex="0"`, so the keyboard can scroll it) and its frame
grows to fit until the loop is live (`.pillar-media:not([data-live]):has(.drawn-code)`).
The stat band's columns and title sizes keep each title beside its motif
(Sections, above). The drawn editor scales its text with the frame
(`cqi` units; `.media` is a size container). The hero's film is
covered at 360 px by `tests/test_hero_browser.py`, every media frame at
360 to 2560 px by `tests/test_media_browser.py`; the rest is checked by hand.
