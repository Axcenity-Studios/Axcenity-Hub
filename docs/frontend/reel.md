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
| `static/reel/scenes/*.js` | One module per segment: `workspace`, `renderer`, `world`, `logic`, `lockup` |
| `static/reel/drawing/layout.js` | Where everything goes: `stageRect`, `workspaceLayout` (the dock, the two floating windows), `COMPACT_TOP`/`COMPACT_ASPECT` |
| `static/reel/drawing/editor.js` | The editor's pieces: windows, tab bars, panels, the viewport, Explorer, Properties, Console, Terrain and Assets panes, the pointer |
| `static/reel/drawing/blocks.js`, `code.js`, `terrain.js` | The block Graph view, typed Luau, and the heightfield, brush and plants with the Terrain and Scatter panes. Drawn by the pillars' loops now ([media.md](media.md)), ready for Scenes 3 and 4 |
| `static/reel/loops/` | The feature pillars' loops: the same contract plus a still frame ([media.md](media.md)) |
| `marketing/content.py` | `MEDIA["reel"]`: caption, description (its `alt`), provenance, the drawn words (`labels`); `REEL_CONTROLS` |

## The timeline

| Segment | Time | Marker | Now |
|---|---|---|---|
| `workspace` (Scene 1) | 0–4 s | 0 s | Kinetic type, panels spring into the dock, the pointer drags Properties and the Console out |
| `renderer` (Scene 2) | 4–8 s | 4 s | The finished workspace (Phase 4: the graybox-to-lit wipe) |
| `world` (Scene 3) | 8–12 s | 8 s | The finished workspace (Phase 4: terrain and foliage) |
| `logic` (Scene 4) | 12–16 s | 12 s | The finished workspace (Phase 4: blocks and Luau) |
| `lockup` (outro) | 16–18 s | none | Workspace shrinks and fades as one layer, wordmark comes up, then fades to the empty first frame |

- `DURATION` is 18 s. `wrap(t)` maps any time into [0, 18): **18 s is
  the loop's first frame**, and anything not finite is 0.
- **Scene markers** are the four scene starts (`MARKERS`: 0, 4, 8, 12).
  They're the scrubber's four ticks and the only stops for ← and →. The
  outro is a segment but not a scene, so it has no marker. The track's
  own ends are the timeline's start and end.
- → goes to the next marker; from scene 4 or the outro it wraps to 0.
  ← goes to the current scene's start, or the one before within 0.3 s
  of a start (`BACK_GRACE`); before the first scene's grace it wraps to
  scene 4.
- `LOCKUP_FRAME` (17 s) is the logo fully shown. Reduced motion opens on
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
`render` taking three arguments, no gaps or overlaps, ending at 18 s.
**To replace a scene (Phase 4), replace its module**; the timeline and
player don't change. One scene becomes one Remotion `<Sequence>`; compact
mode becomes a prop.

- **`context`** (frozen, rebuilt by the player): `g` (the 2D context,
  already mapped to logical pixels), `colors` (the tokens, camelCase),
  `labels` (the words from `content.py`, deep-frozen), `images`
  (`wordmark`, tinted `fg-strong`, or `null` until loaded), and
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

## Scene 1: the workspace

A recreation of the editor's default dock (`layout.rs` `default_dock`,
pane names from `Pane::label`): Scene View | Animation | UI Designer,
with Console | Assets | Profiler below, and Explorer above
Properties | Terrain on the right. Tabs follow the dock's style: a quiet
bar on `app`, the active tab joined to its panel, the others `fg-weak`.
Colours are the site's tokens; their dark values are the editor's Dark
theme (`theme.rs`, tested).

1. 0.1 s: Scene View, Explorer and Properties rise in as kinetic type.
2. From 1.0 s: each word shrinks into its tab (Plus Jakarta handing
   over to Inter) as its panel springs from the word's box into the
   dock. The other tabs fade in as each word lands. The "Arena - Axcenity
   Editor" window (the editor's title format) and the docked Console
   arrive.
3. 1.45 s: the contents appear:
   - the viewport: a grid and a slowly turning block
   - the Explorer tree, with Pad selected
   - Properties (`properties.rs`): the Pad/Part header, "Filter
     properties", then Data, Appearance, Behavior and Part, with Part's
     real defaults (`class.rs`)
   - the Console (`output.rs`, `console.rs`): the real project-opened
     line from `app/session.rs`, a `select` command and the
     "Lua, or a command such as help" field
4. 1.75 s: a pointer comes in and drags the Properties tab out onto
   "Monitor 2" to the right (2.1–2.65 s). The window tears off to its own
   size, and its chrome and lifted shadow come up. Terrain takes its
   docked place.
5. 3.0–3.55 s: it drags the Console onto "Monitor 3" in the hero's empty
   upper left, and Assets takes over below the Scene View.
6. Each drop bobs once (`settle`, zero at the drop). The pointer drifts
   off and is gone by 3.95 s.

Drags are pure functions of time: the pointer eases from the tab's
docked grip to its floating grip, and the window follows it exactly, so
it lands on its final rectangle at release. The dock overlay's accent
highlight is left out: the accent is reserved for the site's fixed uses.

`drawWorkspace(context, size, build, clock)` draws it at any moment of
its build; `restingWorkspace` (build ≥ `SETTLED`) is what the
placeholder scenes and the outro draw, the block still turning with the
loop time.

## Compact mode (below 640 px)

The same timeline. The stage is the top of the hero (`COMPACT_TOP` 108 px,
`COMPACT_ASPECT` 0.62 of its width); the hero's CSS reserves the same
space above the copy (`.hero-copy`, tested). Only the Scene View and the
Explorer (their active tabs only), docked side by side, at larger type;
no pointer and nothing undocks.

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
  a range input (`step` 0.1 s, `aria-valuetext` such as "0:02 of 0:18,
  Scene 1, Workspace"). Space toggles anywhere in the controls; ← and →
  jump markers on the button, but **on the range they keep their native
  fine seeking**. The thumb stays where it's dragged (to 18 s shows 0 s).
- **Visibility of the controls:** they fade in on hover (behind the hover
  gate) or focus, and stay visible on touch screens and whenever the
  visitor has paused (so reduced motion's Play is always there).
- `data-state` (`playing`/`paused`), `data-motion` (`full`/`reduced`),
  `data-size` and `data-ready` (fonts and logo loaded) on the figure are
  for tests and debugging.

## Accessibility and fallbacks

- The canvas is `aria-hidden`. The figure is named by its caption
  ("Illustrative · editor recreation") and, once live, described by
  `#reel-description`: the workspace, the panels and the undocking
  (`MEDIA["reel"].alt`).
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
