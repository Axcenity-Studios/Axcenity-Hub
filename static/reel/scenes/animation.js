// Scene 3 (8–12 s): animation.
//
// 1. The bottom dock settles back as the pointer clicks the Animation tab
//    beside the Scene View: the Clips & Rigging view, with the character in
//    its preview and an empty Wave clip.
// 2. It turns Record on and poses the character's arm by its hand; at each
//    key time the playhead moves and a column of diamond keys pops into the
//    dope sheet (RightUpperArm, RightLowerArm, Spine, Head).
// 3. It presses Play: the playhead runs the clip twice at 1.5×, the keys
//    lighting as it passes, and the character waves.
// 4. It clicks the Scene View tab and drifts off.
//
// Compact mode shows the Animation tab beside the Scene View and the Toolbox,
// at its compact layout (preview, dope sheet, transport), with no pointer.

import { clamp, easeInOut, expoOut, lerp, progress, spring } from "../easing.js";
import { BOTTOM_SHARE, innerOf, workspaceLayout } from "../drawing/layout.js";
import * as ui from "../drawing/editor.js";
import * as anim from "../drawing/animation.js";
import { pointerPath, viewWorkspace } from "./workspace.js";
import { compactTabs as toolboxTabs, toolboxEnd } from "./toolbox.js";

const START = 8;
const DURATION = 4;
/** Playback speed (the transport's rate). Two passes of the 1.2 s clip end where they began. */
const RATE = 1.5;

const T = Object.freeze({
  enter: 0.2,
  tab: 0.5, // the Animation tab is clicked
  record: 0.85, // Record is pressed
  keys: Object.freeze([1.0, 1.17, 1.34, 1.51, 1.68]), // each key column is set
  home: 1.75, // the playhead goes back to the start
  play: 1.95, // Play is pressed
  playing: Object.freeze([2.0, 3.6]),
  back: 3.5, // the Scene View tab is clicked
  gone: Object.freeze([3.62, 3.95]),
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

/** How much of the Animation pane shows over the Scene View: in after the click, out after the click back. */
function paneShown(t) {
  return expoOut(progress(t, T.tab + 0.03, 0.15)) * (1 - expoOut(progress(t, T.back + 0.03, 0.17)));
}

function paneState(t) {
  return {
    playhead: playhead(t),
    record: t >= T.record + 0.03 && t < T.play + 0.03,
    keyed: T.keys.map((at) => t - at),
    playing: t >= T.playing[0] && t < T.playing[1],
    pressed: t >= T.record && t < T.record + 0.08 ? "record" : t >= T.play && t < T.play + 0.08 ? "play" : null,
    breathe: START + t,
  };
}

/** The Scene place's content: the Scene View under the Animation pane as it comes and goes. */
function sceneDrawer(context, u, clock, t, compact) {
  const { colors, labels } = context;
  const shown = paneShown(t);
  return (g, box) => {
    if (shown < 1) ui.viewport(g, colors, box, u, clock, 1);
    if (shown <= 0) return;
    g.save();
    g.globalAlpha *= shown;
    g.translate(0, (1 - shown) * 8 * u);
    anim.animationPane(g, colors, box, labels, u, paneState(t), compact);
    g.restore();
  };
}

/** The workspace's view `t` seconds into the scene. */
export function animationView(context, size, t) {
  const { g, labels } = context;
  const before = toolboxEnd(context, size);
  const clock = START + t;
  const onTab = t >= T.tab + 0.03 && t < T.back + 0.03;

  if (size.compact) {
    const L = workspaceLayout(size, BOTTOM_SHARE, 1);
    return {
      ...before,
      sceneTabs: t >= T.tab - 0.15 ? compactTabs(labels) : before.sceneTabs,
      sceneTab: onTab ? 2 : 0,
      scene: sceneDrawer(context, L.u, clock, t, true),
    };
  }

  const share = lerp(before.bottom, BOTTOM_SHARE, clamp(spring(t, 1.8, 0.8), 0, 1.2));
  const L = workspaceLayout(size, share);
  const u = L.u;
  const sceneBox = innerOf(L.scene, L.tabBar);
  const tabs = ui.tabBoxes(g, L.scene, labels.tabs.scene, u, L.tabBar);
  const centre = (box) => ({ x: box.x + box.width / 2, y: box.y + box.height / 2 });
  const layout = anim.animationLayout(g, sceneBox, labels, u);
  const hand = (time) => anim.skeleton(layout.preview, anim.poseAt(time), START + t).hand;
  const stop = (point, at) => ({ x: point.x, y: point.y, at });
  let tip;
  if (t >= T.keys[0] && t < T.keys[T.keys.length - 1]) {
    // Posing: the pointer holds the character's hand as it moves.
    const at = hand(playhead(t));
    tip = { x: at.x, y: at.y, pressed: true, alpha: 1 };
  } else {
    tip = pointerPath(
      t,
      [
        stop({ x: L.stage.x + L.stage.width * 0.2, y: L.stage.y + L.stage.height + 50 * u }, T.enter),
        stop(centre(tabs[1]), T.tab),
        stop(centre(tabs[1]), T.tab + 0.1),
        stop(centre(layout.record), T.record),
        stop(centre(layout.record), T.record + 0.05),
        stop(hand(0), T.keys[0]),
        stop(hand(anim.WAVE.length), T.keys[T.keys.length - 1]),
        stop(centre(layout.play), T.play),
        stop(centre(layout.play), T.play + 0.15),
        stop(centre(tabs[0]), T.back),
        stop(centre(tabs[0]), T.back + 0.08),
        stop({ x: centre(tabs[0]).x - 30 * u, y: centre(tabs[0]).y + 60 * u }, T.gone[1]),
      ],
      [
        [T.tab, T.tab + 0.08],
        [T.record, T.record + 0.08],
        [T.keys[0] - 0.02, T.keys[0]],
        [T.play, T.play + 0.08],
        [T.back, T.back + 0.08],
      ],
      T.gone
    );
  }
  return {
    ...before,
    bottom: share,
    sceneTab: onTab ? 1 : 0,
    scene: sceneDrawer(context, u, clock, t, false),
    pointer: tip,
  };
}

/** The Scene place's compact tabs from here on: the Toolbox's, then Animation. */
export function compactTabs(labels) {
  return [...toolboxTabs(labels), labels.tabs.scene[1]];
}

/** How the scene leaves the workspace: back on the Scene View, the dock at its usual split. */
export function animationEnd(context, size) {
  return { ...animationView(context, size, DURATION), scene: null, pointer: null };
}

export default Object.freeze({
  id: "animation",
  start: START,
  duration: DURATION,
  render(context, time, size) {
    viewWorkspace(context, size, START + time, animationView(context, size, time));
  },
});
