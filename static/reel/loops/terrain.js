// The World pillar's loop (12 s): sculpting and scattering.
//
// 1. The Terrain Studio has Raise / Lower chosen. Its brush ring sweeps across
//    the flat ground in the Scene View, and a hill rises under each stop.
// 2. The Scatter pane takes over, Paint becomes Stop painting, and its brush
//    paints trees, bushes, flowers and grass along a path over the hills, each
//    growing in as the brush passes.
// 3. The plants shrink away and the hills settle flat (as undo would leave
//    them), so the last frame is the first. The camera drifts gently and
//    periodically the whole time.
//
// Below 480 px wide only the Scene View shows, with the current tool named in
// a chip. Like a reel scene it holds no state: a frame comes from (context,
// time, size) alone.

import { clamp, easeInOut, expoOut, lerp, progress, rect, spring } from "../easing.js";
import * as ui from "../drawing/editor.js";
import * as terrain from "../drawing/terrain.js";

const DURATION = 12;
/** The frame reduced motion shows: the hills, fully planted. */
const STILL = 9.6;
const COMPACT_BELOW = 480;

// The hills the brush raises, in the order it visits them: x, z, radius, height.
const HILLS = Object.freeze([
  Object.freeze([-4.6, 9.5, 2.6, 3.0]),
  Object.freeze([-1.6, 11.5, 3.0, 4.2]),
  Object.freeze([0.6, 7.0, 2.1, 1.6]),
  Object.freeze([2.4, 10.5, 2.5, 2.9]),
  Object.freeze([5.0, 12.5, 3.1, 3.8]),
]);
// When things happen, in seconds.
const SCULPT = Object.freeze({ in: 0.5, first: 1.0, step: 0.7, out: 4.2 });
const SCATTER = Object.freeze({ pane: 4.8, paint: 5.1, start: 5.4, length: 3.0, stop: 8.6 });
const RESET = Object.freeze({ plants: 10.3, ground: 10.5, pane: 11.3 });
const PLANTS = 56;
const KINDS = Object.freeze(["Tree", "Bush", "Flower", "Grass"]);

/** The brush while sculpting: where it is and how visible. */
function sculptBrush(t) {
  const stops = HILLS.map(([x, z], index) => ({ x, z, at: SCULPT.first + index * SCULPT.step }));
  const enter = { x: -7.5, z: 7, at: SCULPT.in };
  const path = [enter, ...stops];
  let at = path[path.length - 1];
  for (let index = 1; index < path.length; index += 1) {
    if (t < path[index].at) {
      const p = easeInOut(progress(t, path[index - 1].at, path[index].at - path[index - 1].at));
      at = { x: lerp(path[index - 1].x, path[index].x, p), z: lerp(path[index - 1].z, path[index].z, p) };
      break;
    }
  }
  const alpha = expoOut(progress(t, SCULPT.in, 0.3)) * (1 - progress(t, SCULPT.out, 0.4));
  return { ...at, alpha };
}

/** How far each hill has risen at `t`, then sunk back for the loop. */
function grown(t) {
  const settle = 1 - easeInOut(progress(t, RESET.ground, 1.0));
  return HILLS.map((_, index) => expoOut(progress(t, SCULPT.first + index * SCULPT.step - 0.15, 1.1)) * settle);
}

/** The scatter brush's path over the hills, at `s` (0 to 1). */
function scatterPath(s) {
  return { x: lerp(-6.5, 6.5, s), z: 9.5 + 2.6 * Math.sin(s * Math.PI * 2) };
}

/** Each plant: its kind, where it stands and when it grows in (as the brush passes). */
function plants() {
  const list = [];
  for (let index = 0; index < PLANTS; index += 1) {
    const s = (index + 0.5) / PLANTS;
    const centre = scatterPath(s);
    const angle = terrain.hash(index) * Math.PI * 2;
    const reach = Math.sqrt(terrain.hash(index + 100)) * 2.3;
    list.push({
      index,
      kind: KINDS[index % KINDS.length],
      x: centre.x + Math.cos(angle) * reach,
      z: centre.z + Math.sin(angle) * reach,
      at: SCATTER.start + s * SCATTER.length + terrain.hash(index + 200) * 0.15,
      seed: terrain.hash(index + 300),
    });
  }
  return list;
}

