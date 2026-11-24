// The Logic pillar's loop (16 s): one script in the block editor's Blocks and
// Graph views, and the Luau it becomes.
//
// 1. In the Blocks view a "when Pad is touched" hat pops in, and a "spawn decal"
//    block springs up under it and snaps into place.
// 2. The Luau the blocks translate to types out below, in the editor's syntax
//    colours.
// 3. The bar above the script switches to Graph: the same script as a When
//    Touched node and a Spawn Decal node. A wire draws between them, then a
//    pulse runs along it, as when the Pad is touched, and Spawn Decal lights up.
// 4. It switches back to Blocks, and everything fades, leaving the empty Blocks
//    view the loop starts from.
//
// Below 480 px wide it shows one view at a time in a single panel, as the bar
// switches between them: Blocks (panning across the wide block), Graph, then
// Code from the Connect call down. Like every loop it holds no state: a frame
// comes from (context, time, size) alone.

import { clamp, easeInOut, expoOut, lerp, progress, rect, spring } from "../easing.js";
import * as ui from "../drawing/editor.js";
import * as blocks from "../drawing/blocks.js";
import * as stacks from "../drawing/stacks.js";
import { code, length } from "../drawing/code.js";

const DURATION = 16;
/** The frame reduced motion shows: the blocks snapped together, the code typed. */
const STILL = 6.5;
/** Below this width the loop shows one view at a time. */
const COMPACT_BELOW = 480;
/** The bar's views, as positions: 0 Code, 1 Blocks, 2 Graph. */
const CODE = 0;
const BLOCKS = 1;
const GRAPH = 2;

// When things happen, in seconds. `views` is when the bar switches, and to what.
const WIDE = Object.freeze({
  hat: 0.3,
  block: 0.9,
  type: Object.freeze([2.0, 4.4]),
  views: Object.freeze([
    Object.freeze([7.0, GRAPH]),
    Object.freeze([12.2, BLOCKS]),
  ]),
  nodes: Object.freeze([7.3, 7.75]),
  wire: Object.freeze([8.4, 0.8]),
  pulse: Object.freeze([9.7, 1.1]),
  out: Object.freeze([14.6, 1.0]),
});
const COMPACT = Object.freeze({
  hat: 0.3,
  block: 0.9,
  pan: Object.freeze([2.0, 2.2]),
  views: Object.freeze([
    Object.freeze([5.0, GRAPH]),
    Object.freeze([9.4, CODE]),
    Object.freeze([14.6, BLOCKS]),
  ]),
  nodes: Object.freeze([5.3, 5.75]),
  wire: Object.freeze([6.3, 0.8]),
  pulse: Object.freeze([7.5, 1.1]),
  type: Object.freeze([9.8, 3.4]),
  out: Object.freeze([14.6, 1.0]),
});
/** How long the bar takes to switch, and the views to cross-fade. */
const SWITCH = 0.35;

/** Where the bar is at `t` (a view position, between two while it switches). */
function viewAt(t, timing) {
  let view = BLOCKS;
  for (const [at, to] of timing.views) view = lerp(view, to, easeInOut(progress(t, at, SWITCH)));
  return view;
}

/** How much of `view` shows at `t` (1 when the bar is on it). */
function showing(t, timing, view) {
  return clamp(1 - Math.abs(viewAt(t, timing) - view));
}

// ---------- The bar ----------

