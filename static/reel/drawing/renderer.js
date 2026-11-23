// The renderer wipe: the Showcase-Renderer room blocked out in grey, and the
// ray-traced capture of the same room, with a scan line between them. The
// grey room is drawn here (no graybox capture exists yet), over the capture's
// own layout: the window slits in the left wall, the sphere on its plinth, the
// tall slab, the cylinder and the light strip along the back wall. It's
// placed in the capture's pixel space (1280 × 720), so both ends line up.
//
// The capture is the 1920 px WebP derivative. Covering the Scene View, even
// pushed in, it's drawn at most ~850 CSS px wide (1700 device px at 2×), so
// it's never upscaled.
//
// Every function draws from its arguments alone, in logical pixels.

import { clamp, expoOut, progress, rect } from "../easing.js";
import * as ui from "./editor.js";

/** The capture's pixel space the room is laid out in. */
const W = 1280;
const H = 720;

/** How the capture covers `box`, pushed in by `push` (1 fits): scale and origin. */
export function cover(box, push) {
  const scale = Math.max(box.width / W, box.height / H) * push;
  return {
    scale,
    x: box.x + (box.width - W * scale) / 2,
    y: box.y + (box.height - H * scale) / 2,
  };
}

// The room's shapes, in capture pixels, each with when it rises in (seconds into the build).
const SLITS = Object.freeze([
  [60, 85, 190, 455],
  [165, 185, 205, 448],
  [258, 275, 213, 445],
  [338, 346, 222, 440],
  [408, 415, 230, 436],
]);
const BLOCKS = Object.freeze([
  // [front face x0, y0, x1, y1, top inset, rise at]
  Object.freeze([332, 422, 564, 540, 10, 0.2]), // the sphere's plinth
  Object.freeze([676, 488, 888, 530, 8, 0.3]), // the slab's plinth
  Object.freeze([733, 137, 828, 492, 6, 0.45]), // the slab
]);

function poly(g, points) {
  g.beginPath();
  points.forEach(([x, y], index) => (index ? g.lineTo(x, y) : g.moveTo(x, y)));
  g.closePath();
}

/**
 * The grey room, `build` seconds into blocking out (each shape rises from the
 * floor in turn; 1.2 or more is whole), in `box` pushed in by `push`.
 */
