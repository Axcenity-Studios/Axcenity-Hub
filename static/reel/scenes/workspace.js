// Scene 1 (0–4 s): the workspace. The panel names arrive as kinetic type, then
// each word shrinks into its panel's tab as the panels spring into the editor
// window; Properties then undocks onto a second monitor and the Explorer grows
// into the space it left. Compact mode (phones) shows the Scene View and the
// Explorer only, and nothing undocks.
//
// Styled after the editor: its Dark theme tokens (via the site's tokens), its
// pane labels (crates/editor/src/layout.rs) and its square, 1px panel language.
//
// Like every scene, this module holds no state: render() draws the frame for
// `time` from (context, time, size) alone, so seeking anywhere, in any order,
// draws the same frame. All geometry is in logical (CSS) pixels.

import { clamp, expoOut, lerp, lerpRect, progress, rect, spring } from "../easing.js";

const START = 0;
const DURATION = 4;

// When things happen, in seconds into the scene.
const WORD_IN = 0.1; // the first word starts rising in
const WORD_STAGGER = 0.15;
const MORPH = 1.2; // the first word starts shrinking into its tab
const MORPH_STAGGER = 0.12;
const WINDOW_IN = 1.15; // the editor window fades in around the panels
const CONTENT_IN = 1.9; // the tree, rows and viewport appear
const UNDOCK = 2.5; // Properties lifts out to the second monitor
/** By this time into the build everything is at rest (springs settled to well under a pixel). */
export const SETTLED = 8;

/** Compact mode's stage: its top and its height as a share of its width. The hero's
 * stylesheet reserves the same space above the copy on phones (.hero-copy). */
export const COMPACT_TOP = 108;
export const COMPACT_ASPECT = 0.62;

// ---------- Layout (pure functions of the logical size) ----------

/** The region the workspace occupies: upper right on wide screens, above the copy on phones. */
export function stageRect(size) {
  if (size.compact) {
    const width = size.width - 32;
    return rect(16, COMPACT_TOP, width, width * COMPACT_ASPECT);
  }
  const right = size.width - Math.max(32, size.width * 0.04);
  const top = Math.max(112, size.height * 0.12);
  let width = Math.min(size.width * 0.54, 1120);
  let height = width * 0.6;
  const room = size.height * 0.6 - top;
  if (height > room) {
    height = Math.max(180, room);
    width = height / 0.6;
  }
  return rect(right - width, top, width, height);
}

/** The size unit: 1 at an 820 px wide stage, larger type in compact mode. */
function unitFor(size, stage) {
  return size.compact ? 1.15 : clamp(stage.width / 820, 0.8, 1.35);
}

function layout(size) {
  const stage = stageRect(size);
  const u = unitFor(size, stage);
  const titleBar = 26 * u;
  const main = size.compact
    ? stage
    : rect(stage.x, stage.y, stage.width * 0.8, stage.height * 0.9);
  const body = rect(main.x, main.y + titleBar, main.width, main.height - titleBar);
  const split = body.x + body.width * (size.compact ? 0.58 : 0.66);
  const column = rect(split, body.y, body.x + body.width - split, body.height);
  const scene = rect(body.x, body.y, split - body.x, body.height);
  const explorerDocked = size.compact ? column : rect(column.x, column.y, column.width, column.height * 0.56);
  const propertiesDocked = rect(column.x, column.y + explorerDocked.height, column.width, column.height - explorerDocked.height);
  const floatWidth = stage.width * 0.3;
  const floatHeight = stage.height * 0.56;
  const floating = rect(stage.x + stage.width - floatWidth, stage.y + stage.height * 0.4, floatWidth, floatHeight);
  const floatingBody = rect(floating.x, floating.y + titleBar, floating.width, floating.height - titleBar);
  return { stage, u, titleBar, main, scene, column, explorerDocked, propertiesDocked, floating, floatingBody };
}