/** The bar above the script: Code, Blocks and Graph as one segmented control, and its hint. */
function modeBar(g, colors, labels, box, u, view) {
  ui.fill(g, colors.panel, box);
  ui.fill(g, colors.line, rect(box.x, box.y + box.height - 1, box.width, 1));
  const css = ui.font(500, 11 * u, "Inter");
  g.font = css;
  const height = box.height - 10 * u;
  let x = box.x + 8 * u;
  const segments = labels.views.map((name) => {
    const width = g.measureText(name).width + 20 * u;
    const at = rect(x, box.y + 5 * u, width, height);
    x += width;
    return at;
  });
  const whole = rect(segments[0].x, segments[0].y, x - segments[0].x, height);
  ui.fill(g, colors.control, whole);
  ui.outline(g, colors.line, whole);
  // The chosen segment slides as the bar switches.
  const low = Math.floor(view);
  const high = Math.min(low + 1, segments.length - 1);
  const chosen = { x: lerp(segments[low].x, segments[high].x, view - low), width: lerp(segments[low].width, segments[high].width, view - low) };
  ui.fill(g, colors.controlActive, rect(chosen.x, whole.y, chosen.width, height));
  ui.outline(g, colors.lineStrong, rect(chosen.x, whole.y, chosen.width, height));
  segments.forEach((at, index) => {
    const on = Math.abs(view - index) < 0.5;
    ui.text(g, on ? colors.fgStrong : colors.fgSecondary, labels.views[index], at.x + at.width / 2, at.y + at.height / 2, css, "center");
  });
  // The hint, only where it fits whole.
  const hintCss = ui.font(400, 10.5 * u, "Inter");
  g.font = hintCss;
  if (x + 12 * u + g.measureText(labels.switch_hint).width < box.x + box.width - 8 * u) {
    ui.text(g, colors.fgWeak, labels.switch_hint, x + 12 * u, box.y + box.height / 2, hintCss);
  }
}

// ---------- The Blocks view ----------

/** The stack's size at zoom 1: the hat over the block. */
function stackSize(g, labels) {
  const [hat, block] = labels.stack;
  const top = stacks.blockSize(g, hat, 1, true);
  const under = stacks.blockSize(g, block, 1);
  return { width: Math.max(top.width, under.width), hat: top.height, height: top.height + under.height };
}

/**
 * The Blocks view in `area`: the hat popping in, the block springing up under
 * it and snapping on. `z` fits the stack; `pan` (0 to 1) scrolls across it when
 * it's wider than the view.
 */
function drawBlocks(context, area, u, time, timing, compact) {
  const { g, colors, labels, layer } = context;
  const size = stackSize(g, labels);
  const pad = 16 * u;
  const fit = Math.min((area.width - pad * 2) / size.width, (area.height - pad * 2) / size.height);
  const z = compact ? Math.max(0.62, Math.min(fit, 1)) : Math.min(fit, 1.05 * u);
  const over = Math.max(0, size.width * z - (area.width - pad * 2));
  const pan = compact ? easeInOut(progress(time, timing.pan[0], timing.pan[1])) * over : 0;
  const x = area.x + Math.max(pad, (area.width - size.width * z) / 2) - pan;
  const y = area.y + (area.height - size.height * z) / 2;
  // The dots are spaced by the frame's unit, not the stack's zoom, so the empty view matches.
  stacks.canvas(g, colors, area, u, { x: -pan, y: 0 });
  g.save();
  ui.clipTo(g, area);
  const [hat, block] = labels.stack;
  // The block, under the hat so the hat's tab overlaps its top.
  const blockSince = time - timing.block;
  if (blockSince > 0) {
    const settle = clamp(spring(blockSince, 2.4, 0.7), 0, 1.2);
    layer(expoOut(progress(blockSince, 0, 0.25)), (inside) =>
      stacks.drawBlock(inside.g, colors, block, x + (1 - settle) * 70 * z, y + size.hat * z + (1 - settle) * 46 * z, z)
    );
  }
  const hatSince = time - timing.hat;
  if (hatSince > 0) {
    const rise = (1 - clamp(spring(hatSince, 2.6, 0.6), 0, 1.2)) * 14 * z;
    layer(expoOut(progress(hatSince, 0, 0.35)), (inside) => stacks.drawBlock(inside.g, colors, hat, x, y + rise, z, true));
  }
  g.restore();
}

// ---------- The Graph view ----------

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

