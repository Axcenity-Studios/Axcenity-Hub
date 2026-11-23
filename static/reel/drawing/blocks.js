// The block editor's Graph view, drawn on the canvas: its grid, nodes with
// their category headers, rows, value boxes and pins, and the wires between
// them. Styled after crates/editor/src/block_editor/graph.rs (node shape and
// rows) and the shared canvas, crates/editor-node-graph/src/canvas.rs (grid,
// exec and value pins, wires). The chrome is the site's tokens; the header
// hues and pin types are the editor's own content colours, the same in both
// schemes as in the editor.
//
// Every function draws from its arguments alone, in logical pixels; `z` is
// the graph's zoom (1 is the editor's own size).

import { rect } from "../easing.js";
import { font } from "./editor.js";

/** The node's measurements at zoom 1 (graph.rs and editor-node-graph/src/lib.rs). */
export const HEADER = 28;
export const ROW = 26;
export const MIN_WIDTH = 130;
const PIN_RADIUS = 5;
const PIN_INSET = 11; // a pin's centre, in from the node's edge
const LABEL_INSET = 22; // where a row's label starts
const MIDDLE_GAP = 24; // between a row's input side and its output side
const NAME_GAP = 6;
const CORNER = 6;
const GRID = 32;

const HUES = Object.freeze({ events: "nodeEvents", looks: "nodeLooks" });
const PINS = Object.freeze({
  object: "pinObject",
  any: "pinAny",
  text: "pinText",
  vector: "pinVector",
  number: "pinNumber",
});

const label = (z) => font(400, 12 * z, "Inter");
const value = (z) => font(400, 11.5 * z, "Inter");

/** The canvas: its background and grid lines every 32 units, moving with `offset`. */
export function grid(g, colors, box, z, offset = 0) {
  g.fillStyle = colors.inset;
  g.fillRect(box.x, box.y, box.width, box.height);
  g.save();
  g.beginPath();
  g.rect(box.x, box.y, box.width, box.height);
  g.clip();
  g.strokeStyle = colors.fgStrong;
  g.globalAlpha *= 0.06;
  g.lineWidth = 1;
  const step = GRID * z;
  const shift = ((offset % step) + step) % step;
  g.beginPath();
  for (let x = box.x - shift; x < box.x + box.width; x += step) {
    g.moveTo(Math.round(x) + 0.5, box.y);
    g.lineTo(Math.round(x) + 0.5, box.y + box.height);
  }
  for (let y = box.y - shift; y < box.y + box.height; y += step) {
    g.moveTo(box.x, Math.round(y) + 0.5);
    g.lineTo(box.x + box.width, Math.round(y) + 0.5);
  }
  g.stroke();
  g.restore();
}

function textWidth(g, css, text) {
  g.font = css;
  return text ? g.measureText(text).width : 0;
}

/** How wide a row's value box is: its text, padded, with room for a chevron on a dropdown. */
function valueWidth(g, row, z) {
  if (!row[1]) return 0;
  const dropdown = row[2] === "object" || row[3] === "field";
  return textWidth(g, value(z), row[1]) + (dropdown ? 26 : 14) * z;
}

/** A node's width and height at zoom `z`: wide enough for its widest row, at least MIN_WIDTH. */
export function nodeSize(g, node, z) {
  const rows = Math.max(node.rows.length, node.outputs.length);
  let width = MIN_WIDTH * z;
  for (let index = 0; index < rows; index += 1) {
    const row = node.rows[index];
    const output = node.outputs[index];
    let left = 0;
    if (row) {
      left = LABEL_INSET * z + textWidth(g, label(z), row[0]);
      if (row[1]) left += NAME_GAP * z + valueWidth(g, row, z);
    }
    const right = output && output[0] ? textWidth(g, label(z), output[0]) + LABEL_INSET * z : PIN_INSET * z;
    width = Math.max(width, left + MIDDLE_GAP * z + right);
  }
  return { width, height: (HEADER + 2 + rows * ROW + 8) * z };
}

function roundedTop(g, box, radius) {
  g.beginPath();
  g.moveTo(box.x, box.y + box.height);
  g.lineTo(box.x, box.y + radius);
  g.arcTo(box.x, box.y, box.x + radius, box.y, radius);
  g.lineTo(box.x + box.width - radius, box.y);
  g.arcTo(box.x + box.width, box.y, box.x + box.width, box.y + radius, radius);
  g.lineTo(box.x + box.width, box.y + box.height);
  g.closePath();
}

