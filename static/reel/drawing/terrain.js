// Terrain in a perspective Scene View, and the panes that shape it: a
// heightfield grid shaded by its slope, the brush ring that follows the
// ground (crates/editor/src/viewport/overlays.rs: an under-stroke, the ring,
// the falloff ring and a centre dot, here in ink rather than the editor's
// accent), the built-in plants the Scatter pane paints (Tree, Bush, Flower,
// Grass: crates/core/src/terrain.rs), and the Terrain Studio and Scatter
// panes (terrain_studio/tabs.rs, editor-tools/src/terrain_tool.rs,
// scatter_pane.rs). Monochrome, in the site's tokens.
//
// Every function draws from its arguments alone, in logical pixels.

import { clamp, rect } from "../easing.js";
import { font } from "./editor.js";

// The ground's extent, in studs/4 (world units): x across, z away from the camera.
const X0 = -9;
const X1 = 9;
const Z0 = 0;
const Z1 = 15;
const COLUMNS = 32;
const ROWS = 24;
const CAMERA_HEIGHT = 6.5;
const CAMERA_BACK = 5;

/** A deterministic pseudo-random number in [0, 1) for `n` (the same every frame). */
export function hash(n) {
  const value = Math.sin(n * 12.9898 + 78.233) * 43758.5453;
  return value - Math.floor(value);
}

/** The camera for `box`, turned by `yaw` radians about the ground's middle: project(x, y, z). */
export function camera(box, yaw) {
  const focal = box.width * 0.9;
  const cos = Math.cos(yaw);
  const sin = Math.sin(yaw);
  const middle = (Z0 + Z1) / 2;
  return (x, y, z) => {
    const rx = x * cos - (z - middle) * sin;
    const rz = x * sin + (z - middle) * cos + middle;
    const depth = rz + CAMERA_BACK;
    return {
      x: box.x + box.width / 2 + (rx / depth) * focal,
      y: box.y + box.height * 0.1 + ((CAMERA_HEIGHT - y) / depth) * focal * 0.62,
      depth,
    };
  };
}

/** The ground's height at (x, z): each hill (x, z, radius, height) raised by its `grown` share. */
export function heightAt(hills, grown, x, z) {
  let height = 0;
  hills.forEach(([hx, hz, radius, peak], index) => {
    if (grown[index] <= 0) return;
    const dx = x - hx;
    const dz = z - hz;
    height += peak * grown[index] * Math.exp(-(dx * dx + dz * dz) / (radius * radius));
  });
  return height;
}

/** The ground: a grid of quads from far to near, each shaded by how it faces the light. */
export function ground(g, colors, box, project, height, u) {
  const xs = [];
  const zs = [];
  for (let i = 0; i <= COLUMNS; i += 1) xs.push(X0 + ((X1 - X0) * i) / COLUMNS);
  for (let j = 0; j <= ROWS; j += 1) zs.push(Z0 + ((Z1 - Z0) * j) / ROWS);
  const heights = zs.map((z) => xs.map((x) => height(x, z)));
  const points = zs.map((z, j) => xs.map((x, i) => project(x, heights[j][i], z)));
  const light = [-0.45, 0.85, -0.3];
  const length = Math.hypot(...light);
  g.fillStyle = colors.inset;
  g.fillRect(box.x, box.y, box.width, box.height);
  g.lineWidth = Math.max(1, 0.8 * u);
  for (let j = ROWS - 1; j >= 0; j -= 1) {
    for (let i = 0; i < COLUMNS; i += 1) {
      const dx = (xs[i + 1] - xs[i]);
      const dz = (zs[j + 1] - zs[j]);
      const slopeX = (heights[j][i + 1] - heights[j][i]) / dx;
      const slopeZ = (heights[j + 1][i] - heights[j][i]) / dz;
      const normal = [-slopeX, 1, -slopeZ];
      const facing = (normal[0] * light[0] + normal[1] * light[1] + normal[2] * light[2]) / (Math.hypot(...normal) * length);
      const corners = [points[j][i], points[j][i + 1], points[j + 1][i + 1], points[j + 1][i]];
      g.beginPath();
      corners.forEach((corner, index) => (index === 0 ? g.moveTo(corner.x, corner.y) : g.lineTo(corner.x, corner.y)));
      g.closePath();
      g.fillStyle = colors.surface;
      g.fill();
      g.save();
      g.globalAlpha *= clamp(1 - facing, 0, 1) * 0.9 + 0.05;
      g.fillStyle = colors.shade;
      g.fill();
      g.restore();
      g.save();
      g.globalAlpha *= 0.4 * clamp(1.4 - j / ROWS, 0.3, 1);
      g.strokeStyle = colors.fgWeak;
      g.stroke();
      g.restore();
    }
  }
}