/** The Graph view in `body`: the nodes popping in, the wire drawing, the pulse. */
function drawGraph(context, body, u, time, timing) {
  const { g, colors, labels, layer } = context;
  blocks.grid(g, colors, body, u);
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

// ---------- The script ----------

/** The script's views in `area`, cross-faded as the bar switches. `codeView` draws the Code view (compact only). */
function drawViews(context, area, u, time, timing, compact, codeView) {
  const { layer } = context;
  const views = [
    [BLOCKS, (inside) => drawBlocks(inside, area, u, time, timing, compact)],
    [GRAPH, (inside) => drawGraph(inside, area, u, time, timing)],
  ];
  if (codeView) views.push([CODE, codeView]);
  // The view the bar is leaving underneath, the one it's reaching over it.
  const shown = views.map(([view, draw]) => [showing(time, timing, view), draw]).filter(([amount]) => amount > 0);
  shown.sort((a, b) => b[0] - a[0]);
  shown.forEach(([amount, draw], index) => {
    if (index === 0) draw(context);
    else layer(amount, draw);
  });
}

/** How much of the code has been typed at `time`, and whether the caret shows. */
function typing(time, lines, timing) {
  const total = length(lines);
  const typed = progress(time, timing.type[0], timing.type[1]);
  const busy = typed > 0 && typed < 1;
  return { chars: Math.floor(typed * total), caret: typed > 0 && (busy || Math.floor(time * 2) % 2 === 0) };
}

/** Everything that fades at the end of the loop, over the empty view it fades to. */
function fading(context, time, timing, empty, full) {
  const shown = 1 - easeInOut(progress(time, timing.out[0], timing.out[1]));
  if (shown >= 1) full(context);
  else if (shown <= 0) empty(context);
  else {
    empty(context);
    context.layer(shown, full);
  }
}

function renderWide(context, time, size) {
  const { g, colors, labels } = context;
  const u = clamp(size.width / 760, 0.6, 1.3);
  const tabBar = 24 * u;
  const bar = 30 * u;
  const split = Math.round(size.height * 0.55);
  const body = ui.panel(g, colors, rect(0, 0, size.width, split), [labels.script], 0, u, tabBar);
  modeBar(g, colors, labels, rect(body.x, body.y, body.width, bar), u, viewAt(time, WIDE));
  const area = rect(body.x, body.y + bar, body.width, body.height - bar);
  const codeBody = ui.panel(g, colors, rect(0, split, size.width, size.height - split), [labels.code], 0, u, tabBar);
  const fontSize = clamp(11 * u, 8.5, 13);
  const codeBox = rect(codeBody.x + 4 * u, codeBody.y - fontSize * 0.7, codeBody.width - 8 * u, codeBody.height + fontSize * 0.7);

  fading(
    context,
    time,
    WIDE,
    (inside) => {
      stacks.canvas(inside.g, colors, area, u);
      inside.g.fillStyle = colors.inset;
      inside.g.fillRect(codeBody.x, codeBody.y, codeBody.width, codeBody.height);
    },
    (inside) => {
      drawViews(inside, area, u, time, WIDE, false, null);
      inside.g.fillStyle = colors.inset;
      inside.g.fillRect(codeBody.x, codeBody.y, codeBody.width, codeBody.height);
      const { chars, caret } = typing(time, labels.lines, WIDE);
      code(inside.g, colors, codeBox, labels.lines, { size: fontSize, chars, caret });
    }
  );
}

function renderCompact(context, time, size) {
  const { g, colors, labels } = context;
  const u = clamp(size.width / 330, 0.85, 1.3);
  const tabBar = 24 * u;
  const bar = 30 * u;
  const body = ui.panel(g, colors, rect(0, 0, size.width, size.height), [labels.script], 0, u, tabBar);
  modeBar(g, colors, labels, rect(body.x, body.y, body.width, bar), u, viewAt(time, COMPACT));
  const area = rect(body.x, body.y + bar, body.width, body.height - bar);
  const codeView = (inside) => {
    inside.g.fillStyle = colors.inset;
    inside.g.fillRect(area.x, area.y, area.width, area.height);
    const lines = labels.lines.slice(labels.compact_from);
    const { chars, caret } = typing(time, lines, COMPACT);
    code(inside.g, colors, rect(area.x + 2, area.y + 2, area.width - 4, area.height - 4), lines, {
      size: 10 * u,
      chars,
      caret,
      first: labels.compact_from + 1,
    });
  };
  fading(
    context,
    time,
    COMPACT,
    (inside) => stacks.canvas(inside.g, colors, area, u),
    (inside) => drawViews(inside, area, u, time, COMPACT, true, codeView)
  );
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
