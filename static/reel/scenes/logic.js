// Scene 6 (20–24 s): logic.
//
// 1. A Script tab opens beside the Scene View (layout.rs sync_scripts) in its
//    Graph view: a When Touched node for the Pad pops in, then Spawn Decal.
// 2. The pointer drags a wire from When Touched's exec pin to Spawn Decal's.
// 3. The Luau the blocks translate to types out below the graph, in the
//    editor's syntax colours.
// 4. A pulse runs along the wire, as when the Pad is touched, and Spawn
//    Decal lights up. The outro then takes this frame away.
//
// Compact mode shows the graph alone in its widened Scene place, with no
// pointer; the Script tab takes the Toolbox tab's place, as four don't fit.

import { clamp, easeInOut, expoOut, progress, rect, spring } from "../easing.js";
import { innerOf, workspaceLayout } from "../drawing/layout.js";
import * as ui from "../drawing/editor.js";
import * as blocks from "../drawing/blocks.js";
import { code, length } from "../drawing/code.js";
import { pointerPath, viewWorkspace } from "./workspace.js";
import { compactTabs as animationTabs } from "./animation.js";
import { worldEnd } from "./world.js";

const START = 20;
const DURATION = 4;

const T = Object.freeze({
  open: 0.15, // the Script tab opens
  fade: [0.15, 0.3], // the ground gives way to the graph
  nodes: Object.freeze([0.5, 0.8]),
  enter: 0.75,
  grab: 1.1, // the pointer takes the exec pin
  wire: Object.freeze([1.15, 0.5]), // and drags the wire across
  gone: Object.freeze([1.85, 2.3]),
  type: Object.freeze([1.7, 1.6]),
  pulse: Object.freeze([3.15, 0.6]),
});

/** The script tab's parts: the view switch, the graph, the "Luau" strip and the code. */
function scriptLayout(box, u, compact) {
  const bar = 24 * u;
  const rest = box.height - bar;
  const graphHeight = compact ? rest : rest * 0.55;
  const graph = rect(box.x, box.y + bar, box.width, graphHeight);
  const strip = rect(box.x, graph.y + graph.height, box.width, compact ? 0 : 18 * u);
  const codeBox = rect(box.x, strip.y + strip.height, box.width, box.y + box.height - strip.y - strip.height);
  return { bar, graph, strip, code: codeBox };
}

/** Where the two nodes go in `body`, and the zoom that fits them (as the Logic loop places them). */
function arrange(g, nodes, body, u) {
  const [touched, decal] = nodes.map((node) => blocks.nodeSize(g, node, 1));
  const pad = 14 * u;
  const gap = 46;
  const z = Math.max(0.05, Math.min(
    1.05 * u,
    (body.width - pad * 2) / (touched.width + gap + decal.width),
    (body.height - pad * 2) / Math.max(touched.height, decal.height)
  ));
  const width = (touched.width + gap + decal.width) * z;
  const x = body.x + (body.width - width) / 2;
  const top = body.y + (body.height - decal.height * z) / 2;
  return { z, at: [{ x, y: top + 8 * z }, { x: x + (touched.width + gap) * z, y: top }] };
}

/** The wire's two ends: When Touched's exec out and Spawn Decal's exec in. */
function ends(g, nodes, place) {
  return {
    from: blocks.pinAt(g, nodes[0], place.at[0].x, place.at[0].y, place.z, "out", 0),
    to: blocks.pinAt(g, nodes[1], place.at[1].x, place.at[1].y, place.z, "in", 0),
  };
}