// ---------- Drawing helpers ----------

function font(weight, px, family) {
  return `${weight} ${px}px "${family}", ui-sans-serif, sans-serif`;
}

function frame(g, colors, box, fill) {
  g.fillStyle = fill;
  g.fillRect(box.x, box.y, box.width, box.height);
  g.strokeStyle = colors.line;
  g.lineWidth = 1;
  g.strokeRect(box.x + 0.5, box.y + 0.5, box.width - 1, box.height - 1);
}

/** A soft drop shadow from stacked translucent rectangles (canvas blur works in device pixels, not logical ones). */
function shadow(g, colors, box, u, strength) {
  if (strength <= 0) return;
  g.save();
  const alpha = g.globalAlpha * 0.05 * strength;
  g.fillStyle = colors.shade;
  for (let step = 1; step <= 6; step += 1) {
    const spread = step * 3 * u;
    g.globalAlpha = alpha;
    g.fillRect(box.x - spread / 2, box.y + spread, box.width + spread, box.height);
  }
  g.restore();
}

/** A window: its frame, a title bar with three dots and its title. */
function windowChrome(g, colors, box, title, u, titleBar) {
  frame(g, colors, box, colors.app);
  g.fillStyle = colors.line;
  g.fillRect(box.x, box.y + titleBar - 1, box.width, 1);
  g.fillStyle = colors.controlActive;
  for (let dot = 0; dot < 3; dot += 1) {
    g.beginPath();
    g.arc(box.x + (12 + dot * 9) * u, box.y + titleBar / 2, 3 * u, 0, Math.PI * 2);
    g.fill();
  }
  g.fillStyle = colors.fgWeak;
  g.font = font(400, 11 * u, "Inter");
  g.textBaseline = "middle";
  g.fillText(title, box.x + 46 * u, box.y + titleBar / 2);
}

const TAB_FONT = 12;

function tabHeight(u) {
  return 24 * u;
}

/** Where a panel's tab label sits: its left edge and middle line. */
function tabLabelAt(box, u) {
  return { x: box.x + 12 * u, y: box.y + tabHeight(u) / 2 };
}

/** A docked panel: its body, its tab bar and its one active tab (the label is drawn separately). */
function panel(g, colors, box, label, u) {
  frame(g, colors, box, colors.panel);
  g.fillStyle = colors.app;
  g.fillRect(box.x + 1, box.y + 1, box.width - 2, tabHeight(u) - 1);
  g.font = font(600, TAB_FONT * u, "Inter");
  const tabWidth = Math.min(box.width - 2, g.measureText(label).width + 24 * u);
  g.fillStyle = colors.surface;
  g.fillRect(box.x + 1, box.y + 1, tabWidth, tabHeight(u) - 1);
}

function clipTo(g, box) {
  g.beginPath();
  g.rect(box.x, box.y, box.width, box.height);
  g.clip();
}

function contentBox(box, u) {
  return rect(box.x + 1, box.y + tabHeight(u), box.width - 2, box.height - tabHeight(u) - 1);
}

