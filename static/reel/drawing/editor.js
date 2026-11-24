// The editor's pieces, drawn on the canvas: windows, tab bars, docked panels,
// each pane's contents and the pointer. Styled after the editor's own look:
// square 1px panels, quiet tab bars on the app colour with the active tab
// joined to its panel (crates/editor/src/layout.rs style), collapsible
// Properties sections (crates/editor/src/properties.rs) and the Console's
// timed log (crates/editor/src/output.rs). Colours are the site's tokens only.
//
// Every function draws from its arguments alone (no state, no clock), in
// logical pixels; `u` is the loop's size unit.

import { rect } from "../easing.js";
import { hash } from "./terrain.js";

/** A canvas font shorthand with fallbacks. */
export function font(weight, px, family) {
  return `${weight} ${px}px "${family}", ui-sans-serif, sans-serif`;
}

/** The tab labels' size before scaling by `u`. */
export const TAB_FONT = 12;

export function fill(g, color, box) {
  g.fillStyle = color;
  g.fillRect(box.x, box.y, box.width, box.height);
}

export function outline(g, color, box) {
  g.strokeStyle = color;
  g.lineWidth = 1;
  g.strokeRect(box.x + 0.5, box.y + 0.5, box.width - 1, box.height - 1);
}

export function text(g, color, value, x, y, css, align = "left") {
  g.font = css;
  g.fillStyle = color;
  g.textAlign = align;
  g.textBaseline = "middle";
  g.fillText(value, x, y);
  g.textAlign = "left";
}

/** Clips everything after it (until the caller's restore) to `box`. */
export function clipTo(g, box) {
  g.beginPath();
  g.rect(box.x, box.y, box.width, box.height);
  g.clip();
}

