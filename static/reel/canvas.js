// The reel's canvas: HiDPI sizing, the logical size scenes draw in, the colour
// tokens and the tinted logo. Scenes never see physical pixels: the player sets
// a transform from logical (CSS) pixels to the backing store before each frame.

/** Backing-store pixels per CSS pixel, at most this many (sharp on Retina, cheaper on 3× phones). */
export const MAX_PIXEL_RATIO = 2;

/** Below this logical width the scenes use their compact layouts. */
export const COMPACT_BELOW = 640;

/** The display's pixel ratio, capped at MAX_PIXEL_RATIO. */
export function pixelRatio() {
  return Math.min(MAX_PIXEL_RATIO, Math.max(1, window.devicePixelRatio || 1));
}

/** The logical size scenes draw in: CSS pixels, and whether to use the compact layout. */
export function logicalSize(element) {
  const box = element.getBoundingClientRect();
  const width = Math.max(1, Math.round(box.width));
  const height = Math.max(1, Math.round(box.height));
  return Object.freeze({ width, height, compact: width < COMPACT_BELOW });
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

// The site's tokens the scenes may use. In dark mode they're the editor's own
// Dark theme values (tests/test_reel.py pins them to crates/editor-kit/src/theme.rs).
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

/** A copy of a loaded image filled with `color` (the logo is white; this makes it any token). */
export function tint(image, color) {
  if (!image || !image.complete || !image.naturalWidth) return null;
  const copy = document.createElement("canvas");
  copy.width = image.naturalWidth;
  copy.height = image.naturalHeight;
  const g = copy.getContext("2d");
  g.drawImage(image, 0, 0);
  g.globalCompositeOperation = "source-in";
  g.fillStyle = color;
  g.fillRect(0, 0, copy.width, copy.height);
  return copy;
}

/** The fonts the scenes draw with, as CSS font shorthands, so the player can load them first. */
export const FONTS = Object.freeze([
  '800 48px "Plus Jakarta Sans"',
  '400 12px "Inter"',
  '500 12px "Inter"',
  '600 12px "Inter"',
  '400 12px "JetBrains Mono"',
]);