/** The Scene View's viewport: a perspective ground grid and a slowly turning wireframe block. */
function viewport(g, colors, box, u, clock) {
  g.fillStyle = colors.inset;
  g.fillRect(box.x, box.y, box.width, box.height);
  const horizon = box.y + box.height * 0.36;
  const bottom = box.y + box.height;
  const centre = box.x + box.width / 2;
  g.strokeStyle = colors.fgWeak;
  g.lineWidth = 1;
  g.beginPath();
  for (let line = -8; line <= 8; line += 1) {
    g.moveTo(centre + line * box.width * 0.02, horizon);
    g.lineTo(centre + line * box.width * 0.22, bottom);
  }
  for (let row = 1; row <= 7; row += 1) {
    const y = horizon + (bottom - horizon) * Math.pow(row / 7, 2);
    g.moveTo(box.x, y);
    g.lineTo(box.x + box.width, y);
  }
  g.stroke();

  // A unit block (the Pad), turning a little each second: a pure function of the clock.
  const angle = 0.6 + clock * 0.35;
  const tilt = 0.42;
  const scale = Math.min(box.width, box.height) * 0.2;
  const cx = centre;
  const cy = horizon + (bottom - horizon) * 0.3;
  const corners = [];
  for (const x of [-1, 1]) {
    for (const y of [-0.45, 0.45]) {
      for (const z of [-1, 1]) {
        const rx = x * Math.cos(angle) - z * Math.sin(angle);
        const rz = x * Math.sin(angle) + z * Math.cos(angle);
        const ry = y * Math.cos(tilt) - rz * Math.sin(tilt);
        const depth = 4 + y * Math.sin(tilt) + rz * Math.cos(tilt);
        corners.push([cx + (rx * scale * 4) / depth, cy + (ry * scale * 4) / depth]);
      }
    }
  }
  const edges = [
    [0, 1], [2, 3], [4, 5], [6, 7],
    [0, 2], [1, 3], [4, 6], [5, 7],
    [0, 4], [1, 5], [2, 6], [3, 7],
  ];
  g.strokeStyle = colors.fgStrong;
  g.lineWidth = 1.5 * u;
  g.beginPath();
  for (const [from, to] of edges) {
    g.moveTo(corners[from][0], corners[from][1]);
    g.lineTo(corners[to][0], corners[to][1]);
  }
  g.stroke();
}

function tree(g, colors, box, labels, u) {
  g.font = font(400, 12 * u, "Inter");
  g.textBaseline = "middle";
  const row = 20 * u;
  labels.tree.forEach(([name, depth], index) => {
    const y = box.y + 6 * u + index * row;
    if (name === labels.selected) {
      g.fillStyle = colors.controlActive;
      g.fillRect(box.x, y, box.width, row);
    }
    g.fillStyle = name === labels.selected ? colors.fgStrong : colors.fgSecondary;
    g.fillText(name, box.x + (12 + depth * 14) * u, y + row / 2);
  });
}

function properties(g, colors, box, labels, u) {
  g.font = font(400, 12 * u, "Inter");
  g.textBaseline = "middle";
  const row = 22 * u;
  labels.rows.forEach(([name, value], index) => {
    const y = box.y + 8 * u + index * row + row / 2;
    g.fillStyle = colors.fgWeak;
    g.fillText(name, box.x + 12 * u, y);
    g.fillStyle = colors.fg;
    g.fillText(value, box.x + box.width * 0.48, y);
  });
}

// ---------- The workspace at a moment of its build ----------

/**
 * Draws the workspace `build` seconds into its build (SETTLED or more is at
 * rest), with the viewport's block turned to `clock` seconds. Later scenes call
 * it to show the finished workspace. Pure: it draws from its arguments only.
 */
