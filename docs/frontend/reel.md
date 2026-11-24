# The showcase reel

The full-bleed film behind the Home's hero: an illustrative recreation of
the editor, drawn live on a canvas. Native ES modules in `static/reel/`,
no dependencies. `tests/test_reel.py` checks the markup and the contract
as written; `tests/test_reel_browser.py` checks the behaviour in
Chromium. The colour rules are in [theme.md](theme.md).

## Files

| Path | Holds |
|---|---|
| `templates/marketing/media/reel.html` | The figure (canvas, fallback capture, caption, description), the inline probe, the labels as JSON, the controls, and the module script |
| `static/reel/main.js` | Entry: checks for a 2D canvas, loads `player.js`, falls back on any failure |
| `static/reel/player.js` | Mounting, drawing, controls, keyboard, visibility, reduced motion, theme and resize |
| `static/reel/timeline.js` | The registered segments, scene markers, `wrap`, `segmentAt`, `nextMarker`/`previousMarker`, the clock |
| `static/reel/easing.js` | Pure helpers: `clamp`, `lerp`, `progress`, `expoOut`, `spring` (closed form), `lerpRect`, `rect` |
| `static/reel/canvas.js` | Pixel ratio (capped at 2), logical size (the layout box, so transforms don't shrink it), `fit`, `useLogicalPixels`, `groupLayer` (group opacity, shared with the loops), `readPalette`, `tint`, `FONTS` |
| `static/reel/scenes/*.js` | One module per segment: `workspace`, `toolbox`, `animation`, `renderer`, `world`, `logic`, `lockup` |
| `static/reel/drawing/layout.js` | Where everything goes: `stageRect`, `workspaceLayout` (the dock with a movable bottom split, the two floating windows, compact widening), `innerOf`, `BOTTOM_SHARE`, `COMPACT_TOP`/`COMPACT_ASPECT` |
| `static/reel/drawing/editor.js` | The editor's pieces: windows, tab bars, panels, buttons, the viewport (and the Pad's rock texture), Explorer, Properties, Console (lines arriving), Terrain and Assets panes (the Toolbox button), the pointer |
| `static/reel/drawing/toolbox.js`, `animation.js`, `renderer.js` | The Toolbox pane and its cards, the Animation pane (the Wave clip, the mannequin, the dope sheet, the transport), and the renderer wipe (the drawn grey room, the capture, the scan line) |
| `static/reel/drawing/blocks.js`, `code.js`, `terrain.js` | The block Graph view, typed Luau, and the heightfield, brush and plants with the Terrain and Scatter panes. Shared by the pillars' loops ([media.md](media.md)) and Scenes 5 and 6 |
| `static/reel/loops/` | The feature pillars' loops: the same contract plus a still frame ([media.md](media.md)) |
| `marketing/content.py` | `MEDIA["reel"]`: caption, description (its `alt`), provenance, the drawn words (`labels`, with `REEL_TOOLBOX`, `REEL_ANIMATION`, `REEL_SCRIPT`, `TERRAIN_LABELS`, `LOGIC_LABELS`); `REEL_CONTROLS` |
| `templates/marketing/media/reel.html` `data-capture` | The renderer capture's 1920 px WebP derivative, for Scene 4's wipe |
| `templates/marketing/media/reel.html` `data-copy` | The hero copy's id: the player passes its top to the scenes as `size.copyTop` (layout boxes), so the outro's logo stays above it |
| `marketing/content.py` `HOME_HERO["backdrop"]` | The demo video behind the reel (`BackdropVideo`: file, kind, caption, provenance, poster), or `None` |

## The timeline

