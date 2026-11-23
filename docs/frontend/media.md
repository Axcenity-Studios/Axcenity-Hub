# Media: captures, the pipeline and the animated recreations

Every image or animation on the marketing pages is an entry in the media
manifest, `content.MEDIA` (`marketing/content.py`). It is either a
**capture** (a real, unretouched engine frame) or **illustrative** (drawn
or recreated), and its caption says which. `tests/test_home.py` checks the
manifest and the files, `tests/test_media.py` the pipeline and the loops,
and `tests/test_media_browser.py` both in Chromium.

## The manifest

`content.Media` records:

- `kind`, `caption` (starting "Engine capture" or "Illustrative"), `alt`
  and `provenance` (the project, command and settings it was made with,
  or the engine source a recreation follows)
- `source` and `source_size` for a capture, or `drawn` (a template) for a
  drawing, optionally animated by a `loop`, with `fallback_alt` describing
  the still drawing
- `display`: per slot (`inline`, `stage`, `hero`), a `Display` with its
  `sizes` attribute and its largest CSS size in each range of viewport
  widths. For a capture this is the picture's drawn size: a 16:9 picture
  covering a 16:10 frame is 10/9 as wide as the frame (`COVER_DISPLAY`).

It refuses a mislabelled caption, a drawn capture, a file without its
size, a loop without a described fallback and an item without display
sizes.

| Key | Kind | What |
|---|---|---|
| `renderer` | capture | The Showcase-Renderer project at 2560×1440, ray tracing on (`--graphics settings/rt-ultra.json`) |
| `terrain` | illustrative | Loop: sculpting hills, then scattering plants |
| `logic` | illustrative | Loop: When Touched → Spawn Decal nodes and their Luau |
| `editor` | illustrative | Loop: split, float onto Monitor 2, Reset Layout |
| `reel` | illustrative | The hero's film ([reel.md](reel.md)) |

The Showcase's terrain capture is deliberately not used (its trees and
ground don't represent the terrain toolkit), and the engine's 480×270
test references never are.

## The pipeline (captures)

- A capture's source file lives in `marketing/media_sources/`, which is
  never served. It's copied in from where it was made and never edited.
- `uv run python manage.py make_media` writes its derivatives into
  `static/marketing/media/<key>/<key>-<width>.<avif|webp|jpg>`, at every
  width in `media.WIDTHS` (640, 960, 1280, 1920, 2560) that the source can
  supply. It skips files newer than their source (`--force` rewrites) and
  refuses a source whose real size isn't `source_size`.
- Quality: AVIF 80, WebP 90, JPEG 88. Lower AVIF qualities smeared the
  renderer capture's dark wall panels.
- `templates/marketing/media/picture.html` renders a `<picture>`: AVIF,
  then WebP `<source>`s, then the JPEG `<img>` (1280 wide, with its own
  `srcset`), all with the slot's `sizes`, the source's `width`/`height`
  (no layout shift), `loading="lazy"` and `decoding="async"`.
- **No upscaling (tested):** every display size × 2 fits inside the
  source, and a derivative at least that wide exists. In the browser test,
  the file Chromium picks is at least as wide as the picture is drawn, in
  device pixels.
- The hero's fallback capture is at most 1280 × 720 CSS pixels (half the
  source), upper right in the hero, so it stays sharp on 2× screens.

**Adding a capture (Phase 6's Toolbox screenshots):** copy the file into
`marketing/media_sources/`, add a `Media` with its `source_size`,
`display` and provenance, run `make_media`, and commit the derivatives.

## The animated recreations (loops)

The Terrain, Logic and Editor pillars each show a canvas loop: an ES module
in `static/reel/loops/` with the reel's scene contract plus a still
frame:

```js
export default Object.freeze({
  id: "logic",
  duration: DURATION, // seconds; the last frame flows into the first
  still: STILL,       // the frame reduced motion shows
  render(context, time, size) { … },
});
```

The reel's determinism rules apply (no state, clock, randomness or device
pixels; tokens only), and the loops draw with the reel's helpers:
`drawing/editor.js` (windows, panels, panes), `drawing/blocks.js` (the
block Graph view), `drawing/code.js` (typed Luau) and `drawing/terrain.js`
(the heightfield, brush ring, plants and the Terrain and Scatter panes).
Phase 4's Scenes 3 and 4 can draw with the same modules. Each loop's words
come from its manifest `labels`, passed to the page as JSON in
`data-labels`. The Luau arrives already split into the editor's token kinds
(`drawings.luau_lines`).

- **Compact:** below 480 px wide each loop has its own phone layout:
  Terrain shows only the Scene View, with a chip naming the tool; Logic
  shows the graph, then the code from the Connect call down; Editor has one
  monitor and no float.
- **`main.js`** mounts each `[data-loop]` figure with `player.js` and its
  loop. Without modules, a canvas or a working loop, its drawing stays.
- **`player.js`** runs a loop only while the visitor hasn't paused it, at
  least 30 % of it is on screen, the tab is visible and (on the desktop
  stage) its pillar is current. Otherwise it requests no frames. Under
  reduced motion it shows `still` and waits for Play; the setting is
  followed live. It sizes the canvas from the frame's layout box (the
  stage scales items while they fade), redraws on theme changes, and draws
  nothing into a frame that isn't laid out.
- **The pause button** (WCAG 2.2.2) is bottom right in each frame,
  labelled from `content.LOOP_CONTROLS`, and appears once the loop is live.
- **Seeking:** `figure.dispatchEvent(new CustomEvent("loop-seek", { detail:
  seconds }))` shows any moment, for tests and screenshots.

### Fallbacks and accessibility

- Until a loop is live, and for good where it can't run, its static
  drawing shows (`.loop-fallback`: the wireframe terrain, the highlighted
  Luau, the drawn editor), named by `fallback_alt`.
- Once live, the canvas is `aria-hidden` and the frame is described by a
  `.sr-only` paragraph holding `alt`, which describes the film.

### Fidelity notes

Each loop's `provenance` names its engine sources. Two deliberate
differences: the terrain brush ring and the dock's drop preview are drawn
in ink, not the editor's accent (the accent has fixed uses on this site),
and the whole UI is monochrome apart from the Logic loop's content colours
([theme.md](theme.md)).

## Screenshots

`tests/test_media_browser.py::test_media_is_sharp_and_framed_at_every_width`
opens Home at 360, 768, 1280, 1440 and 2560 px, dark and light, 1× and 2×.
It checks each pillar's frame (16:10, a sharp enough file or a canvas at
the full pixel ratio, no sideways scroll) and saves
`screenshots/media/<width>-<scheme>-<scale>x-<key>.png` (git-ignored) for
review by eye. These aren't pixel comparisons.
