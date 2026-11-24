// The Toolbox banner's loop (12 s): finding a texture with the editor's Toolbox
// and dropping it on a part.
//
// 1. The Scene View shows the Pad turning, above the Assets pane.
// 2. A pointer presses the Assets pane's Toolbox button; the Toolbox opens as a
//    tab beside Assets (layout.rs).
// 3. It types "rock" into the search field and presses Search: "Searching…",
//    then the cards pop in one after another.
// 4. It drags the first card's picture onto the Pad. The status line says it's
//    downloading and the Pad takes on the rock texture.
// 5. The pointer drifts off and the textured Pad turns. Then the Toolbox tab
//    closes back to Assets and the texture fades: the loop's first frame.
//
// Below 480 px wide the Toolbox shows its compact layout (the search row and
// the cards). Like every loop it holds no state: a frame comes from
// (context, time, size) alone.

import { clamp, easeInOut, expoOut, progress, rect } from "../easing.js";
import * as ui from "../drawing/editor.js";
import * as tb from "../drawing/toolbox.js";
import { pointerPath } from "../drawing/pointer.js";

const DURATION = 12;
/** The frame reduced motion shows: the results up and the Pad textured. */
const STILL = 7;
const COMPACT_BELOW = 480;
/** The viewport turns the Pad 0.35 rad per clock second. Half a turn a loop (the Pad is square) wraps seamlessly. */
const SPIN = Math.PI / 0.35 / DURATION;

// When things happen, in seconds into the loop.
const T = Object.freeze({
  enter: 0.7, // the pointer comes in
  button: 1.2, // the Toolbox button is pressed
  open: 1.28, // the Toolbox tab opens
  field: 1.75, // the search field is clicked
  type: Object.freeze([1.85, 0.4]), // "rock" typed
  search: 2.5, // Search pressed
  results: 2.8, // the cards start popping in
  grab: 3.4, // the pointer reaches the first card
  press: 3.5, // and picks up its picture
  drop: 4.4, // onto the Pad
  texture: 4.65, // the Pad takes the texture
  gone: Object.freeze([5.1, 5.7]),
  close: Object.freeze([10.0, 0.5]), // the Toolbox tab closes back to Assets
  plain: Object.freeze([10.2, 1.3]), // the texture fades off the Pad
});

/** The Toolbox's search at `t`, as drawing/toolbox.js takes it. */
function searchState(t, labels) {
  const typed = Math.floor(progress(t, T.type[0], T.type[1]) * labels.toolbox.query.length);
  const editing = t >= T.field && t < T.search;
  return {
    typed,
    caret: editing && (t < T.type[0] + T.type[1] || Math.floor(t * 4) % 2 === 0),
    searchPressed: t >= T.search && t < T.search + 0.08,
    searching: t >= T.search + 0.04,
    results: t >= T.results ? t - T.results : -1,
    lifted: t >= T.press && t < T.drop ? 0 : -1,
    status: t >= T.drop ? expoOut(progress(t, T.drop, 0.2)) * (1 - progress(t, T.drop + 0.65, 0.25)) : 0,
  };
}

/** The drag's ghost at the pointer: the card's picture, small, and its name beside a download mark. */
function ghost(g, colors, labels, tip, u) {
  const [name, , pattern] = labels.toolbox.cards[0];
  const side = 30 * u;
  const picture = rect(tip.x + 8 * u, tip.y + 10 * u, side, side);
  g.save();
  g.globalAlpha *= 0.9 * tip.alpha;
  ui.shadow(g, colors, picture, u, 1);
  tb.picture(g, colors, picture, pattern, 1, u);
  g.font = ui.font(500, 11 * u, "Inter");
  const chip = rect(picture.x + side + 4 * u, picture.y + 4 * u, g.measureText(name).width + 28 * u, 20 * u);
  ui.fill(g, colors.elevated, chip);
  ui.outline(g, colors.lineStrong, chip);
  tb.downArrow(g, colors, chip.x + 10 * u, chip.y + chip.height / 2, u);
  ui.text(g, colors.fgStrong, name, chip.x + 19 * u, chip.y + chip.height / 2, ui.font(500, 11 * u, "Inter"));
  g.restore();
}

