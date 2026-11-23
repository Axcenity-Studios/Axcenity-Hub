// Scene 1 (0–4 s): the workspace.
//
// 1. The panel names (Scene View, Explorer, Properties) rise in as kinetic type.
// 2. Each word shrinks into its tab as its panel springs into the editor's
//    default dock, and the window, the other tabs and the Console arrive.
// 3. A pointer drags the Properties tab out onto a second monitor to the
//    right, then the Console onto a third to the left. The Terrain and Assets
//    tabs that shared their places take over, as in the editor's dock.
//
// Compact mode (phones) docks the Scene View and the Explorer only, with no
// pointer. Like every scene this module holds no state: a frame comes from
// (context, time, size) alone, in logical pixels, so seeking anywhere draws
// the same picture as playing up to it.

import { easeInOut, expoOut, lerp, lerpRect, progress, rect, spring } from "../easing.js";
import { bodyOf, workspaceLayout } from "../drawing/layout.js";
import * as ui from "../drawing/editor.js";

const START = 0;
const DURATION = 4;

// When things happen, in seconds into the scene.
const WORD_IN = 0.1; // the first word starts rising in
const WORD_STAGGER = 0.14;
const MORPH = 1.0; // the first word starts shrinking into its tab
const MORPH_STAGGER = 0.1;
const WINDOW_IN = 0.95; // the editor window fades in around the panels
const EXTRAS_IN = 1.3; // the Console's docked tabs
const CONTENT_IN = 1.45; // the tree, the viewport, the rows and the log
const POINTER_IN = 1.75;
// The two drags: when the pointer reaches the tab, presses, and lets go.
const DRAG_PROPERTIES = Object.freeze({ reach: 2.05, press: 2.1, release: 2.65 });
const DRAG_CONSOLE = Object.freeze({ reach: 2.95, press: 3.0, release: 3.55 });
const POINTER_OUT = 3.6; // it drifts off and fades
const POINTER_GONE = 3.95;
/** By this time into the build everything is at rest. */
export const SETTLED = 8;

/** A dropped window's little bob: zero at the drop, then a quick, fading wobble. */
function settle(seconds, u) {
  if (seconds <= 0) return 0;
  return 4 * u * Math.sin(2 * Math.PI * 3 * seconds) * Math.exp(-6 * seconds);
}

/** Where a panel's first tab is grabbed, from the panel's top left. Tabs sit at the left, so it's the same docked or floating. */
function grip(g, names, u, tabBar) {
  const first = ui.tabBoxes(g, rect(0, 0, 1000, tabBar), names, u, tabBar)[0];
  return { dx: first.x + first.width / 2, dy: tabBar / 2 };
}

/**
 * A panel being dragged from `docked` into `frame` (a whole window): where its
 * box is, how far its window chrome has come in, how lifted it looks, and
 * where the pointer holds its tab before and after.
 */
function dragged(t, drag, docked, frame, hold, L) {
  const body = bodyOf(frame, L.titleBar);
  const from = { x: docked.x + hold.dx, y: docked.y + hold.dy };
  const to = { x: body.x + hold.dx, y: body.y + hold.dy };
  const move = easeInOut(progress(t, drag.press, drag.release - drag.press));
  const tear = expoOut(progress(t, drag.press, 0.3));
  const at = { x: lerp(from.x, to.x, move), y: lerp(from.y, to.y, move) };
  const box = rect(
    at.x - hold.dx,
    at.y - hold.dy + settle(t - drag.release, L.u),
    lerp(docked.width, body.width, tear),
    lerp(docked.height, body.height, tear)
  );
  const lifted =
    t < drag.release
      ? 1 + expoOut(progress(t, drag.press, 0.2))
      : lerp(2, 1.3, expoOut(progress(t, drag.release, 0.4)));
  return { box, chrome: expoOut(progress(t, drag.press, 0.2)), lifted, from, to };
}

