// Scene 4 (12–16 s): the renderer.
//
// 1. The bottom dock gives the Scene View more room, and the Scene View cuts
//    from the Pad to the Showcase-Renderer room blocked out in grey: walls
//    first, then the plinths, the slab, the cylinder and the sphere rising
//    from the floor.
// 2. A scan line in the accent sweeps across, leaving the ray-traced capture
//    of the same room behind it. The camera pushes in slowly the whole time.
// 3. It holds on the lit room.
//
// Compact mode does the same in its widened Scene View. The capture is drawn
// only once it has loaded; until then the grey room stays.

import { clamp, easeInOut, expoOut, lerp, progress, spring } from "../easing.js";
import { workspaceLayout } from "../drawing/layout.js";
import * as ui from "../drawing/editor.js";
import * as renderer from "../drawing/renderer.js";
import { viewWorkspace } from "./workspace.js";
import { animationEnd } from "./animation.js";

const START = 12;
const DURATION = 4;
/** The bottom dock's share while the room is on show. */
const SHOW_SHARE = 0.14;

const T = Object.freeze({
  cut: [0.05, 0.35], // the Pad fades into the grey room
  build: 0.15, // the room starts blocking out
  sweep: [1.3, 1.4], // the scan line crosses
});

/** How far the camera has pushed in at `t` (1 is the capture's own framing). */
function push(t) {
  return lerp(1, 1.07, easeInOut(progress(t, 0, DURATION)));
}

/** The Scene View's content at `t`. */
function sceneDrawer(context, u, clock, t) {
  const { colors, images } = context;
  const sweep = easeInOut(progress(t, T.sweep[0], T.sweep[1]));
  const pad = 1 - expoOut(progress(t, T.cut[0], T.cut[1]));
  return (g, box) => {
    renderer.wipe(g, colors, images.capture, box, u, push(t), t - T.build, sweep);
    if (pad <= 0) return;
    g.save();
    g.globalAlpha *= pad;
    ui.viewport(g, colors, box, u, clock, 1);
    g.restore();
  };
}

/** The workspace's view `t` seconds into the scene. */
export function rendererView(context, size, t) {
  const before = animationEnd(context, size);
  const clock = START + t;
  if (size.compact) {
    const L = workspaceLayout(size, before.bottom, 1);
    return { ...before, scene: sceneDrawer(context, L.u, clock, t) };
  }
  const share = lerp(before.bottom, SHOW_SHARE, clamp(spring(t - 0.05, 1.6, 0.85), 0, 1.2));
  const L = workspaceLayout(size, share);
  return { ...before, bottom: share, scene: sceneDrawer(context, L.u, clock, t) };
}

/** How the scene leaves the workspace: the lit room, held. */
export function rendererEnd(context, size) {
  return rendererView(context, size, DURATION);
}

export default Object.freeze({
  id: "renderer",
  start: START,
  duration: DURATION,
  render(context, time, size) {
    viewWorkspace(context, size, START + time, rendererView(context, size, time));
  },
});
