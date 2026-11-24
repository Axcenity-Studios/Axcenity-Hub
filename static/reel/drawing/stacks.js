// The block editor's Blocks view, drawn on the canvas: Scratch-style blocks
// that snap into stacks. Styled after crates/editor/src/block_editor.rs (the
// sizes: 40-point rows, 12-point padding, 8-point corners, a hat's rounder top
// and band, the tab under each block), painter.rs (hats, statements, menus,
// typed fields, reporters) and canvas.rs (the dot grid). A block's words are
// its `sections()` rows, as the editor lays them out.
//
// The category fills are the editor's with Increase contrast (theme.rs Hue,
// darkened until white text reads at 4.5:1), its edges the hue at 78 %, and
// the typed fields its INPUT_FIELD and INPUT_TEXT: content colours, the same in
// both schemes as in the editor. The canvas itself is the site's tokens.
//
// Every function draws from its arguments alone, in logical pixels; `z` is
// the canvas's zoom (1 is the editor's own size).

import { rect } from "../easing.js";
import { font } from "./editor.js";

// Sizes at zoom 1, in points (block_editor.rs).
const ROW = 40;
const PAD = 12;
const GAP = 8;
const MIN_WIDTH = 96;
const CORNER = 8;
const CAP = 8;
const HAT_CORNER = 14;
const TAB_LEFT = 16;
const TAB_WIDTH = 28;
const TAB_DEPTH = 6;
const DROP = 2;
const INPUT = 24;
const FIELD_CORNER = 6;
const REPORTER_MIN = 32;
const REPORTER_INSET = 10;
const ICON = 18;
const DOTS = 24;

/** Each category's fill and edge token. */
const HUES = Object.freeze({
  events: Object.freeze(["blockEvents", "blockEventsEdge"]),
  looks: Object.freeze(["blockLooks", "blockLooksEdge"]),
  sensing: Object.freeze(["blockSensing", "blockSensingEdge"]),
});
/** painter.rs: menus darken the block by black at 45/255, fields are edged in black at 36/255. */
const MENU_SHADE = 45 / 255;
const FIELD_EDGE = 36 / 255;
const BAND = 34 / 255;

const words = (z) => font(500, 13 * z, "Inter");

/** The canvas: its background and a dot grid every 24 points, moving with `offset`. */
export function canvas(g, colors, box, z, offset = { x: 0, y: 0 }) {
  g.fillStyle = colors.inset;
  g.fillRect(box.x, box.y, box.width, box.height);
  g.save();
  g.beginPath();
  g.rect(box.x, box.y, box.width, box.height);
  g.clip();
  g.fillStyle = colors.fgStrong;
  g.globalAlpha *= 0.12;
  const step = DOTS * z;
  const wrap = (value) => ((value % step) + step) % step;
  for (let y = box.y + wrap(offset.y); y < box.y + box.height; y += step) {
    for (let x = box.x + wrap(offset.x); x < box.x + box.width; x += step) {
      g.fillRect(x - 0.6, y - 0.6, 1.2, 1.2);
    }
  }
  g.restore();
}

/** A part's size: ["label", text], ["menu", text], ["text" | "number", value], ["vector", [x, y, z]], ["reporter", category, parts]. */
function partSize(g, part, z) {
  const [kind, value] = part;
  g.font = words(z);
  const width = (text) => g.measureText(text).width;
  if (kind === "icon") return { width: ICON * z, height: ICON * z };
  if (kind === "label") return { width: width(value), height: 16 * z };
  if (kind === "menu") return { width: width(value) + 28 * z, height: INPUT * z };
  if (kind === "text") return { width: Math.max(width(value) + 14 * z, 36 * z), height: INPUT * z };
  if (kind === "number") return { width: Math.max(width(value) + 16 * z, 30 * z), height: INPUT * z };
  if (kind === "vector") {
    const axes = value.reduce((sum, axis) => sum + Math.max(width(axis) + 12 * z, 28 * z), 0);
    return { width: axes + 6 * z, height: INPUT * z };
  }
  const inner = rowSize(g, part[2], z, 6);
  return {
    width: inner.width + REPORTER_INSET * 2 * z,
    height: Math.max(inner.height + 8 * z, REPORTER_MIN * z),
  };
}

