// The Toolbox pane (crates/editor-toolbox/src/lib.rs): the kind tabs
// (Textures, Skies, Models, Sounds), the toolbar (the Search view, Packs,
// All sources, the search field, Search and the resolution and format
// combos), the source chips or the download status, and the card grid. Each
// card is a picture, a name, a "Source · category · maps" line and Get.
// The pictures are drawn stand-ins for texture thumbnails, in the site's
// greys.
//
// Every function draws from its arguments alone, in logical pixels.

import { clamp, expoOut, progress, rect, spring } from "../easing.js";
import * as ui from "./editor.js";
import { hash } from "./terrain.js";

const ROW = 20; // a control row's height, before scaling by `u`
const GAP = 6;

/** Each control's box in the pane's content box `box`, and the card grid's. Compact keeps the search row and the cards. */
export function toolboxLayout(g, box, labels, u, compact = false) {
  const pane = labels.toolbox;
  const pad = 8 * u;
  const css = ui.font(500, 11 * u, "Inter");
  g.font = css;
  const across = (y, names, extra = 18) => {
    let x = box.x + pad;
    return names.map((name) => {
      const width = g.measureText(name).width + extra * u;
      const at = rect(x, y, width, ROW * u);
      x += width + 4 * u;
      return at;
    });
  };
  const kinds = compact ? [] : across(box.y + pad, pane.kinds, 16);
  const barY = compact ? box.y + pad : box.y + pad + (ROW + GAP) * u;
  const combos = compact ? [] : across(barY, pane.toolbar, 26);
  const after = combos[combos.length - 1];
  const fieldX = after ? after.x + after.width + 6 * u : box.x + pad;
  const field = rect(fieldX, barY, clamp(box.width * (compact ? 0.45 : 0.22), 80 * u, 160 * u), ROW * u);
  g.font = css;
  const search = rect(field.x + field.width + 4 * u, barY, g.measureText(pane.search).width + 30 * u, ROW * u);
  const chipsY = barY + (ROW + GAP) * u;
  const gridTop = compact ? chipsY : chipsY + (ROW + GAP) * u;
  // Cards: the picture as large as the room allows (the editor's is 112), then
  // its name, its detail line and Get below it.
  const below = 58 * u;
  const picture = clamp(box.y + box.height - pad - gridTop - below, compact ? 30 * u : 34 * u, 112 * u);
  const width = picture + 12 * u;
  const height = picture + below;
  const columns = Math.max(1, Math.floor((box.width - pad * 2 + 8 * u) / (width + 8 * u)));
  const cards = pane.cards.slice(0, columns * 2).map((_, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const card = rect(box.x + pad + column * (width + 8 * u), gridTop + row * (height + 8 * u), width, height);
    return { card, picture: rect(card.x + 6 * u, card.y + 6 * u, picture, picture) };
  });
  return { kinds, combos, field, search, chipsY, cards, picture, compact };
}

/** A combo box: its label and a small caret. */
function combo(g, colors, box, label, u) {
  ui.fill(g, colors.control, box);
  ui.outline(g, colors.line, box);
  ui.text(g, colors.fgSecondary, label, box.x + 8 * u, box.y + box.height / 2, ui.font(500, 11 * u, "Inter"));
  const x = box.x + box.width - 12 * u;
  const y = box.y + box.height / 2;
  g.fillStyle = colors.fgWeak;
  g.beginPath();
  g.moveTo(x - 3 * u, y - 1.5 * u);
  g.lineTo(x + 3 * u, y - 1.5 * u);
  g.lineTo(x, y + 2 * u);
  g.closePath();
  g.fill();
}

/** A magnifying glass, centred on (x, y). */
function magnifier(g, colors, x, y, u) {
  g.strokeStyle = colors.fgSecondary;
  g.lineWidth = 1.3 * u;
  g.beginPath();
  g.arc(x - 1 * u, y - 1 * u, 3.6 * u, 0, Math.PI * 2);
  g.moveTo(x + 1.6 * u, y + 1.6 * u);
  g.lineTo(x + 4.2 * u, y + 4.2 * u);
  g.stroke();
}

/** A small down arrow into a tray: the drag ghost's "downloads into" mark. */
export function downArrow(g, colors, x, y, u) {
  g.strokeStyle = colors.fgStrong;
  g.lineWidth = 1.4 * u;
  g.lineCap = "round";
  g.beginPath();
  g.moveTo(x, y - 4 * u);
  g.lineTo(x, y + 2 * u);
  g.moveTo(x - 3 * u, y - 1 * u);
  g.lineTo(x, y + 2 * u);
  g.lineTo(x + 3 * u, y - 1 * u);
  g.moveTo(x - 4.5 * u, y + 4.5 * u);
  g.lineTo(x + 4.5 * u, y + 4.5 * u);
  g.stroke();
  g.lineCap = "butt";
}