export function drawWorkspace(context, size, build, clock) {
  const { g, colors, labels } = context;
  const t = Math.min(build, SETTLED);
  const L = layout(size);
  const { u } = L;
  const names = size.compact
    ? [labels.panels.scene, labels.panels.explorer]
    : [labels.panels.scene, labels.panels.explorer, labels.panels.properties];

  // The kinetic type: big, stacked, left aligned in the stage.
  const big = size.compact
    ? Math.min(L.stage.width * 0.13, 44)
    : Math.min(L.stage.height * 0.15, L.stage.width * 0.09);
  const lineHeight = big * 1.08;
  const firstLine = L.stage.y + L.stage.height / 2 - (lineHeight * (names.length - 1)) / 2;
  const left = L.stage.x + L.stage.width * 0.06;
  g.font = font(800, big, "Plus Jakarta Sans");
  const words = names.map((name, index) => {
    const width = g.measureText(name).width;
    return { name, at: { x: left, y: firstLine + index * lineHeight }, box: rect(left, firstLine + index * lineHeight - big / 2, width, big) };
  });

  // Each panel's rectangle: from its word's box, springing to its place in the dock.
  const undock = size.compact ? 0 : spring(t - UNDOCK, 1.6, 0.62);
  const grow = size.compact ? 0 : expoOut(progress(t, UNDOCK + 0.2, 0.7));
  const homes = [
    L.scene,
    lerpRect(L.explorerDocked, rect(L.column.x, L.column.y, L.column.width, L.column.height), grow),
    L.propertiesDocked,
  ];
  const panels = words.map((word, index) => {
    const morphAt = MORPH + index * MORPH_STAGGER;
    let box = lerpRect(word.box, homes[index], spring(t - morphAt, 2, 0.6));
    if (index === 2) box = lerpRect(box, L.floatingBody, undock);
    return {
      word,
      box,
      shown: expoOut(progress(t, morphAt, 0.3)),
      shrink: expoOut(progress(t, morphAt, 0.8)),
      rise: expoOut(progress(t, WORD_IN + index * WORD_STAGGER, 0.7)),
    };
  });

  const windowAlpha = expoOut(progress(t, WINDOW_IN, 0.5));
  const contentAlpha = expoOut(progress(t, CONTENT_IN, 0.5));
  const base = g.globalAlpha;

  // The editor window, then the docked panels.
  if (windowAlpha > 0) {
    g.globalAlpha = base * windowAlpha;
    shadow(g, colors, L.main, u, 1);
    g.globalAlpha = base * windowAlpha;
    windowChrome(g, colors, L.main, labels.window, u, L.titleBar);
  }
  const contents = [
    (box) => viewport(g, colors, box, u, clock),
    (box) => tree(g, colors, box, labels, u),
    (box) => properties(g, colors, box, labels, u),
  ];
  const drawPanel = (item, index) => {
    if (item.shown <= 0) return;
    g.globalAlpha = base * item.shown;
    panel(g, colors, item.box, item.word.name, u);
    if (contentAlpha > 0) {
      g.save();
      g.globalAlpha = base * item.shown * contentAlpha;
      const inner = contentBox(item.box, u);
      clipTo(g, inner);
      contents[index](inner);
      g.restore();
    }
  };
  panels.slice(0, 2).forEach(drawPanel);

  // Properties' own window on the second monitor, around the panel as it floats out.
  if (panels[2]) {
    const lifted = expoOut(progress(t, UNDOCK, 0.4));
    if (lifted > 0) {
      const box = panels[2].box;
      const own = rect(box.x, box.y - L.titleBar, box.width, box.height + L.titleBar);
      g.globalAlpha = base * lifted;
      shadow(g, colors, own, u, 1.6);
      g.globalAlpha = base * lifted;
      windowChrome(g, colors, own, labels.floating, u, L.titleBar);
    }
    drawPanel(panels[2], 2);
  }

  // The words: big while they rise in, then shrinking into their tabs.
  g.textBaseline = "middle";
  for (const item of panels) {
    if (item.rise <= 0) continue;
    const tab = tabLabelAt(item.box, u);
    const px = lerp(big, TAB_FONT * u, item.shrink);
    const x = lerp(item.word.at.x, tab.x, item.shrink);
    const y = lerp(item.word.at.y + (1 - item.rise) * big * 0.4, tab.y, item.shrink);
    // The display face hands over to the editor's UI face (Inter) as the word lands in its tab.
    const handover = progress(item.shrink, 0.6, 0.4);
    g.fillStyle = colors.fgStrong;
    if (handover < 1) {
      g.globalAlpha = base * item.rise * (1 - handover);
      g.font = font(800, px, "Plus Jakarta Sans");
      g.fillText(item.word.name, x, y);
    }
    if (handover > 0) {
      g.globalAlpha = base * item.rise * handover;
      g.font = font(600, px, "Inter");
      g.fillText(item.word.name, x, y);
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
