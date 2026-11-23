// Scene 2 (4–8 s): the Toolbox.
//
// 1. The pointer presses the Assets pane's Toolbox button. The Toolbox opens
//    as a tab beside Assets (layout.rs), and the bottom dock springs taller.
// 2. It types "rock" into the search field and presses Search; "Searching…",
//    then the cards pop in one after another.
// 3. It drags the first card's picture onto the Pad in the Scene View. The
//    status line says it's downloading, the Console reports it, and the Pad
//    takes on the rock texture.
// 4. The pointer drifts off; the workspace holds with the results showing.
//
// Compact mode widens the Scene View over the Explorer and shows the Toolbox
// as a tab beside it, then the textured Pad, with no pointer. Like every
// scene it holds no state: a frame comes from (context, time, size) alone.

import { clamp, expoOut, lerp, progress, rect, spring } from "../easing.js";
import { BOTTOM_SHARE, innerOf, workspaceLayout } from "../drawing/layout.js";
import * as ui from "../drawing/editor.js";
import * as tb from "../drawing/toolbox.js";
import { REST, pointerPath, viewWorkspace } from "./workspace.js";

const START = 4;
const DURATION = 4;
/** The bottom dock's share while the Toolbox is open. */
const OPEN_SHARE = 0.58;

// When things happen, in seconds into the scene.
const T = Object.freeze({
  enter: 0.15,
  button: 0.45, // the Toolbox button is pressed
  open: 0.52, // the Toolbox tab opens
  field: 0.95, // the search field is clicked
  type: [1.05, 0.35], // "rock" typed
  search: 1.55, // Search pressed
  results: 1.8, // the cards start popping in
  grab: 2.2, // the pointer reaches the first card
  press: 2.28, // and picks up its picture
  drop: 3.0, // onto the Pad
  log: [3.08, 3.5], // the Console's two lines
  texture: 3.3, // the Pad takes the texture
  gone: Object.freeze([3.45, 3.9]),
  compactSwitch: 2.75, // compact mode: back to the Scene View
});

/** The bottom dock's share at `t`: it springs taller once the Toolbox opens. */
export function bottomShare(t) {
  return lerp(BOTTOM_SHARE, OPEN_SHARE, clamp(spring(t - T.open, 1.8, 0.8), 0, 1.2));
}

/** The Scene place's tabs in compact mode from here on: the Scene View and the Toolbox. */
export function compactTabs(labels) {
  return [labels.tabs.scene[0], labels.toolbox.button];
}

/** The Toolbox's search at `t`, as drawing/toolbox.js takes it. */
function searchState(t, labels) {
  const typed = Math.floor(progress(t, T.type[0], T.type[1]) * labels.toolbox.query.length);
  const editing = t >= T.field && t < T.search;
  return {
    typed,
    caret: editing && (t < T.type[0] + T.type[1] || Math.floor(t * 4) % 2 === 0),
    searchPressed: t >= T.search && t < T.search + 0.08,
    searching: t >= T.search + 0.04,
    results: t >= T.results ? t - T.results : -1,
    lifted: t >= T.press && t < T.drop ? 0 : -1,
    status: t >= T.drop ? expoOut(progress(t, T.drop, 0.2)) * (1 - progress(t, 3.65, 0.25)) : 0,
  };
}

/** The Console's new lines at `t`, each fading in as it arrives. */
function log(labels, t) {
  return labels.toolbox_log.map((line, index) => [...line, expoOut(progress(t, T.log[index], 0.3))]);
}

/** The drag's ghost at the pointer: the card's picture, small, and its name beside a download mark. */
function ghost(g, colors, labels, tip, u) {
  const [name, , pattern] = labels.toolbox.cards[0];
  const side = 30 * u;
  const picture = rect(tip.x + 8 * u, tip.y + 10 * u, side, side);
  g.save();
  g.globalAlpha *= 0.9 * tip.alpha;
  ui.shadow(g, colors, picture, u, 1);
  tb.picture(g, colors, picture, pattern, 1, u);
  g.font = ui.font(500, 11 * u, "Inter");
  const chip = rect(picture.x + side + 4 * u, picture.y + 4 * u, g.measureText(name).width + 28 * u, 20 * u);
  ui.fill(g, colors.elevated, chip);
  ui.outline(g, colors.lineStrong, chip);
  tb.downArrow(g, colors, chip.x + 10 * u, chip.y + chip.height / 2, u);
  ui.text(g, colors.fgStrong, name, chip.x + 19 * u, chip.y + chip.height / 2, ui.font(500, 11 * u, "Inter"));
  g.restore();
}