/** A row of parts laid side by side, `gap` points apart. */
function rowSize(g, parts, z, gap = GAP) {
  let width = 0;
  let height = 0;
  parts.forEach((part, index) => {
    const size = partSize(g, part, z);
    width += size.width + (index ? gap * z : 0);
    height = Math.max(height, size.height);
  });
  return { width, height };
}

/** A block's rows (the first led by its icon), each row's height, and its whole size. */
export function blockSize(g, block, z, hat = false) {
  const rows = block.rows.map((parts, index) => (index === 0 ? [["icon", block.icon], ...parts] : parts));
  const sizes = rows.map((parts) => rowSize(g, parts, z));
  const heights = sizes.map((size) => Math.max(ROW * z, size.height + 12 * z));
  const width = Math.max((hat ? MIN_WIDTH + 40 : MIN_WIDTH) * z, ...sizes.map((size) => size.width + PAD * 2 * z));
  const height = heights.reduce((sum, h) => sum + h, 0) + (hat ? CAP * z : 0);
  return { rows, heights, width, height };
}

/** The block's icon, white: a pointing hand (When touched) or a sparkle (Spawn decal). */
function icon(g, colors, name, x, y, z) {
  const s = (ICON * z) / 2;
  g.fillStyle = colors.nodeTitle;
  g.beginPath();
  if (name === "sparkle") {
    const star = (cx, cy, r) => {
      g.moveTo(cx, cy - r);
      g.quadraticCurveTo(cx, cy, cx + r, cy);
      g.quadraticCurveTo(cx, cy, cx, cy + r);
      g.quadraticCurveTo(cx, cy, cx - r, cy);
      g.quadraticCurveTo(cx, cy, cx, cy - r);
    };
    star(x - s * 0.15, y + s * 0.15, s * 0.75);
    star(x + s * 0.6, y - s * 0.55, s * 0.32);
  } else {
    // A hand pointing up: the finger, then the fist.
    g.roundRect(x - s * 0.42, y - s * 0.95, s * 0.36, s * 1.1, s * 0.18);
    g.roundRect(x - s * 0.5, y - s * 0.05, s * 1.05, s * 0.95, s * 0.3);
  }
  g.fill();
}

function menu(g, colors, box, text, z) {
  g.save();
  g.globalAlpha *= MENU_SHADE;
  g.fillStyle = colors.blockShade;
  g.beginPath();
  g.roundRect(box.x, box.y, box.width, box.height, FIELD_CORNER * z);
  g.fill();
  g.restore();
  g.fillStyle = colors.nodeTitle;
  g.font = words(z);
  g.textBaseline = "middle";
  g.textAlign = "left";
  g.fillText(text, box.x + 9 * z, box.y + box.height / 2);
  const cx = box.x + box.width - 9 * z;
  const cy = box.y + box.height / 2;
  g.beginPath();
  g.moveTo(cx - 3 * z, cy - 1.5 * z);
  g.lineTo(cx + 3 * z, cy - 1.5 * z);
  g.lineTo(cx, cy + 2 * z);
  g.closePath();
  g.fill();
}

function field(g, colors, box, text, z) {
  g.fillStyle = colors.blockField;
  g.beginPath();
  g.roundRect(box.x + 0.5, box.y + 0.5, box.width - 1, box.height - 1, FIELD_CORNER * z);
  g.fill();
  g.save();
  g.globalAlpha *= FIELD_EDGE;
  g.strokeStyle = colors.blockShade;
  g.lineWidth = 1;
  g.stroke();
  g.restore();
  g.fillStyle = colors.blockFieldText;
  g.font = words(z);
  g.textBaseline = "middle";
  g.textAlign = "center";
  g.fillText(text, box.x + box.width / 2, box.y + box.height / 2);
}

