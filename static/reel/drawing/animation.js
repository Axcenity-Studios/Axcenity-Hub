// The Animation pane in its Clips & Rigging view (crates/editor/src/animation/):
// the view buttons (chrome.rs), the clip toolbar with Record, Show Bones and
// Preview on (clip_ui.rs), the Recording status line, the character preview,
// the dope sheet (property_editor/dope_sheet.rs: a ruler in seconds, one row
// per "name · property" track, diamond keys, the playhead) and the transport
// (transport.rs: skip, step, play, loop, the clock and the frame counter).
// The editor draws its playhead in its error red and the selected key in its
// accent; here both are in ink, as the site keeps the accent for fixed uses.
//
// The character is the default humanoid's skeleton (Hips, Spine, Head,
// RightUpperArm, RightLowerArm … in assets/characters/humanoid/rig.py) drawn
// as a simple mannequin, not the engine's skinned mesh.
//
// Every function draws from its arguments alone, in logical pixels.

import { clamp, lerp, rect, spring } from "../easing.js";
import * as ui from "./editor.js";

/** The Wave clip: its key times in seconds and, per track (the rows, in order), each key's value in radians. */
export const WAVE = Object.freeze({
  length: 1.2,
  times: Object.freeze([0, 0.3, 0.6, 0.9, 1.2]),
  tracks: Object.freeze([
    Object.freeze([0.38, 2.5, 2.45, 2.5, 0.38]), // RightUpperArm: raised out from the side
    Object.freeze([0, 0.55, -0.4, 0.55, 0]), // RightLowerArm: the wave
    Object.freeze([0, -0.05, 0.04, -0.05, 0]), // Spine: a lean
    Object.freeze([0, 0.14, 0.08, 0.14, 0]), // Head: a tilt
  ]),
});

/** The clip's pose at `time` seconds (clamped to the clip), eased between keys (the "Smooth" key mode). */
export function poseAt(time) {
  const t = clamp(time, 0, WAVE.length);
  let index = 0;
  while (index < WAVE.times.length - 2 && t > WAVE.times[index + 1]) index += 1;
  const from = WAVE.times[index];
  const span = WAVE.times[index + 1] - from;
  const p = clamp((t - from) / span);
  const s = p * p * (3 - 2 * p);
  const [upper, lower, spine, head] = WAVE.tracks.map((keys) => lerp(keys[index], keys[index + 1], s));
  return { upper, lower, spine, head };
}

function along(origin, angle, length) {
  return { x: origin.x + Math.sin(angle) * length, y: origin.y + Math.cos(angle) * length };
}

/** The mannequin's joints in `box` for `pose`; `breathe` (seconds) gives an idle rise and fall. */
export function skeleton(box, pose, breathe = 0) {
  const H = Math.min(box.height * 0.8, box.width * 1.5);
  const ground = box.y + box.height * 0.91;
  const cx = box.x + box.width / 2;
  const hips = { x: cx, y: ground - H * 0.46 };
  const lift = Math.sin(breathe * 2.4) * H * 0.004;
  const lean = pose.spine;
  // Angles are measured from straight down, so "up" is π.
  const neck = along({ x: hips.x, y: hips.y + lift }, Math.PI + lean, H * 0.29);
  const across = (side, reach, drop) => ({
    x: neck.x + Math.cos(lean) * side * reach - Math.sin(lean) * drop,
    y: neck.y + Math.sin(lean) * side * reach + Math.cos(lean) * drop,
  });
  const shoulders = { right: across(-1, H * 0.1, H * 0.03), left: across(1, H * 0.1, H * 0.03) };
  const headTop = along(neck, Math.PI + lean + pose.head, H * 0.05);
  const head = along(headTop, Math.PI + lean + pose.head, H * 0.062);
  // The right arm (on the viewer's left) waves; its angle turns outwards, away from the body.
  const rightElbow = along(shoulders.right, -pose.upper, H * 0.165);
  const rightHand = along(rightElbow, -(pose.upper + pose.lower), H * 0.155);
  const leftElbow = along(shoulders.left, 0.38, H * 0.165);
  const leftHand = along(leftElbow, 0.28, H * 0.155);
  const hipsRight = { x: hips.x - H * 0.055, y: hips.y };
  const hipsLeft = { x: hips.x + H * 0.055, y: hips.y };
  return {
    H,
    ground,
    hips,
    neck,
    headTop,
    head,
    headRadius: H * 0.062,
    shoulders,
    arms: [
      [shoulders.left, leftElbow, leftHand],
      [shoulders.right, rightElbow, rightHand],
    ],
    legs: [
      [hipsRight, { x: hips.x - H * 0.062, y: hips.y + H * 0.23 }, { x: hips.x - H * 0.07, y: ground }],
      [hipsLeft, { x: hips.x + H * 0.062, y: hips.y + H * 0.23 }, { x: hips.x + H * 0.07, y: ground }],
    ],
    hand: rightHand,
  };
}