export function graybox(g, colors, box, u, push, build) {
  const c = cover(box, push);
  g.save();
  ui.clipTo(g, box);
  ui.fill(g, colors.inset, box);
  g.translate(c.x, c.y);
  g.scale(c.scale, c.scale);
  const hair = 1 / c.scale; // one logical pixel in capture pixels
  const edge = (alpha = 1) => {
    g.save();
    g.globalAlpha *= alpha;
    g.strokeStyle = colors.fgWeak;
    g.lineWidth = 1.2 * hair;
    g.stroke();
    g.restore();
  };

  // Walls, ceiling and floor.
  const room = expoOut(progress(build, 0, 0.5));
  g.save();
  g.globalAlpha *= room;
  g.fillStyle = colors.panel;
  poly(g, [[0, 120], [455, 180], [455, 470], [0, 495]]); // the left wall
  g.fill();
  g.fillStyle = colors.surface;
  poly(g, [[455, 180], [W, 20], [W, 470], [455, 470]]); // the back wall
  g.fill();
  g.fillStyle = colors.control;
  poly(g, [[0, 495], [455, 470], [W, 470], [W, H], [0, H]]); // the floor
  g.fill();
  g.beginPath();
  g.moveTo(0, 120);
  g.lineTo(455, 180);
  g.lineTo(W, 20);
  g.moveTo(455, 180);
  g.lineTo(455, 470);
  g.moveTo(0, 495);
  g.lineTo(455, 470);
  g.lineTo(W, 470);
  // The floor's grid, towards the far corner.
  for (let line = 0; line <= 10; line += 1) {
    g.moveTo(455 + line * 82, 470);
    g.lineTo(-500 + line * 230, H);
  }
  edge(0.8);
  // The window slits and the back wall's posts.
  g.fillStyle = colors.inset;
  for (const [x0, x1, y0, y1] of SLITS) {
    g.fillRect(x0, y0, x1 - x0, y1 - y0);
    g.beginPath();
    g.rect(x0, y0, x1 - x0, y1 - y0);
    edge(0.8);
  }
  g.fillStyle = colors.lineStrong;
  for (const [x, y0, y1] of [[525, 290, 470], [672, 288, 470], [882, 272, 470], [1170, 255, 470]]) {
    g.fillRect(x, y0, 6, y1 - y0);
  }
  // The light strip, unlit.
  g.beginPath();
  g.moveTo(565, 462);
  g.lineTo(W, 498);
  g.strokeStyle = colors.fgSecondary;
  g.lineWidth = 4;
  g.stroke();
  g.restore();

  // The shapes rise from the floor in turn.
  const rise = (at) => expoOut(progress(build, at, 0.55));
  const lifted = (amount, bottom, draw) => {
    if (amount <= 0) return;
    g.save();
    g.globalAlpha *= amount;
    g.translate(0, (1 - amount) * 40);
    g.beginPath();
    g.rect(-W, -H, W * 3, bottom + H);
    g.clip();
    draw();
    g.restore();
  };
  for (const [x0, y0, x1, y1, inset, at] of BLOCKS) {
    lifted(rise(at), y1, () => {
      g.fillStyle = colors.lineStrong;
      g.fillRect(x0, y0, x1 - x0, y1 - y0);
      g.beginPath();
      g.rect(x0, y0, x1 - x0, y1 - y0);
      edge();
      g.fillStyle = colors.fgWeak;
      poly(g, [[x0, y0], [x1, y0], [x1 - inset, y0 - inset], [x0 + inset, y0 - inset]]);
      g.fill();
      edge();
    });
  }
  // The cylinder's plinth, seen from above at an angle, then the cylinder.
  lifted(rise(0.35), 640, () => {
    g.fillStyle = colors.lineStrong;
    poly(g, [[826, 590], [1040, 628], [1040, 640], [826, 602]]);
    g.fill();
    g.fillStyle = colors.fgWeak;
    poly(g, [[826, 590], [1040, 628], [1107, 580], [900, 552]]);
    g.fill();
    edge();
  });
  lifted(rise(0.6), 590, () => {
    g.fillStyle = colors.lineStrong;
    g.beginPath();
    g.ellipse(968, 572, 68, 14, 0, 0, Math.PI);
    g.lineTo(900, 258);
    g.ellipse(968, 258, 68, 12, 0, Math.PI, 0, true);
    g.lineTo(1036, 572);
    g.fill();
    edge();
    g.fillStyle = colors.fgWeak;
    g.beginPath();
    g.ellipse(968, 258, 68, 12, 0, 0, Math.PI * 2);
    g.fill();
    edge();
  });
  // The sphere, last, settling onto its plinth.
  lifted(rise(0.75), 425, () => {
    g.beginPath();
    g.arc(449, 347, 74, 0, Math.PI * 2);
    g.fillStyle = colors.fgWeak;
    g.fill();
    edge();
    // Its wireframe: two meridians and the equator.
    g.beginPath();
    g.ellipse(449, 347, 74, 22, 0, 0, Math.PI * 2);
    g.ellipse(449, 347, 30, 74, 0, 0, Math.PI * 2);
    edge(0.7);
  });
  g.restore();
}

/** The ray-traced capture in `box`, pushed in by `push`, or nothing until it has loaded. */
export function lit(g, image, box, push) {
  if (!image) return false;
  const c = cover(box, push);
  g.save();
  ui.clipTo(g, box);
  g.drawImage(image, c.x, c.y, W * c.scale, H * c.scale);
  g.restore();
  return true;
}

/**
 * The wipe at `sweep` (0: all grey, 1: all lit): the capture left of the scan
 * line, the grey room right of it, and the line in the accent with a soft glow
 * (stacked translucent bars; canvas blur works in device pixels).
 */
export function wipe(g, colors, image, box, u, push, build, sweep) {
  const x = box.x + box.width * clamp(sweep);
  if (sweep < 1 || !image) graybox(g, colors, box, u, push, build);
  if (sweep > 0 && image) {
    g.save();
    ui.clipTo(g, rect(box.x, box.y, x - box.x, box.height));
    lit(g, image, box, push);
    g.restore();
  }
  if (sweep <= 0 || sweep >= 1) return;
  g.save();
  ui.clipTo(g, box);
  g.fillStyle = colors.accent;
  for (let step = 4; step >= 1; step -= 1) {
    g.globalAlpha = 0.07;
    g.fillRect(x - step * 5 * u, box.y, step * 5 * u, box.height);
  }
  g.globalAlpha = 1;
  g.fillRect(x - 1 * u, box.y, 2 * u, box.height);
  g.restore();
}