/** The script tab's content at `t`, over the planted ground as it fades. */
function sceneDrawer(context, u, t, before, compact) {
  const { colors, labels } = context;
  const nodes = labels.logic.nodes;
  const shown = expoOut(progress(t, T.fade[0], T.fade[1]));
  return (g, box) => {
    if (shown < 1) before(g, box);
    if (shown <= 0) return;
    g.save();
    g.globalAlpha *= shown;
    const L = scriptLayout(box, u, compact);
    ui.fill(g, colors.panel, box);
    // The view switch: Code, Blocks, Graph (chosen).
    let x = box.x + 6 * u;
    labels.script.views.forEach((label, index) => {
      x += ui.chip(g, colors, x, box.y + L.bar / 2, label, u, index === 2) + 2 * u;
    });
    blocks.grid(g, colors, L.graph, u);
    const place = arrange(g, nodes, L.graph, u);
    const { from, to } = ends(g, nodes, place);
    const drawn = easeInOut(progress(t, T.wire[0], T.wire[1]));
    const wired = drawn >= 1;
    const travel = progress(t, T.pulse[0], T.pulse[1]);
    const glow = t >= T.pulse[0] + T.pulse[1] * 0.85 ? 1 - progress(t, T.pulse[0] + T.pulse[1] + 0.2, 0.6) : 0;
    g.save();
    ui.clipTo(g, L.graph);
    nodes.forEach((node, index) => {
      const since = t - T.nodes[index];
      if (since <= 0) return;
      const rise = (1 - spring(since, 2.6, 0.6)) * 14 * place.z;
      g.save();
      g.globalAlpha *= expoOut(progress(since, 0, 0.35));
      const wires = wired ? (index === 0 ? ["out:0"] : ["in:0"]) : [];
      blocks.drawNode(g, colors, node, place.at[index].x, place.at[index].y + rise, place.z, wires, index === 1 ? glow : 0);
      g.restore();
    });
    if (drawn > 0) {
      blocks.wire(g, colors, from, to, place.z, drawn);
      if (travel > 0 && travel < 1) blocks.pulse(g, colors, from, to, place.z, easeInOut(travel), Math.sin(Math.PI * travel));
    }
    g.restore();
    if (!compact) {
      ui.fill(g, colors.app, L.strip);
      ui.fill(g, colors.line, rect(L.strip.x, L.strip.y, L.strip.width, 1));
      ui.text(g, colors.fgSecondary, labels.logic.code, L.strip.x + 8 * u, L.strip.y + L.strip.height / 2, ui.font(600, 11 * u, "Inter"));
      ui.fill(g, colors.inset, L.code);
      const total = length(labels.logic.lines);
      const typed = progress(t, T.type[0], T.type[1]);
      const fontSize = clamp(10.5 * u, 8.5, 13);
      g.save();
      ui.clipTo(g, L.code);
      code(g, colors, rect(L.code.x + 4 * u, L.code.y - fontSize * 0.6, L.code.width - 8 * u, L.code.height + fontSize * 0.6), labels.logic.lines, {
        size: fontSize,
        chars: Math.floor(typed * total),
        caret: typed > 0 && (typed < 1 || Math.floor(t * 2) % 2 === 0),
      });
      g.restore();
    }
    g.restore();
  };
}

/** The workspace's view `t` seconds into the scene. */
export function logicView(context, size, t) {
  const { g, labels } = context;
  const before = worldEnd(context, size);
  const open = t >= T.open;

  if (size.compact) {
    const L = workspaceLayout(size, before.bottom, 1);
    return {
      ...before,
      // Four tabs don't fit a phone's dock: the Script tab takes the Toolbox's place.
      sceneTabs: open ? [...animationTabs(labels).filter((tab) => tab !== labels.toolbox.button), labels.script.tab] : before.sceneTabs,
      sceneTab: open ? 2 : 0,
      scene: sceneDrawer(context, L.u, t, before.scene, true),
    };
  }

  const L = workspaceLayout(size, before.bottom);
  const u = L.u;
  const sceneBox = innerOf(L.scene, L.tabBar);
  const place = arrange(g, labels.logic.nodes, scriptLayout(sceneBox, u, false).graph, u);
  const { from, to } = ends(g, labels.logic.nodes, place);
  let tip;
  if (t >= T.wire[0] && t < T.wire[0] + T.wire[1]) {
    // Dragging: the pointer holds the wire's loose end.
    const at = blocks.wirePoint(from, to, place.z, easeInOut(progress(t, T.wire[0], T.wire[1])));
    tip = { x: at.x, y: at.y, pressed: true, alpha: 1 };
  } else {
    tip = pointerPath(
      t,
      [
        { x: sceneBox.x + sceneBox.width * 0.3, y: L.stage.y + L.stage.height + 50 * u, at: T.enter },
        { ...from, at: T.grab },
        { ...from, at: T.wire[0] },
        { ...to, at: T.wire[0] + T.wire[1] },
        { ...to, at: T.gone[0] },
        { x: to.x + 50 * u, y: to.y + 80 * u, at: T.gone[1] },
      ],
      [[T.grab, T.wire[0] + T.wire[1] + 0.04]],
      T.gone
    );
  }
  return {
    ...before,
    sceneTabs: open ? [...labels.tabs.scene, labels.script.tab] : null,
    sceneTab: open ? 3 : 0,
    scene: sceneDrawer(context, u, t, before.scene, false),
    pointer: tip,
  };
}

/** The scene's last frame, for the outro to take away. */
export function logicEnd(context, size) {
  return logicView(context, size, DURATION);
}

export default Object.freeze({
  id: "logic",
  start: START,
  duration: DURATION,
  render(context, time, size) {
    viewWorkspace(context, size, START + time, logicView(context, size, time));
  },
});
