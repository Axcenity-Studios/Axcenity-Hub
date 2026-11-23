// Luau in the script editor's look, drawn on the canvas: a gutter of line
// numbers, then each line's tokens in the editor's syntax colours
// (crates/editor-kit/src/lua_syntax.rs, as the site's luau-* tokens). The
// lines arrive already split into [kind, text] tokens by
// marketing/drawings.py luau_lines, so the canvas and the page's own
// highlighted fallback colour the code the same way.
//
// Pure: everything comes from the arguments, in logical pixels.

import { font } from "./editor.js";

const KINDS = Object.freeze({
  keyword: "luauKeyword",
  literal: "luauLiteral",
  builtin: "luauBuiltin",
  number: "luauNumber",
  string: "luauString",
  comment: "luauComment",
});

/** The code font at `size` pixels. */
export function mono(size) {
  return font(400, size, "JetBrains Mono");
}

/** How many characters `lines` hold, counting each line break as one. */
export function length(lines) {
  return lines.reduce((total, line) => total + line.reduce((sum, [, text]) => sum + text.length, 0) + 1, 0);
}

/**
 * Draws `lines` into `box` with its first line `first` (for the gutter's
 * numbers), typed out up to `chars` characters, with a caret after the last
 * one while `caret` is true. Lines past the box's right edge are clipped.
 */
export function code(g, colors, box, lines, { size, chars = Infinity, caret = false, first = 1 }) {
  const lineHeight = size * 1.7;
  g.save();
  g.beginPath();
  g.rect(box.x, box.y, box.width, box.height);
  g.clip();
  g.font = mono(size);
  g.textBaseline = "middle";
  const gutter = g.measureText(String(first + lines.length)).width + size * 1.6;
  let left = chars;
  let caretAt = { x: box.x + gutter, y: box.y + size + lineHeight / 2 };
  lines.forEach((line, index) => {
    const y = box.y + size + lineHeight * index + lineHeight / 2;
    if (left < 0) return;
    g.fillStyle = colors.fgWeak;
    g.textAlign = "right";
    g.fillText(String(first + index), box.x + gutter - size * 0.9, y);
    g.textAlign = "left";
    let x = box.x + gutter;
    for (const [kind, text] of line) {
      if (left <= 0) break;
      const shown = text.slice(0, Math.max(0, left));
      g.fillStyle = colors[KINDS[kind]] || colors.fg;
      g.fillText(shown, x, y);
      x += g.measureText(shown).width;
      left -= text.length;
    }
    caretAt = { x, y };
    left -= 1; // the line break
  });
  if (caret) {
    g.fillStyle = colors.fgStrong;
    g.fillRect(caretAt.x + 1, caretAt.y - size * 0.7, Math.max(1, size * 0.12), size * 1.4);
  }
  g.restore();
}