/** A limb as a rounded capsule: an outline stroke, then the fill stroke inside it. */
function limb(g, colors, points, width, u) {
  g.lineCap = "round";
  g.lineJoin = "round";
  for (const [color, extra] of [[colors.fgWeak, 2 * u], [colors.lineStrong, 0]]) {
    g.strokeStyle = color;
    g.lineWidth = width + extra;
    g.beginPath();
    points.forEach((point, index) => (index ? g.lineTo(point.x, point.y) : g.moveTo(point.x, point.y)));
    g.stroke();
  }
}

/** The character in its preview `box`, posed, with its bones over it when `bones`. */
export function character(g, colors, box, pose, u, breathe = 0, bones = true) {
  const S = skeleton(box, pose, breathe);
  const { H } = S;
  // The preview's floor: a shadow and a few grid lines.
  g.strokeStyle = colors.line;
  g.lineWidth = 1;
  g.beginPath();
  for (let line = -3; line <= 3; line += 1) {
    g.moveTo(S.hips.x + line * H * 0.12, S.ground - H * 0.05);
    g.lineTo(S.hips.x + line * H * 0.3, box.y + box.height);
  }
  g.moveTo(box.x, S.ground - H * 0.02);
  g.lineTo(box.x + box.width, S.ground - H * 0.02);
  g.stroke();
  g.fillStyle = colors.line;
  g.beginPath();
  g.ellipse(S.hips.x, S.ground, H * 0.16, H * 0.025, 0, 0, Math.PI * 2);
  g.fill();

  for (const leg of S.legs) limb(g, colors, leg, H * 0.075, u);
  // The torso: shoulders to hips.
  g.beginPath();
  g.moveTo(S.shoulders.right.x, S.shoulders.right.y);
  g.lineTo(S.shoulders.left.x, S.shoulders.left.y);
  g.lineTo(S.hips.x + H * 0.08, S.hips.y + H * 0.03);
  g.lineTo(S.hips.x - H * 0.08, S.hips.y + H * 0.03);
  g.closePath();
  g.lineJoin = "round";
  g.fillStyle = colors.lineStrong;
  g.fill();
  g.strokeStyle = colors.fgWeak;
  g.lineWidth = 1 * u;
  g.stroke();
  limb(g, colors, [S.neck, S.headTop], H * 0.05, u);
  for (const arm of S.arms) limb(g, colors, arm, H * 0.058, u);
  g.beginPath();
  g.arc(S.head.x, S.head.y, S.headRadius, 0, Math.PI * 2);
  g.fillStyle = colors.lineStrong;
  g.fill();
  g.strokeStyle = colors.fgWeak;
  g.lineWidth = 1 * u;
  g.stroke();

  if (!bones) return S;
  // Show Bones: each bone as a line, each joint as a dot.
  const chains = [[S.hips, S.neck, S.headTop, S.head], ...S.arms.map((arm) => [S.neck, ...arm]), ...S.legs.map((leg) => [S.hips, ...leg])];
  g.strokeStyle = colors.fgSecondary;
  g.lineWidth = 1.2 * u;
  g.lineCap = "round";
  for (const chain of chains) {
    g.beginPath();
    chain.forEach((point, index) => (index ? g.lineTo(point.x, point.y) : g.moveTo(point.x, point.y)));
    g.stroke();
  }
  g.fillStyle = colors.fgStrong;
  for (const chain of chains) {
    for (const point of chain) {
      g.beginPath();
      g.arc(point.x, point.y, 2 * u, 0, Math.PI * 2);
      g.fill();
    }
  }
  return S;
}