/** Where a node drawn at (x, y) has pin `index` on `side` ("in" or "out"), as drawNode places it. */
export function pinAt(g, node, x, y, z, side, index) {
  const middle = y + (HEADER + 2 + ROW * index + ROW / 2) * z;
  if (side === "in") return { x: x + PIN_INSET * z, y: middle };
  return { x: x + nodeSize(g, node, z).width - PIN_INSET * z, y: middle };
}

/** An exec pin: the editor's arrow, filled when it's wired. */
export function execPin(g, colors, x, y, z, wired) {
  const points = [[-5, -6], [1, -6], [6, 0], [1, 6], [-5, 6]];
  g.beginPath();
  points.forEach(([px, py], index) => {
    if (index === 0) g.moveTo(x + px * z, y + py * z);
    else g.lineTo(x + px * z, y + py * z);
  });
  g.closePath();
  if (wired) {
    g.fillStyle = colors.fgSecondary;
    g.fill();
  }
  g.strokeStyle = colors.fgSecondary;
  g.lineWidth = 1.5 * Math.max(z, 0.7);
  g.lineJoin = "round";
  g.stroke();
}

/** A value pin: a circle in its type's colour, filled when wired, a ring on the node body when not. */
export function valuePin(g, colors, x, y, z, type, wired) {
  const color = colors[PINS[type]] || colors.pinAny;
  g.beginPath();
  g.arc(x, y, PIN_RADIUS * z, 0, Math.PI * 2);
  g.fillStyle = wired ? color : colors.surface;
  g.fill();
  if (!wired) {
    g.strokeStyle = color;
    g.lineWidth = 1.5 * Math.max(z, 0.7);
    g.stroke();
  }
}

function pin(g, colors, x, y, z, type, wired) {
  if (type === "exec") execPin(g, colors, x, y, z, wired);
  else if (type) valuePin(g, colors, x, y, z, type, wired);
}

function valueBox(g, colors, box, text, z, dropdown) {
  g.fillStyle = colors.inset;
  g.fillRect(box.x, box.y, box.width, box.height);
  g.strokeStyle = colors.line;
  g.lineWidth = 1;
  g.strokeRect(box.x + 0.5, box.y + 0.5, box.width - 1, box.height - 1);
  g.font = value(z);
  g.fillStyle = colors.fg;
  g.textBaseline = "middle";
  g.fillText(text, box.x + 6 * z, box.y + box.height / 2);
  if (!dropdown) return;
  const cx = box.x + box.width - 10 * z;
  const cy = box.y + box.height / 2;
  g.fillStyle = colors.fgSecondary;
  g.beginPath();
  g.moveTo(cx - 3.5 * z, cy - 2 * z);
  g.lineTo(cx + 3.5 * z, cy - 2 * z);
  g.lineTo(cx, cy + 2.5 * z);
  g.closePath();
  g.fill();
}

/**
 * One node at (x, y): its shadow, body, header in its category's hue with the
 * white title, then each row (an input's pin, label and value box; an
 * output's label and pin). `wired` lists the wired pins as "in:<row>" and
 * "out:<row>"; `glow` (0 to 1) brightens its outline. Returns each row's input
 * and output pin positions.
 */