| Segment | Time | Marker | Now |
|---|---|---|---|
| `workspace` (Scene 1) | 0–4 s | 0 s | Kinetic type, panels spring into the dock, the pointer drags Properties and the Console out |
| `toolbox` (Scene 2) | 4–8 s | 4 s | The Toolbox opens, searches "rock", a card is dragged onto the Pad |
| `animation` (Scene 3) | 8–12 s | 8 s | A Wave clip is keyed on the character, then played back |
| `renderer` (Scene 4) | 12–16 s | 12 s | A grey room builds up and a scan line wipes it into the ray-traced capture |
| `world` (Scene 5) | 16–20 s | 16 s | Raise / Lower brushes hills up, Scatter paints plants over them |
| `logic` (Scene 6) | 20–24 s | 20 s | When Touched → Spawn Decal wired by the pointer, its Luau typing out, a pulse |
| `lockup` (outro) | 24–26 s | none | The Logic scene's last frame shrinks and fades as one layer, the wordmark comes up centred across the hero above the copy, then fades to the empty first frame |

- `DURATION` is 26 s. `wrap(t)` maps any time into [0, 26): **26 s is
  the loop's first frame**, and anything not finite is 0.
- **Scene markers** are the six scene starts (`MARKERS`: 0, 4, 8, 12, 16,
  20). They're the scrubber's six ticks and the only stops for ← and →. The
  outro is a segment but not a scene, so it has no marker. The track's
  own ends are the timeline's start and end.
- → goes to the next marker; from scene 6 or the outro it wraps to 0.
  ← goes to the current scene's start, or the one before within 0.3 s
  of a start (`BACK_GRACE`); before the first scene's grace it wraps to
  scene 6.
- `LOCKUP_FRAME` (25 s) is the logo fully shown. Reduced motion opens on
  it.
- The last frame (empty page) is Scene 1's first, so the wrap has no
  visible reset.

## The scene contract

Every segment, placeholders included, is a module whose default export is

```js
export default Object.freeze({
  id: "renderer",
  start: START,         // seconds into the loop
  duration: DURATION,   // seconds
  render(context, time, size) { … },  // time: seconds into this segment
});
```

`timeline.js` imports each module and checks the table when it loads:
every segment frozen, an id, a finite start, a positive duration,
`render` taking three arguments, no gaps or overlaps, ending at 26 s.
**To change a scene, change its module**; the timeline and player don't
change (but the next scene starts from its end: [reel-scenes.md](reel-scenes.md)). One scene becomes one Remotion `<Sequence>`; compact
mode becomes a prop.

