# The reel's scenes

What each of the showcase reel's scenes shows, and how they hand the
workspace on. The engine, the contract and playback are in
[reel.md](reel.md). Everything here is drawn from the engine's sources;
each scene module's header lists its steps, and the provenance is in
`MEDIA["reel"].provenance`.

## Scene 1 (0–4 s): the workspace

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

`drawWorkspace(context, size, build, clock, view)` draws it at any
moment of its build; past `SETTLED` it's the finished workspace that the
later scenes change through `view` (below), the block still turning with
the loop time.

## The view chain (Scenes 2–6)

The later scenes don't redraw the editor: they draw Scene 1's finished
workspace with a **view** (`REST` in `scenes/workspace.js`, copied and
changed): the bottom dock's share (`bottom`), compact widening (`wide`),
each place's tabs and active tab, drawers that replace a place's content
(`scene`, `bottomContent`, `side`), the Pad's texture, new Console lines
(`log`, each with its alpha), the pointer and a drag's ghost (`over`).
A drawer is called with the `g` to draw with and the box to fill, so it
works inside a layer too. `viewWorkspace(context, size, clock, view)`
draws it.

- **Each scene starts where the last one ended.** Every scene exports
  its end view (`toolboxEnd`, `animationEnd`, `rendererEnd`, `worldEnd`,
  `logicEnd`), and the next scene builds on it (`{ ...before, … }`), so
  a change to one scene's end moves the next one's start. The outro
  draws `logicEnd`.
- **The pointer** (`pointerPath(t, stops, presses, gone)`) eases from
  stop to stop, each `{ x, y, at }`; a repeated stop is a dwell. Stops
  are computed from the current frame's layout, so a target that moves
  (a split springing) carries the pointer with it. While it holds
  something that moves (the character's hand, a brush, a wire's loose
  end) the scene places it on that thing directly.
- **Splits move by springs** from wherever the last scene left them
  (`lerp(before.bottom, target, spring(t))`); spring(0) is 0, so there's
  no jump at a scene's start.

## Scene 2 (4–8 s): the Toolbox

The pointer presses the Assets pane's **Toolbox** button; the Toolbox
opens as a tab beside Assets (`layout.rs`) and the bottom dock springs to
58 %. It types "rock" into "Search materials", presses Search
("Searching…"), and the cards pop in. It drags the first card's picture
(a ghost with its name) onto the Pad: the status line reads "Downloading
Rock 030…" with Cancel, the Console prints the download and "Saved Rock
030 (CC0) in assets/textures/Rock030." (`app/toolbox.rs`, `install.rs`),
and the Pad takes on a rock texture. The card pictures are drawn
patterns, not thumbnails; the names are illustrative.

## Scene 3 (8–12 s): animation

The dock settles back as the pointer opens the **Animation** tab:
Clips & Rigging, with Record, Show Bones and "Preview on Character". It
turns Record on ("Recording: moving something in the preview sets a key
at … s") and holds the character's hand while the playhead steps through
the Wave clip's five key times, a column of diamonds popping in at each
(RightUpperArm, RightLowerArm, Spine, Head · Bone). Play runs the 1.2 s
clip twice at 1.5×, the keys under the playhead lighting, and the
character waves; then the pointer clicks back to the Scene View. The
character is the humanoid's skeleton (`rig.py`) as a mannequin; the
editor's red playhead and accent key are in ink here.

## Scene 4 (12–16 s): the renderer

The Scene View gets more room and cuts from the Pad to the
Showcase-Renderer room **blocked out in grey**: walls first, then the
plinths, slab, cylinder and sphere rising in turn. A scan line in the
accent sweeps across it (1.3–2.7 s), leaving the **ray-traced capture**
behind it, and holds. The camera pushes in to 1.07× throughout. The grey
room is drawn over the capture's own layout (its 1280 × 720 pixel
space), as no graybox capture exists yet. The capture is the 1920 px
WebP derivative; it's drawn at most ~850 CSS px wide, so it's never
upscaled (tested). Until it loads, the grey room stays.

## Scene 5 (16–20 s): the world

The Scene View cuts to flat ground. The pointer picks **Raise / Lower**
in the docked Terrain pane and brushes across the ground: a hill rises
under each of five stops. The **Scatter** pane opens beside Terrain; the
pointer presses Paint (now Stop painting) and paints a path over the
hills, plants growing in behind the brush. The Properties window floats
over the right of this column, so the pointer aims at the left of its
controls. The ground, brush and plants are the World loop's drawings.

## Scene 6 (20–24 s): logic

A **Script** tab opens beside the Scene View's tabs in its Graph view
(Code, Blocks, Graph). When Touched (for the Pad) and Spawn Decal pop
in; the pointer drags a wire from one's exec pin to the other's
(`blocks.pinAt`, `wirePoint`); the Luau types out below; a pulse runs
along the wire and Spawn Decal lights up. The nodes and the Luau are the
Logic loop's (`LOGIC_LABELS`).

## The outro (24–26 s)

The Logic scene's last frame shrinks and fades as one layer, the
wordmark comes up (fully shown at 25 s, `LOCKUP_FRAME`) and fades to the
empty page: Scene 1's first frame.