export function drawNode(g, colors, node, x, y, z, wired = [], glow = 0) {
  const size = nodeSize(g, node, z);
  const box = rect(x, y, size.width, size.height);
  const corner = CORNER * z;
  g.save();
  g.globalAlpha *= 0.27;
  g.fillStyle = colors.shade;
  g.beginPath();
  g.roundRect(box.x, box.y + 3 * z, box.width, box.height, corner);
  g.fill();
  g.restore();
  g.fillStyle = colors.surface;
  g.beginPath();
  g.roundRect(box.x, box.y, box.width, box.height, corner);
  g.fill();
  roundedTop(g, rect(box.x, box.y, box.width, HEADER * z), corner);
  g.fillStyle = colors[HUES[node.hue]];
  g.fill();
  g.font = font(600, 13 * z, "Inter");
  g.fillStyle = colors.nodeTitle;
  g.textBaseline = "middle";
  g.textAlign = "left";
  g.fillText(node.title, box.x + 10 * z, box.y + (HEADER * z) / 2);

  const pins = { inputs: [], outputs: [] };
  const rows = Math.max(node.rows.length, node.outputs.length);
  for (let index = 0; index < rows; index += 1) {
    const middle = box.y + (HEADER + 2 + ROW * index + ROW / 2) * z;
    const row = node.rows[index];
    if (row) {
      const [name, text, type, side] = row;
      const at = { x: box.x + PIN_INSET * z, y: middle };
      if (side !== "field") pin(g, colors, at.x, at.y, z, type, side === "wired" || wired.includes(`in:${index}`));
      pins.inputs.push(at);
      let labelX = box.x + LABEL_INSET * z;
      if (name) {
        g.font = label(z);
        g.fillStyle = colors.fg;
        g.fillText(name, labelX, middle);
        labelX += g.measureText(name).width + NAME_GAP * z;
      }
      if (text) {
        const width = valueWidth(g, row, z);
        valueBox(g, colors, rect(labelX, middle - 9 * z, width, 18 * z), text, z, type === "object" || side === "field");
      }
    } else {
      pins.inputs.push(null);
    }
    const output = node.outputs[index];
    if (output) {
      const [name, type] = output;
      const at = { x: box.x + box.width - PIN_INSET * z, y: middle };
      pin(g, colors, at.x, at.y, z, type, wired.includes(`out:${index}`));
      pins.outputs.push(at);
      if (name) {
        g.font = label(z);
        g.fillStyle = colors.fg;
        g.textAlign = "right";
        g.fillText(name, box.x + box.width - LABEL_INSET * z, middle);
        g.textAlign = "left";
      }
    } else {
      pins.outputs.push(null);
    }
  }

  g.lineWidth = 1;
  g.strokeStyle = colors.lineStrong;
  g.beginPath();
  g.roundRect(box.x + 0.5, box.y + 0.5, box.width - 1, box.height - 1, corner);
  g.stroke();
  if (glow > 0) {
    g.save();
    g.globalAlpha *= glow;
    g.strokeStyle = colors.fgStrong;
    g.lineWidth = 2 * z;
    g.beginPath();
    g.roundRect(box.x, box.y, box.width, box.height, corner);
    g.stroke();
    g.restore();
  }
  return pins;
}

/** The point `t` (0 to 1) along a wire from `from` to `to`: a curve that leaves and arrives level. */
export function wirePoint(from, to, z, t) {
  const reach = Math.max(Math.abs(to.x - from.x) * 0.5, 40 * z);
  const c1 = { x: from.x + reach, y: from.y };
  const c2 = { x: to.x - reach, y: to.y };
  const s = 1 - t;
  return {
    x: s * s * s * from.x + 3 * s * s * t * c1.x + 3 * s * t * t * c2.x + t * t * t * to.x,
    y: s * s * s * from.y + 3 * s * s * t * c1.y + 3 * s * t * t * c2.y + t * t * t * to.y,
  };
}

/**
 * An exec wire drawn `amount` of the way from `from` to `to` (2.5 wide, as the
 * editor draws exec wires), over a soft glow of the same colour.
 */
export function wire(g, colors, from, to, z, amount = 1) {
  if (amount <= 0) return;
  const steps = 40;
  const trace = () => {
    g.beginPath();
    for (let step = 0; step <= steps; step += 1) {
      const point = wirePoint(from, to, z, (step / steps) * amount);
      if (step === 0) g.moveTo(point.x, point.y);
      else g.lineTo(point.x, point.y);
    }
  };
  g.save();
  g.lineCap = "round";
  g.lineJoin = "round";
  g.strokeStyle = colors.fgSecondary;
  for (const [width, alpha] of [[10, 0.06], [6, 0.1]]) {
    g.save();
    g.globalAlpha *= alpha;
    g.lineWidth = width * z;
    trace();
    g.stroke();
    g.restore();
  }
  g.lineWidth = 2.5 * z;
  trace();
  g.stroke();
  g.restore();
}

/** A pulse at `t` along a wire: a bright dot in a soft halo, as the event fires. */
export function pulse(g, colors, from, to, z, t, strength) {
  if (strength <= 0) return;
  const point = wirePoint(from, to, z, t);
  g.save();
  g.fillStyle = colors.fgStrong;
  const base = g.globalAlpha;
  for (const [radius, alpha] of [[11, 0.08], [7, 0.16], [3.5, 1]]) {
    g.globalAlpha = base * strength * alpha;
    g.beginPath();
    g.arc(point.x, point.y, radius * z, 0, Math.PI * 2);
    g.fill();
  }
  g.restore();
}