/** The pane's parts in its content box. Compact leaves out the view buttons, the toolbar and the status line. */
export function animationLayout(g, box, labels, u, compact = false) {
  const bar = compact ? 0 : 22 * u;
  const tools = compact ? 0 : 24 * u;
  const status = compact ? 0 : 18 * u;
  const transportHeight = 24 * u;
  const top = box.y + bar + tools + status;
  const transport = rect(box.x, box.y + box.height - transportHeight, box.width, transportHeight);
  const mainHeight = transport.y - top;
  const preview = rect(box.x, top, box.width * (compact ? 0.42 : 0.4), mainHeight);
  const sheet = rect(preview.x + preview.width, top, box.width - preview.width, mainHeight);
  const css = ui.font(500, 11 * u, "Inter");
  g.font = css;
  const toolY = box.y + bar + 2 * u;
  const recordWidth = g.measureText(labels.animation.record).width + 30 * u;
  const record = rect(box.x + 6 * u, toolY, recordWidth, 20 * u);
  const bonesWidth = g.measureText(labels.animation.bones).width + 18 * u;
  const bones = rect(record.x + record.width + 4 * u, toolY, bonesWidth, 20 * u);
  const previewWidth = g.measureText(labels.animation.preview).width + 30 * u;
  const previewOn = rect(bones.x + bones.width + 4 * u, toolY, previewWidth, 20 * u);
  const play = rect(transport.x + 6 * u + 2 * 22 * u, transport.y + 2 * u, 26 * u, 20 * u);
  return { bar, tools, status, preview, sheet, transport, record, bones, previewOn, play, compact };
}

/** Where the dope sheet's ruler, label column and rows are, and where a time falls on it. */
function sheetLayout(sheet, rows, u, compact) {
  const header = compact ? 0 : 20 * u;
  const ruler = 16 * u;
  const labelWidth = clamp(sheet.width * 0.32, 70 * u, 160 * u);
  const track = rect(sheet.x + labelWidth, sheet.y + header + ruler, sheet.width - labelWidth, sheet.height - header - ruler);
  const row = Math.min(22 * u, track.height / rows);
  const xAt = (time) => track.x + 10 * u + (time / WAVE.length) * (track.width - 22 * u);
  return { header, ruler, labelWidth, track, row, xAt };
}

/** A key: a diamond outlined in the sheet's colour. */
function diamond(g, colors, x, y, r, color) {
  g.beginPath();
  g.moveTo(x, y - r);
  g.lineTo(x + r, y);
  g.lineTo(x, y + r);
  g.lineTo(x - r, y);
  g.closePath();
  g.fillStyle = color;
  g.fill();
  g.strokeStyle = colors.inset;
  g.lineWidth = 1;
  g.stroke();
}

/** The transport's small glyphs, each centred on (x, y). */
function glyph(g, colors, kind, x, y, u) {
  const s = 3.6 * u;
  g.fillStyle = colors.fgSecondary;
  g.strokeStyle = colors.fgSecondary;
  g.lineWidth = 1.3 * u;
  const tri = (dir, dx) => {
    g.beginPath();
    g.moveTo(x + dx - dir * s * 0.8, y - s);
    g.lineTo(x + dx + dir * s * 0.8, y);
    g.lineTo(x + dx - dir * s * 0.8, y + s);
    g.closePath();
    g.fill();
  };
  if (kind === "start") {
    tri(-1, 1 * u);
    g.fillRect(x - s * 0.9 - 1 * u, y - s, 1.4 * u, s * 2);
  } else if (kind === "back") {
    tri(-1, 0);
  } else if (kind === "on") {
    tri(1, 0);
  } else if (kind === "end") {
    tri(1, -1 * u);
    g.fillRect(x + s * 0.9 - 0.4 * u, y - s, 1.4 * u, s * 2);
  } else if (kind === "loop") {
    g.beginPath();
    g.arc(x, y, s, 0.3, Math.PI * 1.8);
    g.stroke();
    g.beginPath();
    g.moveTo(x + s * 1.1, y - s * 0.9);
    g.lineTo(x + s * 1.1, y + s * 0.1);
    g.lineTo(x + s * 0.1, y - s * 0.1);
    g.closePath();
    g.fill();
  }
}

/**
 * The Animation pane in its content box:
 * - `playhead`: the clip time shown, in seconds
 * - `record`: Record is on (it shows the Recording status line)
 * - `keyed`: per key column, seconds since it was keyed (0 or less: not yet)
 * - `playing`: the transport is playing (Play shows Pause)
 * - `pressed`: "record" or "play", while the pointer holds it down
 * - `breathe`: seconds, for the character's idle
 * Returns the layout and the character's skeleton, for placing the pointer.
 */