/** Where the Pad sits in the Scene View's content box (editor.js viewport). */
function padIn(box) {
  return { x: box.x + box.width / 2, y: box.y + box.height * 0.552 };
}

/** The workspace's view `t` seconds into the scene. */
export function toolboxView(context, size, t) {
  const { g, colors, labels } = context;
  const state = searchState(t, labels);
  const textured = expoOut(progress(t, T.texture, 0.5));

  if (size.compact) {
    const showing = t >= T.open && t < T.compactSwitch;
    const L = workspaceLayout(size, BOTTOM_SHARE, 1);
    return {
      ...REST,
      wide: expoOut(progress(t, 0, 0.7)),
      sceneTabs: t >= T.open ? compactTabs(labels) : null,
      sceneTab: showing ? 1 : 0,
      scene: showing ? (inner, box) => tb.toolbox(inner, colors, box, labels, L.u, state, true) : null,
      textured: expoOut(progress(t, T.compactSwitch + 0.2, 0.5)),
    };
  }

  const share = bottomShare(t);
  const L = workspaceLayout(size, share);
  const u = L.u;
  const open = t >= T.open;
  const bottomBox = innerOf(L.console, L.tabBar);
  const button = ui.toolboxButton(g, bottomBox, labels.toolbox.button, u);
  const layout = tb.toolboxLayout(g, bottomBox, labels, u);
  const centre = (box) => ({ x: box.x + box.width / 2, y: box.y + box.height / 2 });
  const pad = padIn(innerOf(L.scene, L.tabBar));
  const card = centre(layout.cards[0].picture);
  const field = { x: layout.field.x + 20 * u, y: layout.field.y + layout.field.height / 2 };
  const stop = (point, at) => ({ x: point.x, y: point.y, at });
  const tip = pointerPath(
    t,
    [
      stop({ x: L.stage.x + L.stage.width * 0.32, y: L.stage.y + L.stage.height + 60 * u }, T.enter),
      stop(centre(button), T.button),
      stop(centre(button), T.button + 0.1),
      stop(field, T.field),
      stop(field, T.field + 0.08),
      stop(centre(layout.search), T.search),
      stop(centre(layout.search), T.search + 0.12),
      stop(card, T.grab),
      stop(card, T.press),
      stop(pad, T.drop),
      stop({ x: pad.x + 40 * u, y: pad.y + 60 * u }, T.gone[1]),
    ],
    [
      [T.button, T.button + 0.1],
      [T.field, T.field + 0.07],
      [T.search, T.search + 0.08],
      [T.press, T.drop + 0.03],
    ],
    T.gone
  );

  return {
    ...REST,
    bottom: share,
    textured,
    bottomTabs: open ? [labels.tabs.console[1], labels.toolbox.button, labels.tabs.console[2]] : null,
    bottomTab: open ? 1 : 0,
    bottomContent: open ? (inner, box) => tb.toolbox(inner, colors, box, labels, u, state) : null,
    assetsPressed: t >= T.button && t < T.button + 0.1,
    log: log(labels, t),
    pointer: tip,
    over: tip && t >= T.press && t < T.drop ? (inner) => ghost(inner, colors, labels, tip, u) : null,
  };
}

/** How the scene leaves the workspace: the next scene starts from exactly this. */
export function toolboxEnd(context, size) {
  return { ...toolboxView(context, size, DURATION), pointer: null, over: null };
}

export default Object.freeze({
  id: "toolbox",
  start: START,
  duration: DURATION,
  render(context, time, size) {
    viewWorkspace(context, size, START + time, toolboxView(context, size, time));
  },
});