/** The brush on the ground at (x, z): radius `radius`, its falloff ring, at `alpha`. */
export function brush(g, colors, project, height, x, z, radius, falloff, u, alpha) {
  if (alpha <= 0) return;
  const ring = (r) => {
    g.beginPath();
    for (let step = 0; step <= 72; step += 1) {
      const angle = (step / 72) * Math.PI * 2;
      const px = x + Math.cos(angle) * r;
      const pz = z + Math.sin(angle) * r;
      const point = project(px, height(px, pz) + 0.05, pz);
      if (step === 0) g.moveTo(point.x, point.y);
      else g.lineTo(point.x, point.y);
    }
  };
  g.save();
  g.globalAlpha *= alpha;
  g.lineJoin = "round";
  ring(radius);
  g.save();
  g.globalAlpha *= 0.45;
  g.strokeStyle = colors.app;
  g.lineWidth = 3.5 * u;
  g.stroke();
  g.restore();
  g.strokeStyle = colors.fgStrong;
  g.lineWidth = 1.6 * u;
  g.stroke();
  ring(radius * (1 - falloff));
  g.globalAlpha *= 0.55;
  g.lineWidth = 1;
  g.stroke();
  g.restore();
  g.save();
  g.globalAlpha *= alpha;
  const centre = project(x, height(x, z) + 0.05, z);
  g.fillStyle = colors.fgStrong;
  g.beginPath();
  g.arc(centre.x, centre.y, 3 * u, 0, Math.PI * 2);
  g.fill();
  g.restore();
}

/** One plant at its projected base (x, y), `scale` pixels per world unit, grown to `grow`. */
export function plant(g, colors, kind, x, y, scale, grow, seed) {
  if (grow <= 0) return;
  const s = scale * grow;
  g.save();
  g.lineCap = "round";
  if (kind === "Tree") {
    const height = (1.7 + seed * 0.6) * s;
    const width = (0.75 + seed * 0.2) * s;
    g.fillStyle = colors.fgWeak;
    g.fillRect(x - 0.06 * s, y - 0.45 * s, 0.12 * s, 0.45 * s);
    g.beginPath();
    g.moveTo(x, y - 0.3 * s - height);
    g.lineTo(x - width / 2, y - 0.3 * s);
    g.lineTo(x + width / 2, y - 0.3 * s);
    g.closePath();
    g.fillStyle = colors.fgSecondary;
    g.fill();
    g.beginPath();
    g.moveTo(x, y - 0.3 * s - height);
    g.lineTo(x + width / 2, y - 0.3 * s);
    g.lineTo(x, y - 0.3 * s);
    g.closePath();
    g.globalAlpha *= 0.35;
    g.fillStyle = colors.shade;
    g.fill();
  } else if (kind === "Bush") {
    g.fillStyle = colors.fgWeak;
    for (const [dx, dy, r] of [[-0.22, -0.2, 0.26], [0.22, -0.22, 0.24], [0, -0.38, 0.3]]) {
      g.beginPath();
      g.arc(x + dx * s, y + dy * s, r * s, 0, Math.PI * 2);
      g.fill();
    }
  } else if (kind === "Flower") {
    g.strokeStyle = colors.fgSecondary;
    g.lineWidth = Math.max(1, 0.05 * s);
    g.beginPath();
    g.moveTo(x, y);
    g.lineTo(x, y - 0.55 * s);
    g.stroke();
    g.fillStyle = colors.fgStrong;
    g.beginPath();
    g.arc(x, y - 0.6 * s, 0.12 * s, 0, Math.PI * 2);
    g.fill();
  } else {
    g.strokeStyle = colors.fgSecondary;
    g.lineWidth = Math.max(1, 0.05 * s);
    g.beginPath();
    for (const lean of [-0.18, 0, 0.16]) {
      g.moveTo(x + lean * 0.4 * s, y);
      g.lineTo(x + lean * s, y - (0.42 + Math.abs(lean)) * s);
    }
    g.stroke();
  }
  g.restore();
}

// ---------- The panes ----------

function text(g, color, value, x, y, css, align = "left") {
  g.font = css;
  g.fillStyle = color;
  g.textAlign = align;
  g.textBaseline = "middle";
  g.fillText(value, x, y);
  g.textAlign = "left";
}

function button(g, colors, box, label, u, on) {
  g.fillStyle = on ? colors.controlActive : colors.control;
  g.fillRect(box.x, box.y, box.width, box.height);
  text(g, on ? colors.fgStrong : colors.fgSecondary, label, box.x + 8 * u, box.y + box.height / 2, font(400, 11.5 * u, "Inter"));
}