export function animationPane(g, colors, box, labels, u, state, compact = false) {
  const pane = labels.animation;
  const L = animationLayout(g, box, labels, u, compact);
  const css = ui.font(500, 11 * u, "Inter");
  ui.fill(g, colors.panel, box);

  if (!compact) {
    // The view buttons, Clips & Rigging chosen, and + New.
    let x = box.x + 6 * u;
    const y = box.y + L.bar / 2;
    pane.views.forEach((label, index) => {
      g.font = css;
      const width = g.measureText(label).width + 16 * u;
      if (index === 1) ui.fill(g, colors.controlActive, rect(x, box.y + 2 * u, width, L.bar - 4 * u));
      ui.text(g, index === 1 ? colors.fgStrong : colors.fgWeak, label, x + 8 * u, y, css);
      x += width + 4 * u;
    });
    ui.text(g, colors.fgSecondary, pane.new, box.x + box.width - 8 * u, y, css, "right");
    ui.fill(g, colors.line, rect(box.x, box.y + L.bar - 1, box.width, 1));

    // The clip toolbar: Record (a dot that fills while on), Show Bones (on), Preview on Character.
    const on = state.record;
    ui.fill(g, on || state.pressed === "record" ? colors.controlActive : colors.control, L.record);
    ui.outline(g, on ? colors.lineStrong : colors.line, L.record);
    g.beginPath();
    g.arc(L.record.x + 11 * u, L.record.y + L.record.height / 2, 3.5 * u, 0, Math.PI * 2);
    g.fillStyle = on ? colors.fgStrong : colors.fgWeak;
    g.fill();
    ui.text(g, on ? colors.fgStrong : colors.fgSecondary, pane.record, L.record.x + 20 * u, L.record.y + L.record.height / 2, css);
    ui.button(g, colors, L.bones, pane.bones, u, true);
    ui.fill(g, colors.control, L.previewOn);
    ui.outline(g, colors.line, L.previewOn);
    ui.text(g, colors.fgSecondary, pane.preview, L.previewOn.x + 8 * u, L.previewOn.y + L.previewOn.height / 2, css);

    // The Recording status line.
    if (on) {
      const line = pane.recording.replace("{t}", state.playhead.toFixed(2));
      g.save();
      ui.clipTo(g, rect(box.x, box.y + L.bar + L.tools, box.width, L.status));
      ui.text(g, colors.fgSecondary, line, box.x + 8 * u, box.y + L.bar + L.tools + L.status / 2, ui.font(400, 10.5 * u, "Inter"));
      g.restore();
    }
  }

  // The preview.
  ui.fill(g, colors.inset, L.preview);
  g.save();
  ui.clipTo(g, L.preview);
  const skeletonNow = character(g, colors, L.preview, poseAt(state.playhead), u, state.breathe, true);
  g.restore();
  ui.fill(g, colors.line, rect(L.preview.x + L.preview.width - 1, L.preview.y, 1, L.preview.height));

  // The dope sheet.
  const rows = pane.rows.length;
  const S = sheetLayout(L.sheet, rows, u, compact);
  ui.fill(g, colors.inset, L.sheet);
  if (!compact) {
    let x = L.sheet.x + 6 * u;
    pane.modes.forEach((label, index) => {
      x += ui.chip(g, colors, x, L.sheet.y + S.header / 2, label, u, index === 0) + 2 * u;
    });
  }
  const rulerY = L.sheet.y + S.header;
  ui.fill(g, colors.panel, rect(L.sheet.x, rulerY, L.sheet.width, S.ruler));
  g.strokeStyle = colors.line;
  g.lineWidth = 1;
  g.beginPath();
  for (let tick = 0; tick <= WAVE.length * 10 + 0.01; tick += 1) {
    const x = Math.round(S.xAt(tick / 10)) + 0.5;
    g.moveTo(x, rulerY + S.ruler * (tick % 5 === 0 ? 0.45 : 0.7));
    g.lineTo(x, rulerY + S.ruler);
  }
  g.stroke();
  for (const second of [0, 0.5, 1]) {
    ui.text(g, colors.fgWeak, String(second), S.xAt(second) + 3 * u, rulerY + S.ruler * 0.32, ui.font(400, 9.5 * u, "Inter"));
  }
  pane.rows.forEach((label, index) => {
    const y = S.track.y + index * S.row;
    if (index % 2 === 1) {
      g.save();
      g.globalAlpha *= 0.4;
      ui.fill(g, colors.surface, rect(L.sheet.x, y, L.sheet.width, S.row));
      g.restore();
    }
    g.save();
    ui.clipTo(g, rect(L.sheet.x, y, S.labelWidth - 4 * u, S.row));
    ui.text(g, colors.fg, label, L.sheet.x + 6 * u, y + S.row / 2, ui.font(400, 10.5 * u, "Inter"));
    g.restore();
    WAVE.times.forEach((time, column) => {
      const since = state.keyed[column];
      if (since <= 0) return;
      const pop = clamp(spring(since + index * 0.03, 3, 0.5), 0, 1.4);
      const near = Math.abs(state.playhead - time) < 0.04;
      diamond(g, colors, S.xAt(time), y + S.row / 2, 4.5 * u * pop, near ? colors.fgStrong : colors.fgSecondary);
    });
  });
  ui.fill(g, colors.line, rect(S.track.x - 1, rulerY, 1, L.sheet.height - S.header));
  // The playhead: a handle on the ruler and a line down the rows.
  const head = S.xAt(state.playhead);
  ui.fill(g, colors.fgStrong, rect(head - 1 * u, rulerY, 2 * u, S.ruler + rows * S.row));
  g.beginPath();
  g.moveTo(head - 4 * u, rulerY);
  g.lineTo(head + 4 * u, rulerY);
  g.lineTo(head, rulerY + 5 * u);
  g.closePath();
  g.fillStyle = colors.fgStrong;
  g.fill();

  // The transport.
  ui.fill(g, colors.panel, L.transport);
  ui.fill(g, colors.line, rect(L.transport.x, L.transport.y, L.transport.width, 1));
  const midY = L.transport.y + L.transport.height / 2;
  let x = L.transport.x + 6 * u;
  for (const kind of ["start", "back"]) {
    glyph(g, colors, kind, x + 11 * u, midY, u);
    x += 22 * u;
  }
  ui.fill(g, state.pressed === "play" ? colors.lineStrong : colors.controlActive, L.play);
  g.fillStyle = colors.fgStrong;
  if (state.playing) {
    g.fillRect(L.play.x + L.play.width / 2 - 4 * u, midY - 4.5 * u, 2.6 * u, 9 * u);
    g.fillRect(L.play.x + L.play.width / 2 + 1.4 * u, midY - 4.5 * u, 2.6 * u, 9 * u);
  } else {
    g.beginPath();
    g.moveTo(L.play.x + L.play.width / 2 - 3.5 * u, midY - 5 * u);
    g.lineTo(L.play.x + L.play.width / 2 + 5 * u, midY);
    g.lineTo(L.play.x + L.play.width / 2 - 3.5 * u, midY + 5 * u);
    g.closePath();
    g.fill();
  }
  x = L.play.x + L.play.width + 4 * u;
  for (const kind of ["on", "end", "loop"]) {
    glyph(g, colors, kind, x + 11 * u, midY, u);
    x += 22 * u;
  }
  const mono = ui.font(400, 10.5 * u, "JetBrains Mono");
  const clock = `0:${state.playhead.toFixed(2).padStart(5, "0")}`;
  const frames = Math.round(WAVE.length * pane.fps);
  const counter = `${Math.round(state.playhead * pane.fps)}/${frames}`;
  ui.text(g, colors.fg, clock, x + 6 * u, midY, mono);
  g.font = mono;
  const seekX = x + 14 * u + g.measureText(clock).width;
  const counterWidth = g.measureText(`${frames}/${frames}`).width;
  const seekWidth = L.transport.x + L.transport.width - seekX - counterWidth - 18 * u;
  if (seekWidth > 20 * u) {
    ui.fill(g, colors.lineStrong, rect(seekX, midY - 1, seekWidth, 2));
    ui.fill(g, colors.fgSecondary, rect(seekX, midY - 1, seekWidth * (state.playhead / WAVE.length), 2));
  }
  ui.text(g, colors.fgSecondary, counter, L.transport.x + L.transport.width - 8 * u, midY, mono, "right");
  return { layout: L, skeleton: skeletonNow };
}
