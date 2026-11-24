// The closing call to action's loop (10 s): keying a Wave clip in the editor's
// Animation pane (its Clips & Rigging view).
//
// 1. The character stands in the preview beside an empty dope sheet.
// 2. A pointer turns Record on and poses the character's arm by its hand; at
//    each key time the playhead moves and a column of diamond keys pops into
//    the dope sheet (RightUpperArm, RightLowerArm, Spine, Head).
// 3. It presses Play and drifts off: the playhead runs the clip six times at
//    1.5×, the keys lighting as it passes, and the character waves.
// 4. The keys fade, leaving the empty clip the loop starts from.
//
// Below 480 px wide the pane shows its compact layout (preview, dope sheet,
// transport) and the keys set themselves, with no pointer. Like every loop it
// holds no state: a frame comes from (context, time, size) alone.

import { clamp, easeInOut, lerp, progress, rect } from "../easing.js";
import * as ui from "../drawing/editor.js";
import * as anim from "../drawing/animation.js";
import { pointerPath } from "../drawing/pointer.js";

const DURATION = 10;
/** The frame reduced motion shows: every key set, the character mid-wave. */
const STILL = 4.5;
const COMPACT_BELOW = 480;
/** Playback speed (the transport's rate). Six passes of the 1.2 s clip end where they began. */
const RATE = 1.5;
/** The character's idle is sin(seconds × 2.4); four whole breaths a loop keep the wrap seamless. */
const BREATHE = (4 * 2 * Math.PI) / 2.4 / DURATION;

const T = Object.freeze({
  enter: 0.6,
  record: 1.05, // Record is pressed
  keys: Object.freeze([1.3, 1.5, 1.7, 1.9, 2.1]), // each key column is set
  home: 2.2, // the playhead goes back to the start
  play: 2.45, // Play is pressed
  playing: Object.freeze([2.5, 7.3]),
  gone: Object.freeze([2.9, 3.4]),
  clear: Object.freeze([8.4, 0.8]), // the keys fade
});

/** The playhead (clip seconds) at `t`: stepping through the keys, back to 0, then playing. */
function playhead(t) {
  const times = anim.WAVE.times;
  if (t >= T.playing[0]) {
    return t < T.playing[1] ? ((t - T.playing[0]) * RATE) % anim.WAVE.length : 0;
  }
  if (t >= T.home) return lerp(anim.WAVE.length, 0, easeInOut(progress(t, T.home, 0.15)));
  for (let column = times.length - 1; column >= 1; column -= 1) {
    const at = T.keys[column];
    if (t >= at - 0.15) return lerp(times[column - 1], times[column], easeInOut(progress(t, at - 0.15, 0.15)));
  }
  return 0;
}

/** The pane at `t`; `fresh` is the empty clip the loop starts from. */
function paneState(t, fresh) {
  const breathe = t * BREATHE;
  if (fresh) return { playhead: 0, record: false, keyed: T.keys.map(() => -1), playing: false, pressed: null, breathe };
  return {
    playhead: playhead(t),
    record: t >= T.record + 0.03 && t < T.play + 0.03,
    keyed: T.keys.map((at) => t - at),
    playing: t >= T.playing[0] && t < T.playing[1],
    pressed: t >= T.record && t < T.record + 0.08 ? "record" : t >= T.play && t < T.play + 0.08 ? "play" : null,
    breathe,
  };
}

function draw(context, time, size) {
  const { g, colors, labels, layer } = context;
  const compact = size.width < COMPACT_BELOW;
  const u = compact ? clamp(size.width / 400, 0.7, 1.1) : clamp(size.width / 680, 0.6, 1.3);
  const tabBar = 24 * u;
  const box = ui.panel(g, colors, rect(0, 0, size.width, size.height), labels.tabs.scene, 1, u, tabBar);

  // The keyed clip over the empty one, fading out at the end of the loop.
  const keys = 1 - easeInOut(progress(time, T.clear[0], T.clear[1]));
  if (keys < 1) anim.animationPane(g, colors, box, labels, u, paneState(time, true), compact);
  if (keys > 0) {
    const draw = (inside) => anim.animationPane(inside.g, colors, box, labels, u, paneState(time, false), compact);
    if (keys < 1) layer(keys, draw);
    else draw(context);
  }
  if (compact) return;

  // The pointer: Record, the character's hand through each key, then Play.
  const layout = anim.animationLayout(g, box, labels, u);
  const hand = (clip) => anim.skeleton(layout.preview, anim.poseAt(clip), time * BREATHE).hand;
  const centre = (at) => ({ x: at.x + at.width / 2, y: at.y + at.height / 2 });
  const stop = (point, at) => ({ x: point.x, y: point.y, at });
  let tip;
  if (time >= T.keys[0] && time < T.keys[T.keys.length - 1]) {
    // Posing: the pointer holds the character's hand as it moves.
    const at = hand(playhead(time));
    tip = { x: at.x, y: at.y, pressed: true, alpha: 1 };
  } else {
    tip = pointerPath(
      time,
      [
        stop({ x: size.width * 0.3, y: size.height * 0.92 }, T.enter),
        stop(centre(layout.record), T.record),
        stop(centre(layout.record), T.record + 0.05),
        stop(hand(0), T.keys[0]),
        stop(hand(anim.WAVE.length), T.keys[T.keys.length - 1]),
        stop(centre(layout.play), T.play),
        stop(centre(layout.play), T.play + 0.12),
        stop({ x: centre(layout.play).x + 70 * u, y: centre(layout.play).y - 40 * u }, T.gone[1]),
      ],
      [
        [T.record, T.record + 0.08],
        [T.keys[0] - 0.02, T.keys[0]],
        [T.play, T.play + 0.08],
      ],
      T.gone
    );
  }
  if (!tip) return;
  g.save();
  g.globalAlpha *= tip.alpha;
  ui.pointer(g, colors, tip.x, tip.y, u, tip.pressed);
  g.restore();
}

export default Object.freeze({
  id: "animation",
  duration: DURATION,
  still: STILL,
  render(context, time, size) {
    draw(context, time, size);
  },
});
