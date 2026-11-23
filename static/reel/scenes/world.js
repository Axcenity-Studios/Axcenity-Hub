// Scene 5 (16–20 s): the world.
//
// 1. The bottom dock settles back and the Scene View cuts from the lit room
//    to flat ground. The pointer picks Raise / Lower in the docked Terrain
//    pane.
// 2. It brushes across the ground: the brush ring follows it, and a hill
//    rises under each stop.
// 3. The Scatter pane opens beside Terrain; the pointer chooses it, presses
//    Paint (now Stop painting) and paints along a path over the hills, where
//    trees, bushes, flowers and grass grow in behind the brush.
// 4. It drifts off. The camera turns gently the whole time.
//
// Compact mode shows the ground in its widened Scene View, the brush working
// on its own, with no pointer.

import { clamp, easeInOut, expoOut, lerp, progress, rect, spring } from "../easing.js";
import { BOTTOM_SHARE, innerOf, workspaceLayout } from "../drawing/layout.js";
import * as ui from "../drawing/editor.js";
import * as terrain from "../drawing/terrain.js";
import { pointerPath, viewWorkspace } from "./workspace.js";
import { rendererEnd } from "./renderer.js";

const START = 16;
const DURATION = 4;

// The hills the brush raises, in the order it visits them: x, z, radius, height.
const HILLS = Object.freeze([
  Object.freeze([-4.6, 9.5, 2.6, 3.0]),
  Object.freeze([-1.6, 11.5, 3.0, 4.2]),
  Object.freeze([0.6, 7.0, 2.1, 1.6]),
  Object.freeze([2.4, 10.5, 2.5, 2.9]),
  Object.freeze([5.0, 12.5, 3.1, 3.8]),
]);
const PLANTS = 44;
const KINDS = Object.freeze(["Tree", "Bush", "Flower", "Grass"]);

const T = Object.freeze({
  cut: [0.1, 0.45], // the lit room fades into flat ground
  enter: 0.15,
  tool: 0.4, // Raise / Lower is pressed
  sculpt: Object.freeze({ first: 0.8, step: 0.25 }), // the brush's stops, one per hill
  tab: 2.0, // the Scatter tab opens
  scatter: 2.2, // and is chosen
  paint: 2.45, // Paint is pressed
  path: Object.freeze([2.72, 0.75]), // the scatter brush's sweep
  gone: Object.freeze([3.55, 3.9]),
});

/** The sculpting brush's ground position at `t`: easing from hill to hill. */
function sculptAt(t) {
  const times = HILLS.map((_, index) => T.sculpt.first + index * T.sculpt.step);
  let at = HILLS[0];
  for (let index = 1; index < HILLS.length; index += 1) {
    if (t < times[index]) {
      const p = easeInOut(progress(t, times[index - 1], T.sculpt.step));
      return { x: lerp(HILLS[index - 1][0], HILLS[index][0], p), z: lerp(HILLS[index - 1][1], HILLS[index][1], p) };
    }
    at = HILLS[index];
  }
  return { x: at[0], z: at[1] };
}

/** How far each hill has risen at `t`. */
function grown(t) {
  return HILLS.map((_, index) => expoOut(progress(t, T.sculpt.first + index * T.sculpt.step - 0.05, 0.7)));
}

/** The scatter brush's path over the hills, at `s` (0 to 1). */
function pathAt(s) {
  return { x: lerp(-6.5, 6.5, s), z: 9.5 + 2.6 * Math.sin(s * Math.PI * 2) };
}

/** Each plant: its kind, where it stands and when it grows in (as the brush passes). */
function plants() {
  return Array.from({ length: PLANTS }, (_, index) => {
    const s = (index + 0.5) / PLANTS;
    const centre = pathAt(s);
    const angle = terrain.hash(index) * Math.PI * 2;
    const reach = Math.sqrt(terrain.hash(index + 100)) * 2.3;
    return {
      kind: KINDS[index % KINDS.length],
      x: centre.x + Math.cos(angle) * reach,
      z: centre.z + Math.sin(angle) * reach,
      at: T.path[0] + s * T.path[1] + terrain.hash(index + 200) * 0.1,
      seed: terrain.hash(index + 300),
    };
  });
}

/** The camera for the Scene View's `box`, turning gently with the loop's clock. */
function cameraFor(box, clock) {
  return terrain.camera(box, 0.08 * Math.sin((2 * Math.PI * clock) / 9));
}

/** The ground, the brushes and the plants at `t`, over the lit room as it fades. */
function sceneDrawer(context, u, clock, t, before) {
  const { colors } = context;
  const room = 1 - expoOut(progress(t, T.cut[0], T.cut[1]));
  return (g, box) => {
    const project = cameraFor(box, clock);
    const amounts = grown(t);
    const height = (x, z) => terrain.heightAt(HILLS, amounts, x, z);
    g.save();
    ui.clipTo(g, box);
    terrain.ground(g, colors, box, project, height, u);
    const standing = plants()
      .filter((plant) => t >= plant.at)
      .map((plant) => ({ ...plant, base: project(plant.x, height(plant.x, plant.z), plant.z) }))
      .sort((a, b) => b.base.depth - a.base.depth);
    for (const plant of standing) {
      const grow = clamp(spring(t - plant.at, 2.4, 0.6), 0, 1.15);
      const scale = (box.width * 0.9 * 0.62 * 1.3) / plant.base.depth;
      terrain.plant(g, colors, plant.kind, plant.base.x, plant.base.y, scale, grow, plant.seed);
    }
    const sculpt = sculptAt(t);
    const sculpting = expoOut(progress(t, T.sculpt.first - 0.15, 0.2)) * (1 - progress(t, T.sculpt.first + 4 * T.sculpt.step + 0.1, 0.25));
    terrain.brush(g, colors, project, height, sculpt.x, sculpt.z, 2.4, 0.6, u, sculpting);
    const along = pathAt(progress(t, T.path[0], T.path[1]));
    const painting = expoOut(progress(t, T.path[0] - 0.15, 0.2)) * (1 - progress(t, T.path[0] + T.path[1], 0.25));
    terrain.brush(g, colors, project, height, along.x, along.z, 2.4, 0.3, u, painting);
    g.restore();
    if (room > 0) {
      g.save();
      g.globalAlpha *= room;
      before(g, box);
      g.restore();
    }
  };
}