/** A labelled slider: its name, a track filled to `amount`, and its value. Returns the next row's y. */
function slider(g, colors, box, y, [name, value, amount], u) {
  const pad = 8 * u;
  text(g, colors.fgSecondary, name, box.x + pad, y, font(400, 11.5 * u, "Inter"));
  const trackX = box.x + box.width * 0.36;
  const trackWidth = box.width * 0.3;
  g.fillStyle = colors.lineStrong;
  g.fillRect(trackX, y - 1, trackWidth, 2);
  g.fillStyle = colors.fgSecondary;
  g.fillRect(trackX, y - 1, trackWidth * amount, 2);
  g.beginPath();
  g.arc(trackX + trackWidth * amount, y, 4 * u, 0, Math.PI * 2);
  g.fillStyle = colors.fgStrong;
  g.fill();
  g.save();
  g.beginPath();
  g.rect(trackX + trackWidth + 8 * u, y - 10 * u, box.x + box.width - trackX - trackWidth - 8 * u, 20 * u);
  g.clip();
  text(g, colors.fg, value, trackX + trackWidth + 10 * u, y, font(400, 11 * u, "Inter"));
  g.restore();
  return y + 22 * u;
}

function heading(g, colors, box, title, u) {
  text(g, colors.fgStrong, title, box.x + 8 * u, box.y + 16 * u, font(600, 13 * u, "Inter"));
  return box.y + 36 * u;
}

/** The Terrain Studio: its title, its tabs (Sculpt chosen), the Sculpt tools and the brush. */
export function studio(g, colors, box, labels, tool, u) {
  let y = heading(g, colors, box, labels.studio, u);
  let x = box.x + 8 * u;
  labels.tabs.forEach((label, index) => {
    g.font = font(500, 11.5 * u, "Inter");
    const width = g.measureText(label).width + 16 * u;
    if (index === 0) {
      g.fillStyle = colors.controlActive;
      g.beginPath();
      g.roundRect(x, y - 11 * u, width, 22 * u, 11 * u);
      g.fill();
    }
    text(g, index === 0 ? colors.fgStrong : colors.fgWeak, label, x + 8 * u, y, font(500, 11.5 * u, "Inter"));
    x += width + 4 * u;
  });
  y += 20 * u;
  labels.tools.forEach((label, index) => {
    button(g, colors, rect(box.x + 8 * u, y, box.width - 16 * u, 22 * u), label, u, index === tool);
    y += 26 * u;
  });
  y += 12 * u;
  for (const row of labels.brush) y = slider(g, colors, box, y, row, u);
}

/** The Scatter pane: its title, the palette, Paint (or Stop painting), the brush and the items. */
export function scatter(g, colors, box, labels, painting, u) {
  let y = heading(g, colors, box, labels.scatter, u);
  const field = rect(box.x + 8 * u, y - 10 * u, box.width - 16 * u, 20 * u);
  g.fillStyle = colors.inset;
  g.fillRect(field.x, field.y, field.width, field.height);
  g.strokeStyle = colors.line;
  g.lineWidth = 1;
  g.strokeRect(field.x + 0.5, field.y + 0.5, field.width - 1, field.height - 1);
  text(g, colors.fg, labels.palette, field.x + 7 * u, y, font(400, 11.5 * u, "Inter"));
  y += 18 * u;
  button(g, colors, rect(box.x + 8 * u, y, box.width - 16 * u, 24 * u), painting ? labels.painting : labels.paint, u, painting);
  y += 40 * u;
  for (const row of labels.scatter_brush) y = slider(g, colors, box, y, row, u);
  y += 6 * u;
  for (const [name, share] of labels.items) {
    const side = 11 * u;
    g.fillStyle = colors.inset;
    g.fillRect(box.x + 8 * u, y - side / 2, side, side);
    g.strokeStyle = colors.lineStrong;
    g.strokeRect(box.x + 8.5 * u, y - side / 2 + 0.5, side - 1, side - 1);
    g.strokeStyle = colors.fgStrong;
    g.lineWidth = 1.4 * u;
    g.beginPath();
    g.moveTo(box.x + 10.5 * u, y);
    g.lineTo(box.x + 12.5 * u, y + 2.2 * u);
    g.lineTo(box.x + 16.5 * u, y - 2.4 * u);
    g.stroke();
    g.lineWidth = 1;
    text(g, colors.fg, name, box.x + 26 * u, y, font(400, 11.5 * u, "Inter"));
    text(g, colors.fgSecondary, share, box.x + box.width - 8 * u, y, font(400, 11.5 * u, "Inter"), "right");
    y += 20 * u;
  }
}
