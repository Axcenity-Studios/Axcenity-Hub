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
| `static/reel/canvas.js` | Pixel ratio (capped at 2), logical size, `fit`, `useLogicalPixels`, `readPalette`, `tint`, `FONTS` |
| `static/reel/scenes/*.js` | One module per segment: `workspace`, `renderer`, `world`, `logic`, `lockup` |
| `marketing/content.py` | `MEDIA["reel"]`: caption, description (its `alt`), provenance, the drawn words (`labels`); `REEL_CONTROLS` |

## The timeline

| Segment | Time | Marker | Now |
|---|---|---|---|
| `workspace` (Scene 1) | 0–4 s | 0 s | Kinetic type, panels spring into the window, Properties undocks |
| `renderer` (Scene 2) | 4–8 s | 4 s | The finished workspace (Phase 4: the graybox-to-lit wipe) |
| `world` (Scene 3) | 8–12 s | 8 s | The finished workspace (Phase 4: terrain and foliage) |
| `logic` (Scene 4) | 12–16 s | 12 s | The finished workspace (Phase 4: blocks and Luau) |
| `lockup` (outro) | 16–18 s | none | Workspace fades, wordmark comes up, then fades to the empty first frame |

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
  (`wordmark`, tinted `fg-strong`, or `null` until loaded).
- **`size`** (frozen): `width` and `height` in **logical (CSS) pixels**,
  and `compact` (width under 640). Scenes never see physical pixels.

### Determinism rules (tested)

- **Pure:** a frame depends only on `(context, time, size)`. No state
  at module level (`let`/`var`), and no `Math.random`, `Date`,
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

The panel names from `Pane::label` (`crates/editor/src/layout.rs`):
**Scene View**, **Explorer**, **Properties**, styled from the editor's
Dark theme tokens (`crates/editor-kit/src/theme.rs`, which the site's
dark tokens equal; tested) and its square 1px panels.

1. 0.1 s: the names rise in as big kinetic type, staggered.
2. From 1.2 s: each word shrinks into its panel's tab (Plus Jakarta
   handing over to Inter) while the panel springs from the word's box to
   its dock place; the "Axcenity Editor" window fades in around them.
3. 1.9 s: the viewport (grid and a slowly turning block), the Explorer
   tree and the Properties rows appear.
4. 2.5 s: Properties undocks onto "Floating · Monitor 2" with a spring
   and a shadow; the Explorer grows into the space it left.

`drawWorkspace(context, size, build, clock)` draws it at any moment of
its build; `restingWorkspace` (build ≥ `SETTLED`) is what the
placeholder scenes and the outro draw, the block still turning with the
loop time.

## Compact mode (below 640 px)

The same timeline. The stage is the top of the hero (`COMPACT_TOP` 108 px,
`COMPACT_ASPECT` 0.62 of its width); the hero's CSS reserves the same
space above the copy (`.hero-copy`, tested). Only the Scene View and the
Explorer, docked side by side, at larger type; nothing undocks.

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

- Keep a `MediaQueryList` reachable from something long-lived (the
  player reads `reduce` in `update()`): one held only by its own listener
  can be garbage-collected, and its change event never fires.
- Inner modules are imported without a version query, so a browser may
  keep an old scene after an edit until it revalidates; reload hard.