/** The Scene View's ground, brush and plants at `t`. */
function scene(context, box, t, u) {
  const { g, colors } = context;
  const project = terrain.camera(box, 0.07 * Math.sin((2 * Math.PI * t) / DURATION));
  const amounts = grown(t);
  const height = (x, z) => terrain.heightAt(HILLS, amounts, x, z);
  g.save();
  ui.clipTo(g, box);
  terrain.ground(g, colors, box, project, height, u);

  const shrink = (plant) => 1 - expoOut(progress(t, RESET.plants + (plant.index % 8) * 0.03, 0.4));
  const standing = plants()
    .filter((plant) => t >= plant.at)
    .map((plant) => ({ ...plant, base: project(plant.x, height(plant.x, plant.z), plant.z) }))
    .sort((a, b) => b.base.depth - a.base.depth);
  for (const plant of standing) {
    const grow = clamp(spring(t - plant.at, 2.4, 0.6), 0, 1.15) * shrink(plant);
    const scale = (box.width * 0.9 * 0.62 * 1.3) / plant.base.depth;
    terrain.plant(g, colors, plant.kind, plant.base.x, plant.base.y, scale, grow, plant.seed);
  }

  const sculpt = sculptBrush(t);
  terrain.brush(g, colors, project, height, sculpt.x, sculpt.z, 2.4, 0.6, u, sculpt.alpha);
  const sweep = progress(t, SCATTER.start, SCATTER.length);
  const along = scatterPath(sweep);
  const alpha = expoOut(progress(t, SCATTER.start - 0.2, 0.3)) * (1 - progress(t, SCATTER.start + SCATTER.length, 0.3));
  terrain.brush(g, colors, project, height, along.x, along.z, 2.4, 0.3, u, alpha);
  g.restore();
}

/** Which pane the side panel shows: 1 (Scatter) from its switch until the reset. */
function scattering(t) {
  return t >= SCATTER.pane && t < RESET.pane;
}

function renderWide(context, time, size) {
  const { g, colors, labels } = context;
  const u = clamp(size.width / 840, 0.6, 1.2);
  const tabBar = 24 * u;
  const split = Math.round(size.width * 0.64);
  const viewport = ui.panel(g, colors, rect(0, 0, split, size.height), [labels.viewport], 0, u, tabBar);
  const pane = scattering(time) ? 1 : 0;
  const side = ui.panel(g, colors, rect(split, 0, size.width - split, size.height), labels.panes, pane, u, tabBar);
  scene(context, viewport, time, u);
  g.save();
  ui.clipTo(g, side);
  if (pane === 0) terrain.studio(g, colors, side, labels, 0, u);
  else terrain.scatter(g, colors, side, labels, time >= SCATTER.paint && time < SCATTER.stop, u);
  g.restore();
}

function renderCompact(context, time, size) {
  const { g, colors, labels } = context;
  const u = clamp(size.width / 360, 0.85, 1.25);
  const tabBar = 24 * u;
  const viewport = ui.panel(g, colors, rect(0, 0, size.width, size.height), [labels.viewport], 0, u, tabBar);
  scene(context, viewport, time, u);
  const label = scattering(time) ? labels.scatter : labels.tools[0];
  g.font = ui.font(500, 11.5 * u, "Inter");
  const width = g.measureText(label).width + 18 * u;
  const chip = rect(viewport.x + viewport.width - width - 8 * u, viewport.y + 8 * u, width, 22 * u);
  g.fillStyle = colors.app;
  g.beginPath();
  g.roundRect(chip.x, chip.y, chip.width, chip.height, 11 * u);
  g.fill();
  g.strokeStyle = colors.lineStrong;
  g.lineWidth = 1;
  g.stroke();
  g.fillStyle = colors.fgStrong;
  g.textBaseline = "middle";
  g.fillText(label, chip.x + 9 * u, chip.y + chip.height / 2);
}

export default Object.freeze({
  id: "terrain",
  duration: DURATION,
  still: STILL,
  render(context, time, size) {
    if (size.width < COMPACT_BELOW) renderCompact(context, time, size);
    else renderWide(context, time, size);
  },
});