/**
 * A card's picture: a stand-in for the texture's thumbnail, drawn from its
 * pattern (rock, pebbles, wall, strata, gravel, slate) and `seed`.
 */
export function picture(g, colors, box, pattern, seed, u) {
  g.save();
  g.beginPath();
  g.roundRect(box.x, box.y, box.width, box.height, 4 * u);
  g.clip();
  const w = box.width;
  const h = box.height;
  const at = (n) => hash(seed * 31 + n);
  const tones = [colors.control, colors.controlActive, colors.lineStrong, colors.line, colors.fgWeak];
  const blob = (x, y, rx, ry, color, turn = 0) => {
    g.fillStyle = color;
    g.beginPath();
    g.ellipse(x, y, rx, ry, turn, 0, Math.PI * 2);
    g.fill();
  };
  if (pattern === "pebbles") {
    ui.fill(g, colors.inset, box);
    for (let n = 0; n < 16; n += 1) {
      const r = (0.08 + at(n) * 0.1) * w;
      blob(box.x + at(n + 40) * w, box.y + at(n + 80) * h, r, r * 0.8, tones[n % 3], at(n + 9) * 3);
      blob(box.x + at(n + 40) * w - r * 0.3, box.y + at(n + 80) * h - r * 0.3, r * 0.3, r * 0.18, colors.fgWeak, 0.6);
    }
  } else if (pattern === "wall") {
    ui.fill(g, colors.inset, box);
    const rows = 5;
    for (let row = 0; row < rows; row += 1) {
      let x = box.x - at(row) * w * 0.3;
      const y = box.y + (row * h) / rows;
      let n = 0;
      while (x < box.x + w) {
        const width = (0.25 + at(row * 10 + n) * 0.25) * w;
        ui.fill(g, tones[(row + n) % 3], rect(x + 1.5 * u, y + 1.5 * u, width - 3 * u, h / rows - 3 * u));
        x += width;
        n += 1;
      }
    }
  } else if (pattern === "strata") {
    for (let band = 0; band < 7; band += 1) {
      g.fillStyle = tones[band % 4];
      g.beginPath();
      const top = box.y + (band / 7) * h;
      g.moveTo(box.x, top);
      for (let step = 0; step <= 6; step += 1) {
        g.lineTo(box.x + (step / 6) * w, top + Math.sin(step + band * 1.7) * h * 0.03);
      }
      g.lineTo(box.x + w, top + h / 7 + 2);
      g.lineTo(box.x, top + h / 7 + 2);
      g.closePath();
      g.fill();
    }
  } else if (pattern === "gravel") {
    ui.fill(g, colors.control, box);
    for (let n = 0; n < 70; n += 1) {
      const r = (0.015 + at(n) * 0.03) * w;
      blob(box.x + at(n + 100) * w, box.y + at(n + 200) * h, r, r, tones[(n % 4) + 1]);
    }
  } else if (pattern === "slate") {
    ui.fill(g, colors.line, box);
    for (let n = 0; n < 9; n += 1) {
      g.save();
      g.translate(box.x + at(n) * w, box.y + at(n + 20) * h);
      g.rotate(-0.5 + at(n + 30) * 0.3);
      ui.fill(g, tones[n % 3], rect(-w * 0.3, -h * 0.12, w * 0.6, h * 0.24));
      ui.fill(g, colors.inset, rect(-w * 0.3, h * 0.12 - 1.5 * u, w * 0.6, 1.5 * u));
      g.restore();
    }
  } else {
    ui.fill(g, colors.controlActive, box);
    for (let n = 0; n < 10; n += 1) {
      blob(box.x + at(n) * w, box.y + at(n + 50) * h, (0.12 + at(n + 70) * 0.2) * w, (0.08 + at(n + 90) * 0.12) * h,
        tones[n % 4], at(n + 60) * 3);
    }
    g.strokeStyle = colors.inset;
    g.lineWidth = 1.2 * u;
    g.beginPath();
    g.moveTo(box.x + w * 0.1, box.y + h * (0.3 + at(1) * 0.2));
    g.lineTo(box.x + w * 0.45, box.y + h * (0.45 + at(2) * 0.2));
    g.lineTo(box.x + w * 0.9, box.y + h * (0.6 + at(3) * 0.2));
    g.stroke();
  }
  g.restore();
}

/**
 * The Toolbox in its content box at a moment of a search:
 * - `typed`: how many characters of the query are in the field (0 shows the placeholder)
 * - `caret`: whether the field's caret shows
 * - `searchPressed`: the Search button held down
 * - `results`: seconds since the results arrived (below 0: none yet, "Searching…" once `searching`)
 * - `searching`: the search is running
 * - `lifted`: the card being dragged (its picture dims), or -1
 * - `status`: how far the download status has come in, 0 to 1
 */
