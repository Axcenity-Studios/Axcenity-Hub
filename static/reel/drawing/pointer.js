// The pointer's path through a loop: it eases from stop to stop, dwelling where
// a stop repeats, and fades in before its first stop and out when it leaves.
// Stops are computed from the current frame's layout, so a target that moves
// carries the pointer with it.
//
// Every function draws or computes from its arguments alone.

import { easeInOut, expoOut, lerp, progress } from "../easing.js";

/**
 * Where the pointer is, between `stops` ({ x, y, at }, in time order): it
 * eases from each to the next, arriving at its time. `presses` are spans
 * [from, to] when it's held down. It fades in over the 0.25 s before the first
 * stop's time, and out across `gone` ([from, to]). Null when it's away.
 */
export function pointerPath(t, stops, presses = [], gone = null) {
  const first = stops[0];
  const last = stops[stops.length - 1];
  if (t < first.at - 0.25 || (gone && t >= gone[1])) return null;
  let at = { x: first.x, y: first.y };
  if (t >= last.at) at = { x: last.x, y: last.y };
  else {
    for (let index = 1; index < stops.length; index += 1) {
      const from = stops[index - 1];
      const to = stops[index];
      if (t < to.at) {
        const p = easeInOut(progress(t, from.at, to.at - from.at));
        at = { x: lerp(from.x, to.x, p), y: lerp(from.y, to.y, p) };
        break;
      }
    }
  }
  const pressed = presses.some(([from, to]) => t >= from && t < to);
  const fadeIn = expoOut(progress(t, first.at - 0.25, 0.25));
  const fadeOut = gone ? 1 - progress(t, gone[0], gone[1] - gone[0]) : 1;
  return { x: at.x, y: at.y, pressed, alpha: fadeIn * fadeOut };
}
