# Media: captures, the hero's film, the pipeline and the animated recreations

Every image or animation on the marketing pages is an entry in the media
manifest, `content.MEDIA` (`marketing/content.py`). It is either a
**capture** (a real, unretouched frame) or **illustrative** (drawn or
recreated), and its caption says which. A capture's `subject` says what
it shows: the engine ("Engine capture", the default) or the Toolbox
("Toolbox screenshot", `CAPTURE_SUBJECTS`), so a Toolbox screenshot is
never presented as the engine's. The engine docs' diagrams are
illustrative too: their entries are in `documentation/diagrams.py`.
Each is captioned "Diagram", served as its 1200 px PNG and never drawn
wider than 600 CSS px, so it's never upscaled
([documentation.md](documentation.md)). `tests/test_home.py` checks the
manifest and the files, `tests/test_media.py` the pipeline and the loops,
and `tests/test_media_browser.py` both in Chromium. The hero's film is
checked by `tests/test_hero.py` and `tests/test_hero_browser.py`.

## The manifest

`content.Media` records:

- `kind`, `subject` (captures), `caption` (starting with `label`: "Engine
  capture", "Toolbox screenshot" or "Illustrative"), `alt`
  and `provenance` (the project, command and settings it was made with,
  or the engine source a recreation follows)
- `source` and `source_size` for a capture, or `drawn` (a template) for a
  drawing, optionally animated by a `loop`, with `fallback_alt` describing
  the still drawing
- `display`: per slot (`inline`, `stage`, `section`), a `Display` with its
  `sizes` attribute and its largest CSS size in each range of viewport
  widths. For a capture this is the picture's drawn size: a 16:9 picture
  covering a 16:10 frame is 10/9 as wide as the frame (`COVER_DISPLAY`).
- `light`: a capture's light-theme twin, shown instead when the site is
  light (`frame.html` renders a `<picture>` per scheme; see
  [toolbox.md](toolbox.md))
- `capture`: for a loop that draws a capture (the wipe), that `Media`;
  its WebP `srcset` goes to the canvas as `data-capture`

It refuses a mislabelled caption, a drawn capture, a file without its
size, a loop without a described fallback and an item without display
sizes.

| Key | Kind | What |
|---|---|---|
| `renderer` | capture | The Showcase-Renderer project at 2560×1440, ray tracing on (`--graphics settings/rt-ultra.json`) |
| `terrain` | illustrative | Loop: sculpting hills, then scattering plants |
| `logic` | illustrative | Loop: When touched → Spawn decal as blocks, then as Graph nodes, and their Luau |
| `editor` | illustrative | Loop: split, float onto Monitor 2, Reset Layout |
| `toolbox` | illustrative | Loop (Toolbox banner): search "rock", drag Rock 030 onto the Pad |
| `wipe` | illustrative | Loop (Community): a grey room wiped into the `renderer` capture |
| `animation` | illustrative | Loop (Start building): key a Wave clip, play it back |
| `toolbox-discover`, `toolbox-library`, `toolbox-packs` (+ `-light`) | capture (Toolbox) | The Toolbox page's screenshots, 2560×1600, each with a light-theme twin shown when the site is light; recorded in `toolbox-capture.json` ([toolbox.md](toolbox.md)) |

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
**Adding a capture:** copy the file into `marketing/media_sources/`, add
a `Media` with its `source_size`, `display` and provenance, run
`make_media`, and commit the derivatives. Sources are committed static
assets: the tests only read them and never run `make_media` on them
(the pipeline's tests use a fake source in `tmp_path`).

## The hero's film

`HOME_HERO["backdrop"]` (`content.BackdropVideo`: ordered `sources`, each
a `VideoSource` with its file and RFC 6381 codecs, plus kind, caption,
provenance and poster) fills the hero. It's a capture: every frame is
the engine's renderer (the `examples/desert-homestead` project's
`authoring/film`, 1920×804, hardware ray tracing).

- **Files** (`static/marketing/media/homestead/`): `homestead-1920.webm`
  (AV1, SVT-AV1 CRF 36, about 8 MB) first, `homestead-1280.mp4` (H.264
  High at 1280×536, OpenH264 1.8 Mbit/s, about 11 MB) for browsers
  without AV1, and `homestead-poster.webp` (the first frame). The codecs
  in each `<source>` type let a browser skip one it can't decode. Budget
  (tested): 24 MB of video, 300 KB of poster.
- **The cut** (53.3 s, from `desert-homestead-cinematic-1080p-v3.mp4`):
  only the picture (`crop=1920:804:0:138`), so no title, captions or end
  card; no lightning (strikes at 37.5–37.9, 42.4–42.8, 48.3, 51.8 and
  61.2 s); no grading; 1 s dissolves (1.2 s into the storm and the snow,
  1.5 s into the dawn). Source seconds: spring valley 108.4–112.8, porch
  8.1–13.9, drapes 14.1–20.9, truck 21.1–27.9, windmill 28.1–32.6, storm
  38.2–42.2, rain off the porch 57.6–61.0, lamplight 63.6–69.9, snow at
  dusk 79.0–86.4, lit door 92.8–97.9, dawn thaw 98.7–108.4. The last shot
  ends on the frame before the first begins, so the loop is seamless.
- **Playback** (`home.js`): muted, `loop`, `playsinline`, `aria-hidden`,
  never `autoplay`. It plays only while the visitor hasn't paused it, at
  least 30 % of it is on screen and the tab is visible; under reduced
  motion the poster shows and the button plays it, followed live.
- **The scrim** darkens (light mode: lightens) a band under the nav, a
  pool behind the copy and the bottom edge; the caption sits above the
  pause button, bottom right.
- **Serving:** Safari plays `<video>` only from a server that answers
  byte-range requests (206). Django's development server doesn't, so
  Safari shows the poster there; production static serving must.

## The animated recreations (loops)

Each loop is an ES module in `static/reel/loops/`; the kit, the contract
and the determinism rules are in [canvas.md](canvas.md). Each loop's
words come from its manifest `labels`, passed to the page as JSON in
`data-labels`.

| Loop | Where | Length | Shows |
|---|---|---|---|
| `editor`, `terrain` | The Editor and World pillars (inline, and on the stage from `lg`) | 12 s | Docking; Raise / Lower and Scatter |
| `logic` | The Logic pillar | 16 s | The script's bar on Blocks: the When touched hat and the Spawn decal block snap together while the Luau types out; the bar switches to Graph, the nodes wire up and a pulse runs; back to Blocks, then all fades |
| `toolbox` | Toolbox banner, beside its copy | 12 s | The Toolbox opens from Assets, searches "rock", Rock 030 is dragged onto the Pad, which takes the texture; it closes |
| `wipe` | Community, beside the cards | 10 s | The built grey room, a scan line wipes it into the ray-traced capture, then sweeps back; the camera eases in and out |
| `animation` | Start building, beside the pitch and steps | 10 s | Record, five key columns posed by the hand, Play (six passes), the keys fade |

- **Compact:** below 480 px each has a phone layout: Terrain shows only
  the Scene View; Logic one view at a time (Blocks, panning across the
  wide block, then Graph, then Code from the Connect call); Editor one monitor; the
  Toolbox its compact pane; Animation its compact pane with no pointer;
  the wipe larger tab type.
- **`player.js`** runs a loop only while the visitor hasn't paused it, at
  least 30 % of it is on screen, the tab is visible and (on the desktop
  stage) its pillar is current. Otherwise it requests no frames. Under
  reduced motion it shows `still` and waits for Play, followed live. It
  sizes the canvas from the frame's layout box, redraws on theme changes,
  and for `data-capture` loads the smallest WebP at least 1.2 × the
  frame's width in device pixels (the capture covers the frame, pushed in).
- **The pause button** (WCAG 2.2.2) is bottom right in each frame,
  labelled from `content.LOOP_CONTROLS`, and appears once the loop is live.
- **Seeking:** `figure.dispatchEvent(new CustomEvent("loop-seek", { detail:
  seconds }))` shows any moment, for tests and screenshots.
- **Fallbacks:** until a loop is live, and for good where it can't run,
  its drawing shows (`.loop-fallback`: the wireframe terrain, the
  highlighted Luau, the drawn editor, the Toolbox's results, the dope
  sheet, or for the wipe the capture's own `<picture>`), named by
  `fallback_alt`. Once live, the canvas is `aria-hidden` and a `.sr-only`
  paragraph holds `alt`, which describes the film.

## Screenshots

`tests/test_media_browser.py::test_media_is_sharp_and_framed_at_every_width`
opens Home at 360, 768, 1280, 1440 and 2560 px, dark and light, 1× and 2×.
It checks each pillar's and section's frame (16:10, a sharp enough file or a canvas at
the full pixel ratio, no sideways scroll) and saves
`screenshots/media/<width>-<scheme>-<scale>x-<key>.png` (git-ignored) for
review by eye. These aren't pixel comparisons. The Toolbox page's
screenshots get the same check in
`test_toolbox_screenshots_are_sharp_and_framed_at_every_width`.
