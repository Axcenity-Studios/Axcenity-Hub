# The canvas kit: loops, their contract and determinism

The Home's animated recreations are canvas loops: native ES modules in
`static/reel/`, no dependencies. What each loop shows, where it sits,
its fallback and its playback are in [media.md](media.md); this page is
the kit they're built from and the rules every loop follows.
`tests/test_canvas.py` checks the rules as written; the colour rules
are in [theme.md](theme.md).

## Files

| Path | Holds |
|---|---|
| `static/reel/loops/main.js` | Entry: mounts each `[data-loop]` figure with the player and its loop; on any failure the drawing stays |
| `static/reel/loops/player.js` | One clock per figure: drawing, the pause button, visibility, reduced motion, theme, resize, `loop-seek`, and loading a capture (`data-capture`) |
| `static/reel/loops/<name>.js` | The loops: `editor`, `terrain`, `logic` (the pillars), `toolbox`, `wipe`, `animation` (the sections) |
| `static/reel/canvas.js` | Pixel ratio (capped at 2), logical size (the layout box, so transforms don't shrink it), `fit`, `useLogicalPixels`, `groupLayer`, `readPalette`, `FONTS` |
| `static/reel/easing.js` | Pure helpers: `clamp`, `lerp`, `progress`, `expoOut`, `easeInOut`, `spring` (closed form), `lerpRect`, `rect` |
| `static/reel/drawing/editor.js` | The editor's pieces: windows, tab bars, panels, the viewport (the Pad and its rock texture), Explorer, Properties, Console, Terrain and Assets panes, buttons, chips, the pointer |
| `static/reel/drawing/pointer.js` | `pointerPath(t, stops, presses, gone)`: the pointer easing from stop to stop |
| `static/reel/drawing/toolbox.js`, `animation.js`, `renderer.js` | The Toolbox pane and its cards; the Animation pane (the Wave clip, the mannequin, the dope sheet, the transport); the renderer wipe (the drawn grey room, the capture, the scan line) |
| `static/reel/drawing/blocks.js`, `stacks.js`, `code.js`, `terrain.js` | The block editor's Graph view (nodes, pins, wires) and Blocks view (hats, statement blocks, menus, typed fields, reporters, the dot grid), typed Luau, and the heightfield, brush and plants with the Terrain and Scatter panes |

## The loop contract

```js
export default Object.freeze({
  id: "toolbox",        // its name in content.LOOPS and main.js
  duration: DURATION,   // seconds, 8 to 16; the last frame flows into the first
  still: STILL,         // the frame reduced motion shows
  render(context, time, size) { … },
});
```

Each loop declares `const COMPACT_BELOW = 480;` and lays itself out
differently below it (tested).

- **`context`** (frozen, rebuilt by the player): `g` (the 2D context,
  already mapped to logical pixels), `colors` (the tokens, camelCase),
  `labels` (the loop's words from `content.py`, deep-frozen), `images`
  (`capture`: the picture named by the figure's `data-capture`, `null`
  until loaded), and `layer(alpha, draw)`: draws `draw(layerContext)`
  into an offscreen buffer and composites it at `alpha` as one picture.
  Use it to fade anything made of overlapping pieces; drawing each piece
  at partial alpha lets the ones beneath show through.
- **`size`** (frozen): `width` and `height` in **logical (CSS) pixels**.

## Determinism rules (tested)

- **Pure:** a frame depends only on `(context, time, size)`. These rules
  cover `loops/` (but `main.js` and `player.js`) and `drawing/`. No
  state at module level (`let`/`var`), and no `Math.random`, `Date`,
  `performance`, `requestAnimationFrame`, `window`, `document`,
  `devicePixelRatio` or `canvas.width`/`height`.
- **Seek anywhere:** a frame never depends on the frames before it.
  Springs are closed-form (`spring(seconds)`), and every transition is
  computed from `time`.
- **Seamless wrap (tested in Chromium):** the last frame is the first.
  Anything that runs on its own clock must turn whole periods a loop:
  the viewport turns the Pad `0.35` rad per clock second, so a loop
  passes it `time × SPIN` with half a turn per loop (the Pad is square);
  the mannequin breathes on `sin(t × 2.4)`, so the Animation loop passes
  four whole breaths. An end state fades back to the start, and once the
  fade is done the start is drawn directly, not through `layer()` (the
  buffer's resampling differs by a few pixels).
- **Logical pixels:** the player sets `g.setTransform(canvas.width /
  size.width, …)` before each frame. Avoid `shadowBlur` and `filter`
  blur (they work in device pixels); shadows are stacked translucent
  rectangles.
- **Colours** come only from the tokens (`canvas.js` `TOKENS`); no hex,
  `rgb()` or `hsl()` in any kit file. Only the renderer wipe's scan line
  uses the accent. Every pair drawn is a tested contrast pair.
- The player wraps each `render` in `save()`/`restore()`; loops may set
  any state on `g`.

## Fidelity

The editor is drawn from its sources: the default dock and pane names
(`layout.rs`), its Dark theme (the site's dark tokens are its
`theme.rs` values, tested), Properties for a Part, the Console's
messages, the Toolbox's tabs, the Animation pane's views and bones,
and the block editor: a script's Code / Blocks / Graph bar, each block's
rows as `block_editor.rs` `sections()` lays them out, at its sizes, in
its category colours with Increase contrast (icons are drawn stand-ins
for its icon font).
Each loop's `provenance` names the files it follows. The pointer, the
terrain brush ring and the dock's drop preview are drawn in ink, not
the editor's accent.

## Gotchas

- Every font a loop draws with must be in `canvas.js` `FONTS` (tested):
  a face drawn before it loads paints in a fallback on its first frame,
  so the same moment would look different twice.
- The canvas reads every token at runtime, so `source.css` uses
  `@theme static` (Tailwind otherwise drops a token no utility uses, and
  an empty colour silently keeps the previous fill).
- Keep a `MediaQueryList` reachable from something long-lived (the
  player reads `reduce` in `update()`): one held only by its own
  listener can be garbage-collected, and its change event never fires.
- Inner modules are imported without a version query, so a browser may
  keep an old loop after an edit until it revalidates; reload hard.
