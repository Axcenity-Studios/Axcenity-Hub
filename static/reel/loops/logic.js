// The Logic pillar's loop (12 s): the block editor's Graph view and the Luau
// it becomes.
//
// 1. A When Touched node for the Pad pops in, then a Spawn Decal node.
// 2. An exec wire draws from one to the other.
// 3. The Luau the blocks translate to types out below them, in the editor's
//    syntax colours.
// 4. A pulse runs along the wire, as when the Pad is touched, and Spawn
//    Decal lights up.
// 5. Everything fades, leaving the empty panels the loop starts from.
//
// Below 480 px wide it shows one panel at a time (the graph, then the code,
// from the Connect call down) at a size that stays readable. Like a reel
// scene it holds no state: a frame comes from (context, time, size) alone.

import { clamp, easeInOut, expoOut, progress, rect, spring } from "../easing.js";
import * as ui from "../drawing/editor.js";
import * as blocks from "../drawing/blocks.js";
import { code, length } from "../drawing/code.js";

const DURATION = 12;
/** The frame reduced motion shows: both nodes wired, the code typed. */
const STILL = 9.5;
/** Below this width the loop shows one panel at a time. */
const COMPACT_BELOW = 480;

// When things happen, in seconds. The compact timings are for one panel at a time.
const WIDE = Object.freeze({
  nodes: [0.3, 0.75],
  wire: [1.5, 0.8],
  type: [2.4, 5.0],
  pulse: [7.6, 1.1],
  out: [10.6, 1.0],
});
const COMPACT = Object.freeze({
  nodes: [0.3, 0.75],
  wire: [1.5, 0.8],
  pulse: [3.0, 1.1],
  toCode: [4.6, 0.6],
  type: [5.4, 3.6],
  toGraph: [11.0, 0.8],
});

/** Where the two nodes go in `body`, and the zoom that fits them. */
function arrange(g, nodes, body, u) {
  const [touched, decal] = nodes.map((node) => blocks.nodeSize(g, node, 1));
  const pad = 14 * u;
  const gap = 34;
  const z = Math.max(0.05, Math.min(
    1.15 * u,
    (body.width - pad * 2) / (touched.width + gap + decal.width),
    (body.height - pad * 2) / Math.max(touched.height, decal.height)
  ));
  const width = (touched.width + gap + decal.width) * z;
  const x = body.x + (body.width - width) / 2;
  const top = body.y + (body.height - decal.height * z) / 2;
  return {
    z,
    at: [
      { x, y: top + 8 * z },
      { x: x + (touched.width + gap) * z, y: top },
    ],
  };
}

/** The graph at `time`: the nodes popping in, the wire drawing, the pulse. */
function drawGraph(context, body, u, time, timing) {
  const { g, colors, labels, layer } = context;
  const { z, at } = arrange(g, labels.nodes, body, u);
  const drawn = progress(time, timing.wire[0], timing.wire[1]);
  const wired = drawn >= 1;
  const travel = progress(time, timing.pulse[0], timing.pulse[1]);
  const glow = time >= timing.pulse[0] + timing.pulse[1] * 0.85 ? 1 - progress(time, timing.pulse[0] + timing.pulse[1], 0.8) : 0;
  const pins = [];
  labels.nodes.forEach((node, index) => {
    const since = time - timing.nodes[index];
    if (since <= 0) return;
    const rise = (1 - spring(since, 2.6, 0.6)) * 14 * z;
    layer(expoOut(progress(since, 0, 0.35)), (inside) => {
      const wires = wired ? (index === 0 ? ["out:0"] : ["in:0"]) : [];
      pins[index] = blocks.drawNode(inside.g, colors, node, at[index].x, at[index].y + rise, z, wires, index === 1 ? glow : 0);
    });
  });
  if (pins[0] && pins[1] && drawn > 0) {
    const from = pins[0].outputs[0];
    const to = pins[1].inputs[0];
    blocks.wire(g, colors, from, to, z, easeInOut(drawn));
    if (travel > 0 && travel < 1) blocks.pulse(g, colors, from, to, z, easeInOut(travel), Math.sin(Math.PI * travel));
  }
}

/** How much of the code has been typed at `time`, and whether the caret shows. */
function typing(time, lines, timing) {
  const total = length(lines);
  const typed = progress(time, timing.type[0], timing.type[1]);
  const busy = typed > 0 && typed < 1;
  return { chars: Math.floor(typed * total), caret: typed > 0 && (busy || Math.floor(time * 2) % 2 === 0) };
}

function renderWide(context, time, size) {
  const { g, colors, labels, layer } = context;
  const u = clamp(size.width / 760, 0.6, 1.3);
  const tabBar = 24 * u;
  const split = Math.round(size.height * 0.5);
  const graphBody = ui.panel(g, colors, rect(0, 0, size.width, split), [labels.graph], 0, u, tabBar);
  const codeBody = ui.panel(g, colors, rect(0, split, size.width, size.height - split), [labels.code], 0, u, tabBar);
  blocks.grid(g, colors, graphBody, u);
  g.fillStyle = colors.inset;
  g.fillRect(codeBody.x, codeBody.y, codeBody.width, codeBody.height);

  const fade = 1 - progress(time, WIDE.out[0], WIDE.out[1]);
  const draw = (inside) => {
    drawGraph(inside, graphBody, u, time, WIDE);
    const { chars, caret } = typing(time, labels.lines, WIDE);
    const fontSize = clamp(11 * u, 8.5, 13);
    code(inside.g, colors, rect(codeBody.x + 4 * u, codeBody.y - fontSize * 0.7, codeBody.width - 8 * u, codeBody.height + fontSize * 0.7), labels.lines, {
      size: fontSize,
      chars,
      caret,
    });
  };
  if (fade < 1) layer(fade, draw);
  else draw(context);
}

function renderCompact(context, time, size) {
  const { g, colors, labels, layer } = context;
  const u = clamp(size.width / 330, 0.85, 1.3);
  const tabBar = 24 * u;
  const frame = rect(0, 0, size.width, size.height);
  const toCode = expoOut(progress(time, COMPACT.toCode[0], COMPACT.toCode[1]));
  const toGraph = expoOut(progress(time, COMPACT.toGraph[0], COMPACT.toGraph[1]));
  const codeShare = toCode * (1 - toGraph);

  if (codeShare < 1) {
    const body = ui.panel(g, colors, frame, [labels.graph, labels.code], 0, u, tabBar);
    blocks.grid(g, colors, body, u);
    if (time < COMPACT.toCode[0] + COMPACT.toCode[1]) {
      layer(1 - codeShare, (inside) => drawGraph(inside, body, u, time, COMPACT));
    }
  }
  if (codeShare > 0) {
    layer(codeShare, (inside) => {
      const body = ui.panel(inside.g, colors, frame, [labels.graph, labels.code], 1, u, tabBar);
      inside.g.fillStyle = colors.inset;
      inside.g.fillRect(body.x, body.y, body.width, body.height);
      const lines = labels.lines.slice(labels.compact_from);
      const { chars, caret } = typing(time, lines, COMPACT);
      code(inside.g, colors, rect(body.x + 2, body.y + 2, body.width - 4, body.height - 4), lines, {
        size: 10 * u,
        chars,
        caret,
        first: labels.compact_from + 1,
      });
    });
  }
}

export default Object.freeze({
  id: "logic",
  duration: DURATION,
  still: STILL,
  render(context, time, size) {
    if (size.width < COMPACT_BELOW) renderCompact(context, time, size);
    else renderWide(context, time, size);
  },
});