/** The ground point (x, z) where the pointer holds the brush, on screen. */
function onScreen(box, clock, t, x, z) {
  const project = cameraFor(box, clock);
  return project(x, terrain.heightAt(HILLS, grown(t), x, z), z);
}

/** The workspace's view `t` seconds into the scene. */
export function worldView(context, size, t) {
  const { g, colors, labels } = context;
  const before = rendererEnd(context, size);
  const clock = START + t;

  if (size.compact) {
    const L = workspaceLayout(size, before.bottom, 1);
    return { ...before, scene: sceneDrawer(context, L.u, clock, t, before.scene) };
  }

  const share = lerp(before.bottom, BOTTOM_SHARE, clamp(spring(t, 1.8, 0.8), 0, 1.2));
  const L = workspaceLayout(size, share);
  const u = L.u;
  const sceneBox = innerOf(L.scene, L.tabBar);
  const sideBox = innerOf(L.properties, L.tabBar);
  const sideTabs = [labels.tabs.properties[1], labels.terrain_studio.scatter];
  const tabs = ui.tabBoxes(g, L.properties, sideTabs, u, L.tabBar);
  const scattering = t >= T.scatter + 0.03;
  const painting = t >= T.paint + 0.03;
  const paint = rect(sideBox.x + 8 * u, sideBox.y + 54 * u, sideBox.width - 16 * u, 24 * u);
  // The Properties window floats over this column's right edge, so the pointer
  // aims at the left of each control there.
  const leftOf = (box) => ({ x: box.x + Math.min(box.width / 2, 34 * u), y: box.y + box.height / 2 });
  const tool = leftOf(ui.terrainTool(sideBox, 0, u));
  const stop = (point, at) => ({ x: point.x, y: point.y, at });
  const hill = (index) => onScreen(sceneBox, clock, t, HILLS[index][0], HILLS[index][1]);
  const lastHill = T.sculpt.first + (HILLS.length - 1) * T.sculpt.step;
  const start = pathAt(0);
  const end = pathAt(1);
  let tip;
  if (t >= T.sculpt.first && t < lastHill) {
    const at = sculptAt(t);
    const point = onScreen(sceneBox, clock, t, at.x, at.z);
    tip = { x: point.x, y: point.y, pressed: true, alpha: 1 };
  } else if (t >= T.path[0] && t < T.path[0] + T.path[1]) {
    const at = pathAt(progress(t, T.path[0], T.path[1]));
    const point = onScreen(sceneBox, clock, t, at.x, at.z);
    tip = { x: point.x, y: point.y, pressed: true, alpha: 1 };
  } else {
    tip = pointerPath(
      t,
      [
        stop({ x: L.stage.x + L.stage.width * 0.95, y: L.stage.y + L.stage.height + 50 * u }, T.enter),
        stop(tool, T.tool),
        stop(tool, T.tool + 0.1),
        stop(hill(0), T.sculpt.first),
        stop(hill(HILLS.length - 1), lastHill),
        stop(leftOf(tabs[1]), T.scatter),
        stop(leftOf(tabs[1]), T.scatter + 0.08),
        stop(leftOf(paint), T.paint),
        stop(leftOf(paint), T.paint + 0.08),
        stop(onScreen(sceneBox, clock, t, start.x, start.z), T.path[0]),
        stop(onScreen(sceneBox, clock, t, end.x, end.z), T.path[0] + T.path[1]),
        stop({ x: L.stage.x + L.stage.width * 0.95, y: L.stage.y + L.stage.height + 40 * u }, T.gone[1]),
      ],
      [
        [T.tool, T.tool + 0.08],
        [T.scatter, T.scatter + 0.07],
        [T.paint, T.paint + 0.07],
      ],
      T.gone
    );
  }
  return {
    ...before,
    bottom: share,
    scene: sceneDrawer(context, u, clock, t, before.scene),
    terrainTool: t >= T.tool + 0.03 ? 0 : -1,
    sideTabs: t >= T.tab ? sideTabs : null,
    sideTab: scattering ? 1 : 0,
    side: scattering ? (inner, box) => terrain.scatter(inner, colors, box, labels.terrain_studio, painting, u) : null,
    pointer: tip,
  };
}

/** How the scene leaves the workspace: the planted hills, the Scatter pane still painting. */
export function worldEnd(context, size) {
  return { ...worldView(context, size, DURATION), pointer: null };
}

export default Object.freeze({
  id: "world",
  start: START,
  duration: DURATION,
  render(context, time, size) {
    viewWorkspace(context, size, START + time, worldView(context, size, time));
  },
});
