// The Community section's loop (10 s): a room blocked out in grey becomes the
// ray-traced capture of the same room, and back.
//
// 1. The Scene View holds the Showcase-Renderer room blocked out in grey: the
//    walls, the plinths, the slab, the cylinder and the sphere.
// 2. A scan line in the accent sweeps across, leaving the ray-traced capture
//    behind it.
// 3. It holds on the lit room, then the scan line sweeps back to the grey room.
//    The camera eases in and back out over the loop, so the frame is never empty
//    and the last frame is the first.
//
// The capture is drawn only once it has loaded; until then the grey room
// stays. Below 480 px wide only the tab bar's type grows. Like every loop it
// holds no state: a frame comes from (context, time, size) alone.

import { clamp, easeInOut, progress, rect } from "../easing.js";
import * as ui from "../drawing/editor.js";
import * as renderer from "../drawing/renderer.js";

const DURATION = 10;
/** The frame reduced motion shows: the lit room. */
const STILL = 4.5;
/** Below this width the tab bar's type grows to stay readable. */
const COMPACT_BELOW = 480;
/** How far the camera pushes in at the loop's middle (1 is the capture's own framing). */
const PUSH = 0.07;
/** Seconds into blocking out at which every shape has risen (drawing/renderer.js graybox). */
const BUILT = 2;

const T = Object.freeze({
  lit: Object.freeze([1.2, 1.6]), // the scan line crosses to the lit room
  grey: Object.freeze([6.6, 1.6]), // and back to the grey room
});

/** The camera's push at `t`: in and back out once a loop, still at both ends. */
function push(t) {
  return 1 + PUSH * Math.sin((Math.PI * t) / DURATION) ** 2;
}

function draw(context, time, size) {
  const { g, colors, labels, images } = context;
  const u = size.width < COMPACT_BELOW ? clamp(size.width / 400, 0.7, 1.1) : clamp(size.width / 760, 0.6, 1.3);
  const box = ui.panel(g, colors, rect(0, 0, size.width, size.height), labels.tabs.scene, 0, u, 24 * u);
  const sweep = easeInOut(progress(time, T.lit[0], T.lit[1])) * (1 - easeInOut(progress(time, T.grey[0], T.grey[1])));
  renderer.wipe(g, colors, images.capture, box, u, push(time), BUILT, sweep);
}

export default Object.freeze({
  id: "wipe",
  duration: DURATION,
  still: STILL,
  render(context, time, size) {
    draw(context, time, size);
  },
});