/** The pointer's tip, whether it's pressed and how visible it is; null while it's away. */
function pointerAt(t, start, properties, consoleDrag, u) {
  if (t < POINTER_IN || t >= POINTER_GONE) return null;
  const go = (a, b, from, to) => {
    const p = easeInOut(progress(t, from, to - from));
    return { x: lerp(a.x, b.x, p), y: lerp(a.y, b.y, p) };
  };
  const away = { x: consoleDrag.to.x + 30 * u, y: consoleDrag.to.y + 40 * u };
  let at;
  if (t < DRAG_PROPERTIES.press) {
    at = go(start, properties.from, POINTER_IN, DRAG_PROPERTIES.reach);
  } else if (t < DRAG_PROPERTIES.release) {
    at = go(properties.from, properties.to, DRAG_PROPERTIES.press, DRAG_PROPERTIES.release);
  } else if (t < DRAG_CONSOLE.press) {
    at = go(properties.to, consoleDrag.from, DRAG_PROPERTIES.release + 0.05, DRAG_CONSOLE.reach);
  } else if (t < DRAG_CONSOLE.release) {
    at = go(consoleDrag.from, consoleDrag.to, DRAG_CONSOLE.press, DRAG_CONSOLE.release);
  } else {
    at = go(consoleDrag.to, away, POINTER_OUT, POINTER_GONE);
  }
  const pressed =
    (t >= DRAG_PROPERTIES.press && t < DRAG_PROPERTIES.release + 0.04) ||
    (t >= DRAG_CONSOLE.press && t < DRAG_CONSOLE.release + 0.04);
  const alpha =
    expoOut(progress(t, POINTER_IN, 0.25)) * (1 - progress(t, POINTER_OUT, POINTER_GONE - POINTER_OUT));
  return { x: at.x, y: at.y, pressed, alpha };
}

/**
 * Draws the workspace `build` seconds into its build (SETTLED or more is at
 * rest), with the viewport's block turned to `clock` seconds. Later scenes call
 * it for the finished workspace. Pure: it draws from its arguments only.
 */