export function toolbox(g, colors, box, labels, u, state, compact = false) {
  const pane = labels.toolbox;
  const L = toolboxLayout(g, box, labels, u, compact);
  const css = ui.font(500, 11 * u, "Inter");
  ui.fill(g, colors.panel, box);

  // Kind tabs: Textures chosen.
  L.kinds.forEach((at, index) => {
    if (index === 0) ui.fill(g, colors.controlActive, at);
    ui.text(g, index === 0 ? colors.fgStrong : colors.fgWeak, pane.kinds[index], at.x + 8 * u, at.y + at.height / 2, css);
  });

  // The toolbar.
  L.combos.forEach((at, index) => combo(g, colors, at, pane.toolbar[index], u));
  const query = pane.query.slice(0, state.typed);
  ui.field(g, colors, L.field, query || pane.placeholder, u, !query);
  if (state.caret) {
    g.font = ui.font(400, 11.5 * u, "Inter");
    const x = L.field.x + 7 * u + (query ? g.measureText(query).width + 1 * u : 0);
    ui.fill(g, colors.fgStrong, rect(x, L.field.y + 4 * u, 1.2 * u, L.field.height - 8 * u));
  }
  const pressed = state.searchPressed;
  ui.fill(g, pressed ? colors.controlActive : colors.control, L.search);
  ui.outline(g, pressed ? colors.lineStrong : colors.line, L.search);
  magnifier(g, colors, L.search.x + 11 * u, L.search.y + L.search.height / 2, u);
  ui.text(g, colors.fgSecondary, pane.search, L.search.x + 20 * u, L.search.y + L.search.height / 2, css);
  let x = L.search.x + L.search.width + 4 * u;
  for (const option of compact ? [] : pane.options) {
    g.font = css;
    const width = g.measureText(option).width + 26 * u;
    if (x + width > box.x + box.width - 8 * u) break;
    combo(g, colors, rect(x, L.search.y, width, L.search.height), option, u);
    x += width + 4 * u;
  }

  // The chips, or the download's status line with Cancel.
  const chipY = L.chipsY + (ROW * u) / 2;
  if (compact) {
    // No chips row: the results go straight under the search row.
  } else if (state.status > 0) {
    g.save();
    g.globalAlpha *= state.status;
    ui.text(g, colors.fg, pane.downloading, box.x + 8 * u, chipY, ui.font(400, 11 * u, "Inter"));
    g.font = ui.font(400, 11 * u, "Inter");
    const cancelX = box.x + 16 * u + g.measureText(pane.downloading).width;
    g.font = css;
    ui.button(g, colors, rect(cancelX, L.chipsY + 1 * u, g.measureText(pane.cancel).width + 14 * u, ROW * u - 2 * u), pane.cancel, u);
    g.restore();
  } else if (state.results >= 0) {
    let chipX = box.x + 8 * u;
    pane.chips.forEach((label, index) => {
      chipX += ui.chip(g, colors, chipX, chipY, label, u, index === 0) + 2 * u;
    });
  } else if (state.searching) {
    ui.text(g, colors.fgWeak, pane.searching, box.x + 8 * u, chipY, ui.font(400, 11 * u, "Inter"));
  }

  // The cards pop in one after another.
  if (state.results < 0) return;
  g.save();
  ui.clipTo(g, rect(box.x, L.cards[0].card.y - 4 * u, box.width, box.y + box.height - L.cards[0].card.y + 4 * u));
  L.cards.forEach(({ card, picture: frame }, index) => {
    const since = state.results - index * 0.05;
    if (since <= 0) return;
    const shown = expoOut(progress(since, 0, 0.35));
    const lift = (1 - clamp(spring(since, 2.6, 0.62), 0, 1.2)) * 10 * u;
    const [name, detail, pattern] = pane.cards[index];
    g.save();
    g.globalAlpha *= shown;
    g.translate(0, lift);
    ui.fill(g, colors.surface, card);
    ui.outline(g, colors.line, card);
    g.save();
    if (index === state.lifted) g.globalAlpha *= 0.35;
    picture(g, colors, frame, pattern, index + 1, u);
    g.restore();
    g.save();
    ui.clipTo(g, rect(card.x + 4 * u, card.y, card.width - 8 * u, card.height));
    const textX = card.x + 6 * u;
    let y = frame.y + frame.height + 11 * u;
    ui.text(g, colors.fgStrong, name, textX, y, ui.font(500, 11 * u, "Inter"));
    y += 13 * u;
    ui.text(g, colors.fgWeak, detail, textX, y, ui.font(400, 9.5 * u, "Inter"));
    g.restore();
    g.font = css;
    const get = rect(textX, y + 9 * u, g.measureText(pane.get).width + 18 * u, 18 * u);
    ui.button(g, colors, get, pane.get, u);
    g.restore();
  });
  g.restore();
}