/** A soft drop shadow from stacked translucent rectangles (canvas blur works in device pixels). */
export function shadow(g, colors, box, u, strength) {
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

/** A window's frame and title bar: three dots and its title. */
export function windowChrome(g, colors, box, title, u, titleBar) {
  fill(g, colors.app, box);
  outline(g, colors.lineStrong, box);
  fill(g, colors.line, rect(box.x, box.y + titleBar - 1, box.width, 1));
  g.fillStyle = colors.controlActive;
  for (let dot = 0; dot < 3; dot += 1) {
    g.beginPath();
    g.arc(box.x + (12 + dot * 9) * u, box.y + titleBar / 2, 3 * u, 0, Math.PI * 2);
    g.fill();
  }
  text(g, colors.fgWeak, title, box.x + 46 * u, box.y + titleBar / 2, font(400, 11 * u, "Inter"));
}

/** Each tab's box in a tab bar: at least 72 wide, its label centred (egui_dock's tabs). */
export function tabBoxes(g, box, names, u, tabBar) {
  g.font = font(600, TAB_FONT * u, "Inter");
  const boxes = [];
  let x = box.x + 1;
  for (const name of names) {
    const width = Math.max(72 * u, g.measureText(name).width + 22 * u);
    boxes.push(rect(x, box.y + 1, width, tabBar - 1));
    x += width;
  }
  return boxes;
}

/** Where a tab's label starts (left edge, middle line), so a word can land exactly on it. */
export function tabLabelAt(g, box, names, index, u, tabBar) {
  const tab = tabBoxes(g, box, names, u, tabBar)[index];
  g.font = font(600, TAB_FONT * u, "Inter");
  const width = g.measureText(names[index]).width;
  return { x: tab.x + (tab.width - width) / 2, y: tab.y + tab.height / 2 };
}

/**
 * A docked panel: its body, a tab bar on the app colour, and its tabs. The active
 * tab shares the panel's colour; the others are quiet, at `othersAlpha`. With
 * `labelActive` false the active tab's label is left for the caller (a word
 * landing in it). Returns the content box under the tab bar.
 */
export function panel(g, colors, box, names, active, u, tabBar, labelActive = true, othersAlpha = 1) {
  fill(g, colors.panel, box);
  fill(g, colors.app, rect(box.x, box.y, box.width, tabBar));
  fill(g, colors.line, rect(box.x, box.y + tabBar - 1, box.width, 1));
  const tabs = tabBoxes(g, box, names, u, tabBar);
  g.save();
  clipTo(g, box);
  tabs.forEach((tab, index) => {
    const on = index === active;
    if (on) fill(g, colors.panel, rect(tab.x, tab.y, tab.width, tab.height + 1));
    if (on ? !labelActive : othersAlpha <= 0) return;
    g.save();
    if (!on) g.globalAlpha *= othersAlpha;
    text(g, on ? colors.fgStrong : colors.fgWeak, names[index], tab.x + tab.width / 2, tab.y + tab.height / 2,
      font(600, TAB_FONT * u, "Inter"), "center");
    g.restore();
  });
  g.restore();
  outline(g, colors.line, box);
  return rect(box.x + 1, box.y + tabBar, box.width - 2, box.height - tabBar - 1);
}

// ---------- Pane contents ----------

/**
 * The Scene View: a perspective ground grid and a slowly turning block (the Pad).
 * `textured` (0 to 1) fades in the rock texture the Toolbox puts on it: shaded
 * faces, drawn back to front, flecked with stone.
 */
export function viewport(g, colors, box, u, clock, textured = 0) {
  fill(g, colors.inset, box);
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

  const angle = 0.6 + clock * 0.35;
  const tilt = 0.42;
  const scale = Math.min(box.width, box.height) * 0.2;
  const cy = horizon + (bottom - horizon) * 0.3;
  const corners = [];
  for (const x of [-1, 1]) {
    for (const y of [-0.45, 0.45]) {
      for (const z of [-1, 1]) {
        const rx = x * Math.cos(angle) - z * Math.sin(angle);
        const rz = x * Math.sin(angle) + z * Math.cos(angle);
        const ry = y * Math.cos(tilt) - rz * Math.sin(tilt);
        const depth = 4 + y * Math.sin(tilt) + rz * Math.cos(tilt);
        corners.push([centre + (rx * scale * 4) / depth, cy + (ry * scale * 4) / depth, depth]);
      }
    }
  }
  if (textured > 0) texturedFaces(g, colors, corners, u, textured);
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

// The block's faces by corner (corner index = x * 4 + y * 2 + z), the top first.
const FACES = Object.freeze([
  Object.freeze({ corners: [0, 1, 5, 4], shade: "lineStrong" }),
  Object.freeze({ corners: [2, 3, 7, 6], shade: "control" }),
  Object.freeze({ corners: [0, 1, 3, 2], shade: "controlActive" }),
  Object.freeze({ corners: [4, 5, 7, 6], shade: "controlActive" }),
  Object.freeze({ corners: [0, 2, 6, 4], shade: "control" }),
  Object.freeze({ corners: [1, 3, 7, 5], shade: "control" }),
]);

/** The Pad's faces with its rock texture, farthest first, at `alpha`. */
function texturedFaces(g, colors, corners, u, alpha) {
  const faces = FACES.map((face, index) => ({
    ...face,
    index,
    depth: face.corners.reduce((sum, corner) => sum + corners[corner][2], 0) / 4,
  })).sort((a, b) => b.depth - a.depth);
  g.save();
  g.globalAlpha *= alpha;
  for (const face of faces) {
    const [a, b, c, d] = face.corners.map((corner) => corners[corner]);
    g.beginPath();
    g.moveTo(a[0], a[1]);
    g.lineTo(b[0], b[1]);
    g.lineTo(c[0], c[1]);
    g.lineTo(d[0], d[1]);
    g.closePath();
    g.fillStyle = colors[face.shade];
    g.fill();
    // Flecks of stone, placed by the face's own coordinates so they turn with it.
    g.save();
    g.clip();
    for (let fleck = 0; fleck < 26; fleck += 1) {
      const s = hash(face.index * 97 + fleck);
      const t = hash(face.index * 131 + fleck + 50);
      const x = (1 - s) * ((1 - t) * a[0] + t * d[0]) + s * ((1 - t) * b[0] + t * c[0]);
      const y = (1 - s) * ((1 - t) * a[1] + t * d[1]) + s * ((1 - t) * b[1] + t * c[1]);
      g.fillStyle = fleck % 3 === 0 ? colors.fgWeak : colors.line;
      g.beginPath();
      g.ellipse(x, y, (1.2 + hash(fleck + 7) * 2.4) * u, (0.8 + hash(fleck + 9) * 1.4) * u, hash(fleck) * 3, 0, Math.PI * 2);
      g.fill();
    }
    g.restore();
  }
  g.restore();
}

/** A small class glyph: a square outline, the way each row leads with its class's icon. */
export function glyph(g, colors, x, y, u) {
  const side = 8 * u;
  g.strokeStyle = colors.fgWeak;
  g.lineWidth = 1;
  g.strokeRect(x + 0.5, y - side / 2 + 0.5, side, side);
}

/** The Explorer: the place's tree, the selected row highlighted. */
export function explorer(g, colors, box, labels, u) {
  const row = 20 * u;
  labels.tree.forEach(([name, depth], index) => {
    const y = box.y + 6 * u + index * row;
    const on = name === labels.selected;
    if (on) fill(g, colors.controlActive, rect(box.x, y, box.width, row));
    const x = box.x + (10 + depth * 14) * u;
    glyph(g, colors, x, y + row / 2, u);
    text(g, on ? colors.fgStrong : colors.fgSecondary, name, x + 14 * u, y + row / 2, font(400, 12 * u, "Inter"));
  });
}

export function field(g, colors, box, value, u, quiet = false) {
  fill(g, colors.inset, box);
  outline(g, colors.line, box);
  text(g, quiet ? colors.fgWeak : colors.fg, value, box.x + 7 * u, box.y + box.height / 2, font(400, 11.5 * u, "Inter"));
}

export function checkbox(g, colors, x, y, u, on) {
  const side = 12 * u;
  const box = rect(x, y - side / 2, side, side);
  fill(g, colors.inset, box);
  outline(g, colors.lineStrong, box);
  if (!on) return;
  g.strokeStyle = colors.fgStrong;
  g.lineWidth = 1.6 * u;
  g.beginPath();
  g.moveTo(x + 3 * u, y);
  g.lineTo(x + 5.2 * u, y + 2.4 * u);
  g.lineTo(x + 9.2 * u, y - 2.6 * u);
  g.stroke();
}

/** How light a token's colour is, 0 to 1 (its red channel; the tokens are greys). */
function brightness(token) {
  return parseInt(token.slice(1, 3), 16) / 255;
}

function chevron(g, colors, x, y, u) {
  g.fillStyle = colors.fgSecondary;
  g.beginPath();
  g.moveTo(x, y - 2.5 * u);
  g.lineTo(x + 7 * u, y - 2.5 * u);
  g.lineTo(x + 3.5 * u, y + 2.5 * u);
  g.closePath();
  g.fill();
}

/**
 * The Properties pane for the selected Pad: its name and class, the "Filter
 * properties" field, then each section (Data, Appearance, Behavior, Part) with
 * a divider, a chevron and its rows: a name, then a field, a checkbox or a
 * colour swatch.
 */
export function properties(g, colors, box, labels, u) {
  const pane = labels.properties;
  const pad = 8 * u;
  let y = box.y + pad + 8 * u;
  glyph(g, colors, box.x + pad, y, u);
  g.font = font(600, 13 * u, "Inter");
  const nameWidth = g.measureText(pane.name).width;
  text(g, colors.fgStrong, pane.name, box.x + pad + 14 * u, y, font(600, 13 * u, "Inter"));
  text(g, colors.fgWeak, pane.class, box.x + pad + 20 * u + nameWidth, y, font(400, 11.5 * u, "Inter"));
  y += 16 * u;
  field(g, colors, rect(box.x + pad, y, box.width - pad * 2, 20 * u), pane.filter, u, true);
  y += 30 * u;
  const row = 22 * u;
  const valueX = box.x + box.width * 0.46;
  for (const [title, rows] of pane.sections) {
    fill(g, colors.line, rect(box.x, y, box.width, 1));
    y += row / 2 + 2 * u;
    chevron(g, colors, box.x + pad, y, u);
    text(g, colors.fgSecondary, title, box.x + pad + 13 * u, y, font(500, 12 * u, "Inter"));
    y += row;
    for (const [name, value, kind] of rows) {
      text(g, colors.fgSecondary, name, box.x + pad + 4 * u, y, font(400, 11.5 * u, "Inter"));
      if (kind === "check") {
        checkbox(g, colors, valueX, y, u, value === "true");
      } else if (kind === "color") {
        // Part's default grey (163, 163, 163): the token nearest it in each scheme.
        const side = 12 * u;
        const swatch = brightness(colors.app) < 0.5 ? colors.fgSecondary : colors.lineStrong;
        fill(g, swatch, rect(valueX, y - side / 2, side, side));
        outline(g, colors.line, rect(valueX, y - side / 2, side, side));
        text(g, colors.fg, value, valueX + side + 6 * u, y, font(400, 11.5 * u, "Inter"));
      } else {
        field(g, colors, rect(valueX, y - 9 * u, box.x + box.width - pad - valueX, 18 * u), value, u);
      }
      y += row;
    }
    y += 2 * u;
  }
}

/**
 * The Console: the "Filter logs" field, timed lines, typed commands, and the
 * command line. `extra` lines (time, text, kind, alpha) arrive after the
 * project's own; when they don't all fit, the oldest scroll away.
 */
export function consoleLog(g, colors, box, labels, u, extra = []) {
  const pane = labels.console;
  const pad = 8 * u;
  field(g, colors, rect(box.x + pad, box.y + pad, Math.min(180 * u, box.width - pad * 2), 18 * u), pane.filter, u, true);
  const mono = font(400, 11 * u, "JetBrains Mono");
  const row = 18 * u;
  const top = box.y + pad + 18 * u + 12 * u;
  const input = rect(box.x + pad, box.y + box.height - pad - 20 * u, box.width - pad * 2, 20 * u);
  const room = Math.max(1, Math.floor((input.y - top + row / 2) / row));
  const lines = [...pane.lines, ...extra].filter((line) => (line[3] ?? 1) > 0);
  // A line still arriving pushes the others up by its share of a row.
  const arriving = lines.length > room ? (lines[lines.length - 1][3] ?? 1) : 1;
  const shown = lines.slice(Math.max(0, lines.length - room - 1));
  const scroll = lines.length > room ? (shown.length - room - 1 + arriving) * row : 0;
  g.font = mono;
  const timeWidth = g.measureText("00:00:00").width + 10 * u;
  g.save();
  clipTo(g, rect(box.x, top - row / 2, box.width, input.y - (top - row / 2) - 2 * u));
  let y = top - scroll;
  for (const [time, line, kind, alpha = 1] of shown) {
    g.save();
    g.globalAlpha *= alpha;
    if (kind === "command") {
      text(g, colors.fgStrong, "›", box.x + pad, y, mono);
      text(g, colors.fgStrong, line, box.x + pad + timeWidth, y, mono);
    } else {
      text(g, colors.fgWeak, time, box.x + pad, y, mono);
      text(g, colors.fg, line, box.x + pad + timeWidth, y, mono);
    }
    g.restore();
    y += row;
  }
  g.restore();
  if (input.y > top) field(g, colors, input, pane.prompt, u, true);
}

export function chip(g, colors, x, y, label, u, on) {
  g.font = font(500, 11.5 * u, "Inter");
  const width = g.measureText(label).width + 16 * u;
  if (on) {
    g.fillStyle = colors.controlActive;
    g.beginPath();
    g.roundRect(x, y - 11 * u, width, 22 * u, 11 * u);
    g.fill();
  }
  text(g, on ? colors.fgStrong : colors.fgWeak, label, x + 8 * u, y, font(500, 11.5 * u, "Inter"));
  return width;
}

/** Where the Terrain pane's tool button `index` sits in its content box. */
export function terrainTool(box, index, u) {
  const pad = 8 * u;
  return rect(box.x + pad, box.y + pad + 31 * u + index * 26 * u, box.width - pad * 2, 22 * u);
}

/** The Terrain Studio: its Sculpt and Materials tabs as chips, and the Sculpt tools; `active` is chosen. */
export function terrain(g, colors, box, labels, u, active = -1) {
  const pane = labels.terrain;
  const pad = 8 * u;
  let x = box.x + pad;
  const y = box.y + pad + 11 * u;
  pane.tabs.forEach((label, index) => {
    x += chip(g, colors, x, y, label, u, index === 0) + 4 * u;
  });
  pane.tools.forEach((label, index) => {
    const button = terrainTool(box, index, u);
    const on = index === active;
    fill(g, on ? colors.controlActive : colors.control, button);
    if (on) outline(g, colors.lineStrong, button);
    text(g, on ? colors.fgStrong : colors.fgSecondary, label, button.x + 8 * u, button.y + button.height / 2, font(on ? 500 : 400, 11.5 * u, "Inter"));
  });
}

/** The Assets pane's Toolbox button (asset_browser/panel.rs), top right of its content box. */
export function toolboxButton(g, box, label, u) {
  g.font = font(500, 11.5 * u, "Inter");
  const width = g.measureText(label).width + 30 * u;
  return rect(box.x + box.width - width - 8 * u, box.y + 8 * u, width, 22 * u);
}

/** A small toolbox glyph: a case with a handle. */
function caseGlyph(g, colors, x, y, u) {
  g.strokeStyle = colors.fgSecondary;
  g.lineWidth = 1.2 * u;
  g.strokeRect(x, y - 3 * u, 10 * u, 7 * u);
  g.beginPath();
  g.moveTo(x + 3 * u, y - 3 * u);
  g.lineTo(x + 3 * u, y - 5 * u);
  g.lineTo(x + 7 * u, y - 5 * u);
  g.lineTo(x + 7 * u, y - 3 * u);
  g.stroke();
}

/** A button: a control-coloured box and its label, pressed or chosen when `on`. */
export function button(g, colors, box, label, u, on = false) {
  fill(g, on ? colors.controlActive : colors.control, box);
  outline(g, on ? colors.lineStrong : colors.line, box);
  text(g, on ? colors.fgStrong : colors.fgSecondary, label, box.x + box.width / 2, box.y + box.height / 2,
    font(500, 11.5 * u, "Inter"), "center");
}

/** Assets: a grid of tiles, each a thumbnail square and a file name, and the Toolbox button. */
export function assets(g, colors, box, labels, u, pressed = false) {
  const pad = 8 * u;
  const tile = 46 * u;
  const gap = 10 * u;
  let right = box.x + box.width;
  if (labels.toolbox) {
    const open = toolboxButton(g, box, labels.toolbox.button, u);
    right = open.x - gap;
    fill(g, pressed ? colors.controlActive : colors.control, open);
    outline(g, colors.line, open);
    caseGlyph(g, colors, open.x + 8 * u, open.y + open.height / 2, u);
    text(g, pressed ? colors.fgStrong : colors.fgSecondary, labels.toolbox.button, open.x + 23 * u, open.y + open.height / 2,
      font(500, 11.5 * u, "Inter"));
  }
  let x = box.x + pad;
  for (const name of labels.assets) {
    if (x + tile > right) break;
    const thumb = rect(x, box.y + pad, tile, tile * 0.7);
    fill(g, colors.surface, thumb);
    outline(g, colors.line, thumb);
    g.save();
    clipTo(g, rect(x, thumb.y + thumb.height, tile + gap - 2 * u, 18 * u));
    text(g, colors.fgWeak, name, x, thumb.y + thumb.height + 9 * u, font(400, 10.5 * u, "Inter"));
    g.restore();
    x += tile + gap;
  }
}

/** The pointer: an arrow, its tip at (x, y), a little smaller while pressed. */
export function pointer(g, colors, x, y, u, pressed) {
  const s = u * (pressed ? 0.9 : 1);
  const points = [[0, 0], [0, 17], [4.6, 13], [7.6, 19.6], [10.4, 18.4], [7.4, 11.8], [12.6, 11.8]];
  g.beginPath();
  points.forEach(([px, py], index) => {
    if (index === 0) g.moveTo(x + px * s, y + py * s);
    else g.lineTo(x + px * s, y + py * s);
  });
  g.closePath();
  g.fillStyle = colors.fgStrong;
  g.fill();
  g.strokeStyle = colors.app;
  g.lineWidth = 1.2 * u;
  g.lineJoin = "round";
  g.stroke();
}