/** Draws a row of parts from `x`, centred on `cy`. */
function drawRow(g, colors, parts, x, cy, z, gap = GAP) {
  let at = x;
  for (const part of parts) {
    const size = partSize(g, part, z);
    const box = rect(at, cy - size.height / 2, size.width, size.height);
    const [kind, value] = part;
    if (kind === "icon") icon(g, colors, value, at + size.width / 2, cy, z);
    else if (kind === "label") {
      g.fillStyle = colors.nodeTitle;
      g.font = words(z);
      g.textBaseline = "middle";
      g.textAlign = "left";
      g.fillText(value, at, cy);
    } else if (kind === "menu") menu(g, colors, box, value, z);
    else if (kind === "text" || kind === "number") field(g, colors, box, value, z);
    else if (kind === "vector") {
      let left = at;
      g.font = words(z);
      for (const axis of value) {
        const width = Math.max(g.measureText(axis).width + 12 * z, 28 * z);
        field(g, colors, rect(left, box.y, width, box.height), axis, z);
        left += width + 3 * z;
      }
    } else {
      const [fill, edge] = HUES[value];
      g.beginPath();
      g.roundRect(box.x + 0.5, box.y + 0.5, box.width - 1, box.height - 1, (FIELD_CORNER + 2) * z);
      g.fillStyle = colors[fill];
      g.fill();
      g.strokeStyle = colors[edge];
      g.lineWidth = 1;
      g.stroke();
      drawRow(g, colors, part[2], at + REPORTER_INSET * z, cy, z, 6);
    }
    at += size.width + gap * z;
  }
}

/** The tab under a block, which the next block's top fits round. */
function tab(g, colors, category, x, y, z) {
  const [fill, edge] = HUES[category];
  const box = rect(x + TAB_LEFT * z, y - 1, TAB_WIDTH * z, TAB_DEPTH * z + 1);
  g.beginPath();
  g.roundRect(box.x, box.y + DROP * z, box.width, box.height, [0, 0, 4 * z, 4 * z]);
  g.fillStyle = colors[edge];
  g.fill();
  g.beginPath();
  g.roundRect(box.x, box.y, box.width, box.height, [0, 0, 4 * z, 4 * z]);
  g.fillStyle = colors[fill];
  g.fill();
}

/**
 * A block at (x, y): `block` is { category, icon, rows }, each row a list of
 * parts. A hat has a rounder top and a light band; every block has its shadow,
 * its edge and a tab underneath. Returns its size.
 */
export function drawBlock(g, colors, block, x, y, z, hat = false) {
  const size = blockSize(g, block, z, hat);
  const [fill, edge] = HUES[block.category];
  const top = (hat ? HAT_CORNER : CORNER) * z;
  const radii = [top, top, CORNER * z, CORNER * z];
  g.beginPath();
  g.roundRect(x, y + DROP * z, size.width, size.height, radii);
  g.fillStyle = colors[edge];
  g.fill();
  g.beginPath();
  g.roundRect(x + 0.5, y + 0.5, size.width - 1, size.height - 1, radii);
  g.fillStyle = colors[fill];
  g.fill();
  if (hat) {
    g.save();
    g.globalAlpha *= BAND;
    g.beginPath();
    g.roundRect(x, y, size.width, (CAP + 4) * z, [top, top, 0, 0]);
    g.fillStyle = colors.nodeTitle;
    g.fill();
    g.restore();
  }
  g.beginPath();
  g.roundRect(x + 0.5, y + 0.5, size.width - 1, size.height - 1, radii);
  g.strokeStyle = colors[edge];
  g.lineWidth = 1;
  g.stroke();
  let rowTop = y + (hat ? CAP * z : 0);
  size.rows.forEach((parts, index) => {
    drawRow(g, colors, parts, x + PAD * z, rowTop + size.heights[index] / 2, z);
    rowTop += size.heights[index];
  });
  tab(g, colors, block.category, x, y + size.height, z);
  return size;
}
