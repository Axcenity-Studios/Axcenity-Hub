# Home direction — prototype outcome

Prototype: [home-direction.html](home-direction.html) (throwaway; three variants).
Question: what should the marketing Home look like (layout, hierarchy, reel framing)?

## Chosen: A · Cinematic

Full-bleed reel as the hero with the headline over its lower left; nav that
turns solid on scroll; sticky-scroll features (text scrolls left, one large
media stage swaps per pillar on the right); oversized outlined workflow
numerals; stat band; Toolbox banner; coming-soon community row; giant
final CTA; four-column footer.

**Why:** the user felt it best captures the site and how they want it
built: the cinematic scale and the motion (expo-out reveals, rotating
headline, sticky swap).

## Fixes to carry into the real build

1. **Reel/terrain loop is too short and not seamless.** The placeholder
   rises, collapses and restarts every 8 s with a visible reset. Make the
   ambient terrain loop longer and truly continuous (e.g. a camera
   drifting forward over endlessly tiling terrain, or a periodic function
   whose first and last frames match), with no snap back to flat.
2. **Images look grainy and distorted.** The engine's renders are 480×270
   test references, upscaled. Replace them with high-resolution captures or
   crisp recreations (source decided separately); never upscale the
   480×270 references in production.
3. **Workspace (editor) media is static and doesn't look like the engine.**
   The docs diagram (`editor-layout.png`) is a labelled mock-up. Replace it
   with an animated recreation built from the real editor UI code
   (`crates/editor-kit/src/theme.rs`, panel names and layout in
   `crates/editor/`): panels docking and undocking with expo-out springs,
   matching the reel's Scene 1.
4. **Rotating headline jumps between one and two lines.** "Ray trace in
   real time." wraps where the other phrases don't, so the layout shifts.
   Reserve the height of the longest phrase (or keep every phrase to one
   line at each breakpoint) and animate within that fixed box, so nothing
   below moves.

## Also decided

- **Accent: engine blue** `#19A0FF` (`#0B67B8` on light), the editor's
  selection colour. Only on the primary button, the reel's progress and scan
  line, and the badge dot. Everything else stays monochrome.
- **Feature media: mixed.** Editor and Blocks + Luau slots are animated
  recreations built from the editor's UI code. Renderer and Terrain slots
  use real high-resolution captures from a purpose-built showcase scene in
  the engine; until captured, they show crisp drawn stand-ins, never the
  480×270 references.
- **Captures (2026-11-23):** `~/Projects/Axcenity Projects/Showcase/captures/`.
  Use `renderer-2560x1440.png` (RT on) and `renderer-graybox-2560x1440.png`
  (same camera, Low, no RT) for the Renderer slot and the Scene 2 wipe.
  **Do not use `terrain-2560x1440.png`:** the user rejected it because its
  stylised trees and flat-colour ground don't represent the terrain
  toolkit. The Terrain slot keeps a drawn stand-in until a better capture
  exists.
