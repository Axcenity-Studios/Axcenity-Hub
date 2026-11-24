// The Editor pillar's loop (12 s): the editor's docking, on two monitors.
//
// 1. The editor rests in its default dock (layout.rs default_dock).
// 2. A pointer drags the Console tab onto the right half of the Scene View;
//    the drop preview shows where it lands, and the Scene View splits.
// 3. It drags the Properties tab out of the window onto Monitor 2, where it
//    floats in a window of its own; Terrain takes its docked place.
// 4. It opens View and chooses Reset Layout: every panel springs back, and
//    the last frame is the first.
//
// Below 480 px wide there's one monitor: the split and the reset only. Like every
// loop it holds no state: a frame comes from (context, time, size) alone.

import { clamp, easeInOut, expoOut, lerp, lerpRect, progress, rect, spring } from "../easing.js";
import * as ui from "../drawing/editor.js";

const DURATION = 12;
/** The frame reduced motion shows: split, with Properties on Monitor 2. */
const STILL = 6.5;
const COMPACT_BELOW = 480;

// When things happen, in seconds into the loop.
const POINTER_IN = 0.3;
const SPLIT = Object.freeze({ reach: 0.9, press: 1.05, release: 2.0 });
const FLOAT = Object.freeze({ reach: 3.3, press: 3.45, release: 4.5 });
const AWAY = Object.freeze({ leave: 4.8, gone: 5.6, back: 7.0 });
const MENU = Object.freeze({ open: 7.8, hover: 8.25, choose: 8.45 });
const RESET = 8.5;
const POINTER_OUT = Object.freeze({ leave: 8.8, gone: 9.6 });

/** Every rectangle, as pure functions of the frame's size. */
function layout(g, size, labels) {
  const compact = size.width < COMPACT_BELOW;
  const u = compact ? clamp(size.width / 420, 0.65, 1) : clamp(size.width / 840, 0.6, 1.2);
  const titleBar = 24 * u;
  const menuBar = 20 * u;
  const tabBar = 24 * u;
  const pad = 8 * u;
  const monitor = compact
    ? rect(pad, pad, size.width - pad * 2, size.height - pad * 2 - 28 * u)
    : rect(size.width * 0.025, size.height * 0.06, size.width * 0.665, size.height * 0.78);
  const second = compact ? null : rect(size.width * 0.71, size.height * 0.06, size.width * 0.265, size.height * 0.78);
  const main = compact ? monitor : rect(monitor.x + pad, monitor.y + pad, monitor.width - pad * 2, monitor.height - pad * 2);
  const body = rect(main.x + 1, main.y + titleBar + menuBar, main.width - 2, main.height - titleBar - menuBar - 1);
  const split = body.x + body.width * (compact ? 0.6 : 0.68);
  const left = rect(body.x, body.y, split - body.x, body.height);
  const right = rect(split, body.y, body.x + body.width - split, body.height);
  const sceneArea = rect(left.x, left.y, left.width, left.height * (compact ? 0.62 : 0.68));
  const bottom = rect(left.x, sceneArea.y + sceneArea.height, left.width, left.height - sceneArea.height);
  const half = sceneArea.width / 2;
  const explorer = compact ? right : rect(right.x, right.y, right.width, right.height * 0.46);
  const propertiesPlace = compact ? null : rect(right.x, explorer.y + explorer.height, right.width, right.height - explorer.height);
  const floating = second ? rect(second.x + pad, second.y + second.height * 0.06, second.width - pad * 2, second.height * 0.84) : null;

  // The menu bar's items, and the View menu's dropdown.
  g.font = ui.font(400, 11 * u, "Inter");
  const menus = [];
  let x = main.x + 8 * u;
  for (const name of labels.menus) {
    const width = g.measureText(name).width + 12 * u;
    menus.push(rect(x, main.y + titleBar, width, menuBar));
    x += width;
  }
  const view = menus[labels.menus.indexOf("View")];
  const dropdown = rect(view.x, view.y + view.height, 150 * u, 64 * u);

  return Object.freeze({
    compact, u, titleBar, menuBar, tabBar, monitor, second, main, sceneArea, bottom, explorer, propertiesPlace,
    floating, menus, view, dropdown,
    sceneLeft: rect(sceneArea.x, sceneArea.y, half, sceneArea.height),
    sceneRight: rect(sceneArea.x + half, sceneArea.y, sceneArea.width - half, sceneArea.height),
    resetItem: rect(dropdown.x + 4 * u, dropdown.y + 36 * u, dropdown.width - 8 * u, 22 * u),
  });
}

