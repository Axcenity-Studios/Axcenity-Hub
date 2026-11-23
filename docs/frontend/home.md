# Home: sections, copy as data, media and motion

The Cinematic Home at `/` (`marketing:home`). `tests/test_home.py`
enforces every rule here; the colour rules are in [theme.md](theme.md).

## Files

| Path | Holds |
|---|---|
| `marketing/content.py` | All copy (`HOME_HERO`, `HOME_FEATURES`, `HOME_WORKFLOW`, `HOME_FACTS`, `HOME_TOOLBOX`, `HOME_COMMUNITY`, `HOME_FINAL`), `LUAU_SAMPLE` and the media manifest (`MEDIA`) |
| `marketing/drawings.py` | `terrain_wireframe()` (SVG geometry) and `luau_lines()` (Luau tokens) |
| `templates/marketing/home.html` | Includes one partial per section from `templates/marketing/home/` |
| `templates/marketing/media/` | `frame.html` (a 16:10 media frame and its caption), the drawn stand-ins `terrain.html`, `luau.html`, `editor.html`, and `reel.html` (the hero's reel, [reel.md](reel.md)) |
| `static/js/home.js` | Rotation, reveals and the pillars' stage. Loaded only by Home, deferred |
| `static/marketing/media/` | Media files, copied in (never edited at the source) |

## Sections, in order

`#hero`, `#features`, `#workflow`, `#facts`, `#toolbox`, `#community`,
`#start`. Each pillar is `#feature-<label>` (`#feature-world`). The nav's
Features link is `/#features` (`Link(fragment="features")`; a fragment
link is never marked as the current page). Every `[id]` in `<main>` has
`scroll-margin-top: 4rem`, so anchors stop below the fixed nav.

- **Hero:** the version badge (`ENGINE_VERSION`), "Axcenity Engine.",
  the rotating line, the pitch, Download alpha and Read the docs, over
  the full-bleed showcase reel ([reel.md](reel.md)) with its controls
  bottom right. The renderer capture is the reel's fallback. On phones
  the copy starts below the reel's compact workspace (`.hero-copy`).
  Nothing in the hero uses a reveal.
- **Features:** four pillars (Renderer, World, Logic, Editor). Below `lg`
  each shows its media inline (`.pillar-media`); from `lg` the text
  scrolls past one sticky `.stage` that shows the current pillar's media.
- **Workflow:** Build, Script, Test, Export, with outlined numerals
  (`.flow-num`, decorative and `aria-hidden`).
- **Facts:** Free, Rust, 3 OS, Alpha, as a `<dl>`.
- **Toolbox banner:** its call to action is `soon` until Phase 6.
- **Community:** Forums, Showcases, Projects, each tagged Coming soon.
- **Final CTA:** "Start building.", Download alpha and Getting started.

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

## The media manifest

`content.Media` records `kind` (`capture` or `illustrative`), `caption`,
`alt`, `provenance`, and either `src` (a static file, with
`source_size`) or `drawn` (a template). It refuses a caption that doesn't
start with its kind's label ("Engine capture" or "Illustrative"), a drawn
capture, and a file without its pixel size. Tests check that each file
exists and its PNG header matches `source_size`, that each drawn
template exists, and that every `<img>` and caption on the page is in the
manifest.

| Key | Kind | Now | Phase 5 |
|---|---|---|---|
| `renderer` | capture | `renderer-2560x1440.png` (Showcase, RT on) | responsive derivatives |
| `terrain` | illustrative | drawn wireframe hills and trees (SVG) | animated recreation |
| `logic` | illustrative | `LUAU_SAMPLE` in the monochrome tiers | animated nodes and code |
| `editor` | illustrative | drawn docking layout with a floated panel | animated recreation |
| `reel` | illustrative | the hero's canvas film ([reel.md](reel.md)) | Phase 4: Scenes 2–4 |

Drawings use only the tokens through CSS classes: no hex values and no
`fill`/`stroke` colours in the templates (tested). The Luau sample is
monochrome (keywords `fg-strong`, strings `fg-secondary`, comments
`fg-weak`) until the editor's syntax colours join the palette.

Images carry intrinsic `width`/`height` and are `loading="lazy"`,
including the hero's fallback capture (a browser running the reel never
downloads it).

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
  stays.
- The stylesheet's reduced-motion block also forces any hidden reveal to
  its final state (if the setting changes while the page is open), and
  its blanket rule makes the stage swap instantly.

## Phone width

Nothing scrolls sideways at 360 px. The Luau sample scrolls inside its
own frame (`tabindex="0"`, so the keyboard can scroll it) and its frame
grows to fit (`.pillar-media:has(.drawn-code)`). The drawn editor scales
its text with the frame (`cqi` units; `.media` is a size container).
The reel's phone layout is covered by `tests/test_reel_browser.py`; the
rest of the layout is checked by hand.