- **`context`** (frozen, rebuilt by the player): `g` (the 2D context,
  already mapped to logical pixels), `colors` (the tokens, camelCase),
  `labels` (the words from `content.py`, deep-frozen), `images`
  (`wordmark`, tinted `fg-strong`, and `capture`, the renderer capture for
  Scene 4; each `null` until loaded), and
  `layer(alpha, draw)`: draws `draw(layerContext)` into an offscreen
  buffer (with `g`'s current transform) and composites it at `alpha` as
  one picture. Use it to fade anything made of overlapping pieces;
  drawing each piece at partial alpha lets the ones beneath show
  through. The buffer is cleared on every use.
- **`size`** (frozen): `width` and `height` in **logical (CSS) pixels**,
  and `compact` (width under 640). Scenes never see physical pixels.

### Determinism rules (tested)

- **Pure:** a frame depends only on `(context, time, size)`. These
  rules cover `scenes/` and `drawing/`. No state at module level (`let`/`var`), and no `Math.random`, `Date`,
  `performance`, `requestAnimationFrame`, `window`, `document`,
  `devicePixelRatio` or `canvas.width`/`height` in a scene.
- **Seek anywhere:** a frame never depends on the frames before it.
  Springs are closed-form (`spring(seconds)`), and every transition is
  computed from `time`, so seeking into the middle of a scene draws the
  same picture as playing up to it.
- **Logical pixels:** the player sets `g.setTransform(canvas.width /
  size.width, …)` before each frame, so every coordinate is derived from
  `size`. Avoid `shadowBlur` and `filter` blur (they work in device
  pixels); shadows are stacked translucent rectangles.
- **Resizing** reallocates the canvas and redraws the clock's current
  time: the timing never changes.
- **Colours** come only from the tokens (`canvas.js` `TOKENS`); no hex,
  `rgb()` or `hsl()` in any reel file. Every pair a scene draws is a
  tested contrast pair.
- The player wraps each `render` in `save()`/`restore()`; scenes may set
  any state on `g`.

## The scenes

Each scene's storyboard, the view chain that carries the workspace from
one scene to the next, and the pointer's paths are in
[reel-scenes.md](reel-scenes.md).

## Compact mode (below 640 px)

The same timeline. The stage is the top of the hero (`COMPACT_TOP` 108 px,
`COMPACT_ASPECT` 0.62 of its width); the hero's CSS reserves the same
space above the copy (`.hero-copy`, tested). Only the Scene View and the
Explorer, docked side by side, at larger type; no pointer and nothing
undocks. From Scene 2 the Scene place widens over the Explorer, and each
scene shows its step there in a compact layout of its pane.
The Script tab takes the Toolbox tab's place, as four don't fit.

## Playback

It runs only while all of these hold: the visitor hasn't paused it,
at least 30 % of it is on screen (IntersectionObserver), and the tab is
visible. Otherwise no animation frame is requested at all.

- **Reduced motion:** no autoplay; opens on `LOCKUP_FRAME` with the Play
  button showing. The setting is followed live: turning it on pauses on
  the lockup; turning it off resumes.
- **Hidden tab:** a page loaded in a background tab doesn't start until
  it's shown.
- **Controls:** a play/pause button (its label says what it will do) and
  a range input (`step` 0.1 s, `aria-valuetext` such as "0:02 of 0:26,
  Scene 1, Workspace"). Space toggles anywhere in the controls; ← and →
  jump markers on the button, but **on the range they keep their native
  fine seeking**. The thumb stays where it's dragged (to 18 s shows 0 s).
- **Visibility of the controls:** they fade in on hover (behind the hover
  gate) or focus, and stay visible on touch screens and whenever the
  visitor has paused (so reduced motion's Play is always there).
- `data-state` (`playing`/`paused`), `data-motion` (`full`/`reduced`),
  `data-size` and `data-ready` (fonts and logo loaded) on the figure are
  for tests and debugging.

## The backdrop video

With `HOME_HERO["backdrop"]` set, a `<video class="reel-backdrop">` loops
full bleed (`object-fit: cover`) under the canvas, with its own caption
under the reel's, and the figure gets `data-backdrop`. Its kind and
caption follow the media rules (an engine recording is a capture);
`.mp4` or `.webm` only.

- It's muted, `playsinline`, `aria-hidden` and never `autoplay`: the
  player plays and pauses it with the reel, so Pause, reduced motion
  (the poster shows), off screen and a hidden tab all stop it.
- `data-backdrop` swaps the scrims for lighter ones: a thin band under
  the nav and a pool behind the copy at the bottom left. The rest of the
  video shows at full strength, and fully between the outro and Scene 1.
- It shows only with the live reel; the fallback capture replaces it.

## Accessibility and fallbacks

- The canvas is `aria-hidden`. The figure is named by its caption
  ("Illustrative · editor recreation") and, once live, described by
  `#reel-description`: every scene in order, from the docking to the
  wired blocks (`MEDIA["reel"].alt`, tested).
- **No JavaScript, no ES modules or no 2D canvas:** the renderer capture
  shows with its own caption, and the controls stay hidden. An inline
  probe sets `data-pending` only when modules and a 2D canvas exist,
  hiding the capture before layout; it's `loading="lazy"`, so a browser
  that runs the reel never downloads it. `main.js` falls back
  (`data-fallback`) if any module fails to load or mount.
- Theme changes (`html[data-scheme]`) re-read the tokens and redraw.

## Gotchas

- Every font a scene draws with must be in `canvas.js` `FONTS` (tested):
  a face drawn before it loads paints in a fallback on its first frame,
  so the same moment would look different twice.
- The canvas reads every token at runtime, so `source.css` uses
  `@theme static` (Tailwind otherwise drops a token no utility uses, and
  an empty colour silently keeps the previous fill).

- Keep a `MediaQueryList` reachable from something long-lived (the
  player reads `reduce` in `update()`): one held only by its own listener
  can be garbage-collected, and its change event never fires.
- Inner modules are imported without a version query, so a browser may
  keep an old scene after an edit until it revalidates; reload hard.