/** Where a panel's first tab is held: its middle. */
function grip(g, box, names, u, tabBar) {
  const tab = ui.tabBoxes(g, box, names, u, tabBar)[0];
  return { x: tab.x + tab.width / 2, y: tab.y + tab.height / 2 };
}

/** How split the Scene View is (0 to 1, springing), and how far Properties has come home after a reset. */
function amounts(t) {
  let split = 0;
  if (t >= SPLIT.release) split = t < RESET ? spring(t - SPLIT.release, 2.2, 0.7) : 1 - spring(t - RESET, 2.0, 0.75);
  const home = t >= RESET ? spring(t - RESET - 0.08, 1.8, 0.75) : 0;
  return { split, home };
}

/** The pointer's tip, whether it's pressed, and how visible it is (0 while it's away). */
function pointerAt(t, L, points) {
  const start = { x: L.main.x + L.main.width * 1.05, y: L.main.y + L.main.height * 1.1 };
  const offFrame = { x: L.main.x + L.main.width * 0.9, y: L.main.y + L.main.height * 1.25 };
  const path = [
    [POINTER_IN, start],
    [SPLIT.reach, points.console],
    [SPLIT.press, points.console],
    [SPLIT.release, points.drop],
  ];
  if (L.compact) {
    path.push([SPLIT.release + 0.6, offFrame], [AWAY.back, offFrame]);
  } else {
    path.push(
      [FLOAT.reach, points.properties],
      [FLOAT.press, points.properties],
      [FLOAT.release, points.floating],
      [AWAY.leave, points.floating],
      [AWAY.gone, offFrame],
      [AWAY.back, offFrame]
    );
  }
  path.push(
    [MENU.open - 0.05, points.view],
    [MENU.hover, points.reset],
    [POINTER_OUT.leave, points.reset],
    [POINTER_OUT.gone, offFrame]
  );
  if (t < POINTER_IN || t >= POINTER_OUT.gone) return null;
  let at = path[path.length - 1][1];
  for (let index = 1; index < path.length; index += 1) {
    const [toTime, to] = path[index];
    const [fromTime, from] = path[index - 1];
    if (t < toTime) {
      const p = easeInOut(progress(t, fromTime, toTime - fromTime));
      at = { x: lerp(from.x, to.x, p), y: lerp(from.y, to.y, p) };
      break;
    }
  }
  const pressed =
    (t >= SPLIT.press && t < SPLIT.release + 0.04) ||
    (!L.compact && t >= FLOAT.press && t < FLOAT.release + 0.04) ||
    (t >= MENU.open - 0.06 && t < MENU.open + 0.04) ||
    (t >= MENU.choose - 0.04 && t < MENU.choose + 0.06);
  return { ...at, pressed };
}

function contents(g, colors, labels, box, pane, u, clock) {
  g.save();
  ui.clipTo(g, box);
  if (pane === "scene") ui.viewport(g, colors, box, u, clock);
  else if (pane === "explorer") ui.explorer(g, colors, box, labels, u);
  else if (pane === "properties") ui.properties(g, colors, box, labels, u);
  else if (pane === "console") ui.consoleLog(g, colors, box, labels, u);
  else if (pane === "terrain") ui.terrain(g, colors, box, labels, u);
  else if (pane === "assets") ui.assets(g, colors, box, labels, u);
  g.restore();
}

/** A docked place: its panel, its tabs and its active pane's contents. */
function place(g, colors, labels, box, names, pane, L, clock) {
  if (box.width < 2 || box.height < 2) return;
  const inside = ui.panel(g, colors, box, names, 0, L.u, L.tabBar);
  contents(g, colors, labels, inside, pane, L.u, clock);
}