function draw(context, time, size) {
  const { g, colors, labels, layer } = context;
  const compact = size.width < COMPACT_BELOW;
  const u = compact ? clamp(size.width / 400, 0.7, 1.1) : clamp(size.width / 760, 0.6, 1.3);
  const tabBar = 24 * u;
  const split = Math.round(size.height * (compact ? 0.36 : 0.42));

  // The Scene View and the Pad, textured once the drop lands.
  const sceneBox = ui.panel(g, colors, rect(0, 0, size.width, split), labels.tabs.scene, 0, u, tabBar);
  const textured = expoOut(progress(time, T.texture, 0.5)) * (1 - easeInOut(progress(time, T.plain[0], T.plain[1])));
  ui.viewport(g, colors, sceneBox, u, time * SPIN, textured);

  // The bottom dock: Assets, then the Toolbox as a tab beside it, closing again at the end.
  const dock = rect(0, split, size.width, size.height - split);
  const content = rect(dock.x + 1, dock.y + tabBar, dock.width - 2, dock.height - tabBar - 1);
  const [consoleTab, assetsTab, profilerTab] = labels.tabs.console;
  const open = time >= T.open;
  const closing = expoOut(progress(time, T.close[0], T.close[1]));
  if (!open || closing > 0) {
    const box = ui.panel(g, colors, dock, labels.tabs.console, 1, u, tabBar);
    ui.assets(g, colors, box, labels, u, time >= T.button && time < T.button + 0.1);
  }
  if (open && closing < 1) {
    const draw = (inside) => {
      const box = ui.panel(inside.g, colors, dock, [consoleTab, assetsTab, labels.toolbox.button, profilerTab], 2, u, tabBar);
      tb.toolbox(inside.g, colors, box, labels, u, searchState(time, labels), compact);
    };
    if (closing > 0) layer(1 - closing, draw);
    else draw(context);
  }

  // The pointer: the Toolbox button, the field, Search, then the drag onto the Pad.
  const centre = (box) => ({ x: box.x + box.width / 2, y: box.y + box.height / 2 });
  const L = tb.toolboxLayout(g, content, labels, u, compact);
  const button = ui.toolboxButton(g, content, labels.toolbox.button, u);
  const pad = { x: sceneBox.x + sceneBox.width / 2, y: sceneBox.y + sceneBox.height * 0.552 };
  const card = centre(L.cards[0].picture);
  const field = { x: L.field.x + 20 * u, y: L.field.y + L.field.height / 2 };
  const stop = (point, at) => ({ x: point.x, y: point.y, at });
  const tip = pointerPath(
    time,
    [
      stop({ x: size.width * 0.86, y: size.height * 0.9 }, T.enter),
      stop(centre(button), T.button),
      stop(centre(button), T.button + 0.1),
      stop(field, T.field),
      stop(field, T.field + 0.08),
      stop(centre(L.search), T.search),
      stop(centre(L.search), T.search + 0.12),
      stop(card, T.grab),
      stop(card, T.press),
      stop(pad, T.drop),
      stop({ x: pad.x + 50 * u, y: pad.y + 40 * u }, T.gone[1]),
    ],
    [
      [T.button, T.button + 0.1],
      [T.field, T.field + 0.07],
      [T.search, T.search + 0.08],
      [T.press, T.drop + 0.03],
    ],
    T.gone
  );
  if (!tip) return;
  if (time >= T.press && time < T.drop) ghost(g, colors, labels, tip, u);
  g.save();
  g.globalAlpha *= tip.alpha;
  ui.pointer(g, colors, tip.x, tip.y, u, tip.pressed);
  g.restore();
}

export default Object.freeze({
  id: "toolbox",
  duration: DURATION,
  still: STILL,
  render(context, time, size) {
    draw(context, time, size);
  },
});
