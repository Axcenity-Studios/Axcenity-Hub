// The loops' canvas: HiDPI sizing, the logical size loops draw in and the
// colour tokens. Loops never see physical pixels: the player sets a transform
// from logical (CSS) pixels to the backing store before each frame.

/** Backing-store pixels per CSS pixel, at most this many (sharp on Retina, cheaper on 3× phones). */
export const MAX_PIXEL_RATIO = 2;

/** The display's pixel ratio, capped at MAX_PIXEL_RATIO. */
export function pixelRatio() {
  return Math.min(MAX_PIXEL_RATIO, Math.max(1, window.devicePixelRatio || 1));
}

/**
 * The logical size loops draw in, in CSS pixels.
 * It's the layout box (offsetWidth/Height), which ignores transforms: a frame scaled
 * while it fades in (the pillars' stage) still gets a canvas for its full size.
 */
export function logicalSize(element) {
  const width = Math.max(1, element.offsetWidth);
  const height = Math.max(1, element.offsetHeight);
  return Object.freeze({ width, height });
}

/** Sizes the canvas's backing store for `size` at `ratio`. Resizing clears it, so redraw after. */
export function fit(canvas, size, ratio) {
  const width = Math.round(size.width * ratio);
  const height = Math.round(size.height * ratio);
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
}

/** Maps logical coordinates onto the whole backing store (exactly, even when rounding). */
export function useLogicalPixels(g, canvas, size) {
  g.setTransform(canvas.width / size.width, 0, 0, canvas.height / size.height, 0, 0);
}

/**
 * Group opacity on `canvas`: returns layer(context, alpha, draw), which draws
 * draw(inside) into an offscreen buffer the canvas's size (with g's current
 * transform) and composites it at `alpha` as one picture. `inside` is `context`
 * drawing into the buffer; a layer inside a layer draws straight into the
 * buffer at its own alpha (no second buffer). The buffer is cleared on every
 * use, so a frame never depends on what it held before.
 */
export function groupLayer(canvas, g) {
  const buffer = document.createElement("canvas");
  const bufferG = buffer.getContext("2d");
  return function layer(context, alpha, draw) {
    if (alpha <= 0) return;
    if (buffer.width !== canvas.width) buffer.width = canvas.width;
    if (buffer.height !== canvas.height) buffer.height = canvas.height;
    bufferG.setTransform(1, 0, 0, 1, 0, 0);
    bufferG.globalAlpha = 1;
    bufferG.clearRect(0, 0, buffer.width, buffer.height);
    bufferG.setTransform(g.getTransform());
    bufferG.save();
    const inside = Object.freeze({
      ...context,
      g: bufferG,
      layer: (nestedAlpha, nested) => {
        bufferG.save();
        bufferG.globalAlpha *= nestedAlpha;
        nested(inside);
        bufferG.restore();
      },
    });
    draw(inside);
    bufferG.restore();
    g.save();
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalAlpha *= alpha;
    g.drawImage(buffer, 0, 0);
    g.restore();
  };
}

// The site's tokens the loops may use. In dark mode they're the editor's own
// Dark theme values (tests/test_canvas.py pins them to crates/editor-kit/src/theme.rs).
const TOKENS = [
  "app",
  "panel",
  "surface",
  "inset",
  "control",
  "control-active",
  "line",
  "line-strong",
  "fg",
  "fg-strong",
  "fg-secondary",
  "fg-weak",
  "shade",
  "elevated",
  // The accent: only the renderer wipe's scan line (the PRD's fixed uses).
  "accent",
  // Content colours for code, node graphs and blocks only (the Logic loop), never chrome.
  "luau-keyword",
  "luau-literal",
  "luau-builtin",
  "luau-number",
  "luau-string",
  "luau-comment",
  "node-events",
  "node-looks",
  "node-title",
  "pin-object",
  "pin-any",
  "pin-text",
  "pin-vector",
  "pin-number",
  "block-events",
  "block-events-edge",
  "block-looks",
  "block-looks-edge",
  "block-sensing",
  "block-sensing-edge",
  "block-field",
  "block-field-text",
  "block-shade",
];

function camel(name) {
  return name.replace(/-(\w)/g, (_, letter) => letter.toUpperCase());
}

/** The colour tokens as they are now (light or dark), keyed in camelCase ({ fgStrong, panel, … }). */
export function readPalette(element) {
  const style = getComputedStyle(element);
  const palette = {};
  for (const name of TOKENS) palette[camel(name)] = style.getPropertyValue(`--color-${name}`).trim();
  return Object.freeze(palette);
}

/** The fonts the loops draw with, as CSS font shorthands, so the player can load them first. */
export const FONTS = Object.freeze([
  '400 12px "Inter"',
  '500 12px "Inter"',
  '600 12px "Inter"',
  '400 12px "JetBrains Mono"',
]);