function drawMenu(g, colors, labels, L, t) {
  const u = L.u;
  L.menus.forEach((item, index) => {
    const open = labels.menus[index] === "View" && t >= MENU.open && t < RESET;
    if (open) {
      g.fillStyle = colors.controlActive;
      g.fillRect(item.x, item.y + 2 * u, item.width, item.height - 4 * u);
    }
    g.font = ui.font(400, 11 * u, "Inter");
    g.fillStyle = open ? colors.fgStrong : colors.fgSecondary;
    g.textBaseline = "middle";
    g.fillText(labels.menus[index], item.x + 6 * u, item.y + item.height / 2);
  });
  if (t < MENU.open || t >= RESET) return;
  const box = L.dropdown;
  ui.shadow(g, colors, box, u, 1);
  g.fillStyle = colors.app;
  g.fillRect(box.x, box.y, box.width, box.height);
  g.strokeStyle = colors.lineStrong;
  g.lineWidth = 1;
  g.strokeRect(box.x + 0.5, box.y + 0.5, box.width - 1, box.height - 1);
  g.font = ui.font(500, 10.5 * u, "Inter");
  g.fillStyle = colors.fgWeak;
  g.fillText(labels.panels, box.x + 10 * u, box.y + 14 * u);
  g.fillStyle = colors.line;
  g.fillRect(box.x + 6 * u, box.y + 29 * u, box.width - 12 * u, 1);
  const item = L.resetItem;
  const hovered = t >= MENU.hover;
  if (hovered) {
    g.fillStyle = colors.controlActive;
    g.fillRect(item.x, item.y, item.width, item.height);
  }
  g.font = ui.font(400, 11.5 * u, "Inter");
  g.fillStyle = hovered ? colors.fgStrong : colors.fg;
  g.fillText(labels.reset, item.x + 8 * u, item.y + item.height / 2);
}

/** A whole window around a panel being dragged or floating: chrome at `chrome`, lifted by `lift`. */
function floatingWindow(context, frame, title, names, pane, L, clock, chrome, lift) {
  const { g, colors, labels, layer } = context;
  ui.shadow(g, colors, frame, L.u, lift);
  layer(chrome, (inside) => ui.windowChrome(inside.g, colors, frame, title, L.u, L.titleBar));
  const body = rect(frame.x + 1, frame.y + L.titleBar * chrome, frame.width - 2, frame.height - L.titleBar * chrome - 1);
  const content = ui.panel(g, colors, body, names, 0, L.u, L.tabBar);
  contents(g, colors, labels, content, pane, L.u, clock);
}