export function drawWorkspace(context, size, build, clock) {
  const { g, colors, labels } = context;
  const t = Math.min(build, SETTLED);
  const L = workspaceLayout(size);
  const { u, tabBar, titleBar } = L;
  const compact = size.compact;
  const tabs = labels.tabs;
  const base = g.globalAlpha;

  // ---- The kinetic type: big, stacked, left aligned in the stage ----
  const names = compact
    ? [tabs.scene[0], tabs.explorer[0]]
    : [tabs.scene[0], tabs.explorer[0], tabs.properties[0]];
  const big = compact
    ? Math.min(L.stage.width * 0.13, 44)
    : Math.min(L.stage.height * 0.15, L.stage.width * 0.09);
  const lineHeight = big * 1.08;
  const firstLine = L.stage.y + L.stage.height / 2 - (lineHeight * (names.length - 1)) / 2;
  const left = L.stage.x + L.stage.width * 0.06;
  const homes = compact ? [L.scene, L.explorer] : [L.scene, L.explorer, L.properties];
  // Each docked place's tabs; compact mode shows only the active one.
  const tabSets = compact ? [[tabs.scene[0]], [tabs.explorer[0]]] : [tabs.scene, tabs.explorer, tabs.properties];
  const words = names.map((name, index) => {
    const y = firstLine + index * lineHeight;
    g.font = ui.font(800, big, "Plus Jakarta Sans");
    const width = g.measureText(name).width;
    const morphAt = MORPH + index * MORPH_STAGGER;
    return {
      name,
      tabs: tabSets[index],
      start: { x: left, y },
      box: lerpRect(rect(left, y - big / 2, width, big), homes[index], spring(t - morphAt, 2, 0.6)),
      shown: expoOut(progress(t, morphAt, 0.3)),
      shrink: expoOut(progress(t, morphAt, 0.8)),
      rise: expoOut(progress(t, WORD_IN + index * WORD_STAGGER, 0.7)),
    };
  });

  const windowAlpha = expoOut(progress(t, WINDOW_IN, 0.5));
  const extrasAlpha = expoOut(progress(t, EXTRAS_IN, 0.4));
  const contentAlpha = expoOut(progress(t, CONTENT_IN, 0.5));
  const contents = {
    scene: (box) => ui.viewport(g, colors, box, u, clock),
    explorer: (box) => ui.explorer(g, colors, box, labels, u),
    properties: (box) => ui.properties(g, colors, box, labels, u),
    console: (box) => ui.consoleLog(g, colors, box, labels, u),
    terrain: (box) => ui.terrain(g, colors, box, labels, u),
    assets: (box) => ui.assets(g, colors, box, labels, u),
  };
  const drawPanel = (box, tabNames, content, alpha, landed = 1) => {
    if (alpha <= 0) return;
    g.globalAlpha = base * alpha;
    // Until its word has landed, a panel leaves its active label to the word and
    // brings its other tabs in as the word arrives.
    const inner = ui.panel(g, colors, box, tabNames, 0, u, tabBar, landed >= 1, progress(landed, 0.6, 0.4));
    if (contentAlpha > 0) {
      g.save();
      g.globalAlpha = base * alpha * contentAlpha;
      ui.clipTo(g, inner);
      contents[content](inner);
      g.restore();
    }
  };
  const drawWindow = (box, title, lifted, chrome) => {
    if (chrome <= 0) return;
    const frame = rect(box.x, box.y - titleBar, box.width, box.height + titleBar);
    g.globalAlpha = base * chrome;
    ui.shadow(g, colors, frame, u, lifted);
    g.globalAlpha = base * chrome;
    ui.windowChrome(g, colors, frame, title, u, titleBar);
  };

  // ---- The editor window ----
  if (windowAlpha > 0) {
    g.globalAlpha = base * windowAlpha;
    ui.shadow(g, colors, L.main, u, 1);
    g.globalAlpha = base * windowAlpha;
    ui.windowChrome(g, colors, L.main, labels.window, u, titleBar);
  }

  // ---- The docked panels, then the floating windows (the latest dragged on top) ----
  drawPanel(words[0].box, words[0].tabs, "scene", words[0].shown, words[0].shrink);
  drawPanel(words[1].box, words[1].tabs, "explorer", words[1].shown, words[1].shrink);

  let propertiesDrag = null;
  let consoleDrag = null;
  if (!compact) {
    const props = words[2];
    propertiesDrag = dragged(t, DRAG_PROPERTIES, props.box, L.propertiesWindow, grip(g, tabs.properties, u, tabBar), L);
    consoleDrag = dragged(t, DRAG_CONSOLE, L.console, L.consoleWindow, grip(g, tabs.console, u, tabBar), L);
    // What stays docked: Properties | Terrain until the drag, then Terrain alone (and the same below).
    if (t < DRAG_PROPERTIES.press) {
      drawPanel(props.box, props.tabs, "properties", props.shown, props.shrink);
    } else {
      drawPanel(L.properties, tabs.properties.slice(1), "terrain", 1);
    }
    if (t < DRAG_CONSOLE.press) {
      drawPanel(L.console, tabs.console, "console", extrasAlpha);
    } else {
      drawPanel(L.console, tabs.console.slice(1), "assets", 1);
    }
    if (t >= DRAG_PROPERTIES.press) {
      drawWindow(propertiesDrag.box, labels.monitors.properties, propertiesDrag.lifted, propertiesDrag.chrome);
      drawPanel(propertiesDrag.box, [tabs.properties[0]], "properties", 1);
    }
    if (t >= DRAG_CONSOLE.press) {
      drawWindow(consoleDrag.box, labels.monitors.console, consoleDrag.lifted, consoleDrag.chrome);
      drawPanel(consoleDrag.box, [tabs.console[0]], "console", 1);
    }
  }

  // ---- The words, while they're still big or landing in their tabs ----
  for (const word of words) {
    if (word.rise <= 0 || word.shrink >= 1) continue;
    const tab = ui.tabLabelAt(g, word.box, word.tabs, 0, u, tabBar);
    const px = lerp(big, ui.TAB_FONT * u, word.shrink);
    const x = lerp(word.start.x, tab.x, word.shrink);
    const y = lerp(word.start.y + (1 - word.rise) * big * 0.4, tab.y, word.shrink);
    // The display face hands over to the editor's UI face (Inter) as the word lands.
    const handover = progress(word.shrink, 0.6, 0.4);
    g.fillStyle = colors.fgStrong;
    g.textAlign = "left";
    g.textBaseline = "middle";
    if (handover < 1) {
      g.globalAlpha = base * word.rise * (1 - handover);
      g.font = ui.font(800, px, "Plus Jakarta Sans");
      g.fillText(word.name, x, y);
    }
    if (handover > 0) {
      g.globalAlpha = base * word.rise * handover;
      g.font = ui.font(600, px, "Inter");
      g.fillText(word.name, x, y);
    }
  }

  // ---- The pointer ----
  if (!compact) {
    const start = { x: L.stage.x + L.stage.width * 0.55, y: L.stage.y + L.stage.height + 70 * u };
    const tip = pointerAt(t, start, propertiesDrag, consoleDrag, u);
    if (tip && tip.alpha > 0) {
      g.globalAlpha = base * tip.alpha;
      ui.pointer(g, colors, tip.x, tip.y, u, tip.pressed);
    }
  }
  g.globalAlpha = base;
}

/** The finished workspace, for the scenes that follow until they have their own pictures. */
export function restingWorkspace(context, size, clock) {
  drawWorkspace(context, size, SETTLED, clock);
}

export default Object.freeze({
  id: "workspace",
  start: START,
  duration: DURATION,
  render(context, time, size) {
    drawWorkspace(context, size, time, START + time);
  },
});