function render(context, time, size) {
  const { g, colors, labels, layer } = context;
  const L = layout(g, size, labels);
  const u = L.u;
  const tabs = labels.tabs;
  const t = time;
  // The viewport's block makes half a turn (it looks the same) each loop, so the wrap is seamless.
  const clock = (time * Math.PI) / (DURATION * 0.35);
  const { split, home } = amounts(t);
  const splitting = t >= SPLIT.press && t < SPLIT.release;
  const consoleOut = splitting || (t >= SPLIT.release && split > 0.5);
  const floatingOut = !L.compact && t >= FLOAT.press && (t < RESET || home < 0.98);

  // The monitors: quiet screens behind the windows.
  for (const screen of [L.monitor, L.second]) {
    if (!screen || L.compact) continue;
    g.fillStyle = colors.app;
    g.beginPath();
    g.roundRect(screen.x, screen.y, screen.width, screen.height, 6 * u);
    g.fill();
    g.strokeStyle = colors.line;
    g.lineWidth = 1;
    g.stroke();
  }

  // The main window, its menu bar and the dock.
  ui.windowChrome(g, colors, L.main, labels.window, u, L.titleBar);
  g.fillStyle = colors.line;
  g.fillRect(L.main.x + 1, L.main.y + L.titleBar + L.menuBar - 1, L.main.width - 2, 1);

  const sceneBox = lerpRect(L.sceneArea, L.sceneLeft, split);
  place(g, colors, labels, sceneBox, tabs.scene, "scene", L, clock);
  if (split > 0) {
    const grown = lerpRect(rect(L.sceneArea.x + L.sceneArea.width, L.sceneArea.y, 0, L.sceneArea.height), L.sceneRight, split);
    place(g, colors, labels, grown, [tabs.console[0]], "console", L, clock);
  }
  place(g, colors, labels, L.bottom, consoleOut ? tabs.console.slice(1) : tabs.console, consoleOut ? "assets" : "console", L, clock);
  place(g, colors, labels, L.explorer, tabs.explorer, "explorer", L, clock);
  if (L.propertiesPlace) {
    if (floatingOut) place(g, colors, labels, L.propertiesPlace, tabs.properties.slice(1), "terrain", L, clock);
    else place(g, colors, labels, L.propertiesPlace, tabs.properties, "properties", L, clock);
  }
  drawMenu(g, colors, labels, L, t);

  // Points the pointer goes to.
  const points = {
    console: grip(g, L.bottom, tabs.console, u, L.tabBar),
    drop: { x: L.sceneRight.x + L.sceneRight.width / 2, y: L.sceneRight.y + L.sceneRight.height * 0.45 },
    view: { x: L.view.x + L.view.width / 2, y: L.view.y + L.view.height / 2 },
    reset: { x: L.resetItem.x + 40 * u, y: L.resetItem.y + L.resetItem.height / 2 },
  };
  if (!L.compact) {
    const floatingBody = rect(L.floating.x, L.floating.y + L.titleBar, L.floating.width, L.floating.height - L.titleBar);
    points.properties = grip(g, L.propertiesPlace, tabs.properties, u, L.tabBar);
    points.floating = grip(g, floatingBody, [tabs.properties[0]], u, L.tabBar);

    // Properties: dragged out, floating on Monitor 2, then flying home after the reset.
    if (floatingOut) {
      let frame;
      let chrome;
      let lift;
      if (t < FLOAT.release) {
        const move = easeInOut(progress(t, FLOAT.press, FLOAT.release - FLOAT.press));
        const tear = expoOut(progress(t, FLOAT.press, 0.3));
        const held = { x: lerp(points.properties.x, points.floating.x, move), y: lerp(points.properties.y, points.floating.y, move) };
        const width = lerp(L.propertiesPlace.width, L.floating.width, tear);
        const height = lerp(L.propertiesPlace.height, L.floating.height, tear);
        const titleBar = L.titleBar * tear;
        const offset = grip(g, rect(0, 0, width, height), [tabs.properties[0]], u, L.tabBar);
        frame = rect(held.x - offset.x, held.y - offset.y - titleBar, width, height);
        chrome = tear;
        lift = 1 + tear;
      } else if (t < RESET) {
        const bob = 4 * u * Math.sin(2 * Math.PI * 3 * (t - FLOAT.release)) * Math.exp(-6 * (t - FLOAT.release));
        frame = rect(L.floating.x, L.floating.y + bob, L.floating.width, L.floating.height);
        chrome = 1;
        lift = lerp(2, 1.3, expoOut(progress(t, FLOAT.release, 0.4)));
      } else {
        const docked = rect(L.propertiesPlace.x, L.propertiesPlace.y - L.titleBar, L.propertiesPlace.width, L.propertiesPlace.height + L.titleBar);
        frame = lerpRect(L.floating, docked, home);
        chrome = 1 - expoOut(progress(t, RESET, 0.35));
        lift = 1.3 * (1 - clamp(home));
      }
      floatingWindow(context, frame, labels.monitor, [tabs.properties[0]], "properties", L, clock, chrome, lift);
    }
  }

  // The Console being dragged: a small copy of its panel under the pointer, and the drop preview.
  if (splitting) {
    const pointer = pointerAt(t, L, points);
    const over = expoOut(progress(t, SPLIT.release - 0.45, 0.2));
    if (over > 0) {
      g.save();
      g.globalAlpha *= over;
      g.fillStyle = colors.fgStrong;
      g.globalAlpha *= 0.08;
      g.fillRect(L.sceneRight.x, L.sceneRight.y, L.sceneRight.width, L.sceneRight.height);
      g.restore();
      g.save();
      g.globalAlpha *= over;
      g.strokeStyle = colors.fgStrong;
      g.lineWidth = 1.5 * u;
      g.strokeRect(L.sceneRight.x + 1, L.sceneRight.y + 1, L.sceneRight.width - 2, L.sceneRight.height - 2);
      g.restore();
    }
    const ghost = rect(0, 0, L.sceneArea.width * 0.42, L.sceneArea.height * 0.5);
    const hold = grip(g, ghost, [tabs.console[0]], u, L.tabBar);
    const box = rect(pointer.x - hold.x, pointer.y - hold.y, ghost.width, ghost.height);
    ui.shadow(g, colors, box, u, 1.5);
    layer(0.92, (inside) => place(inside.g, colors, labels, box, [tabs.console[0]], "console", L, clock));
  }

  const pointer = pointerAt(t, L, points);
  if (pointer) ui.pointer(g, colors, pointer.x, pointer.y, u, pointer.pressed);
}

export default Object.freeze({
  id: "editor",
  duration: DURATION,
  still: STILL,
  render,
});
