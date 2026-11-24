// The player for the feature pillars' animated recreations: one per [data-loop]
// figure. It draws loop.render(context, time, size) for its own clock, and runs
// only while the visitor hasn't paused it, at least 30% of it is on screen, the
// tab is visible and (on the desktop stage) its pillar is the one showing.
// Otherwise no animation frame is requested at all. Under reduced motion it
// doesn't autoplay: it shows the loop's still frame, and its button plays it.

import { FONTS, fit, groupLayer, logicalSize, pixelRatio, readPalette, useLogicalPixels } from "../canvas.js";

/** How much of a loop must be on screen for it to play. */
const VISIBLE_SHARE = 0.3;
/** The longest step the clock takes between two frames (after a stall it carries on, it doesn't jump). */
const MAX_STEP = 0.1;

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

/**
 * The smallest file in `srcset` ("url 640w, url 960w, …") at least `width` device pixels
 * wide, or the widest there is. A capture covering a 16:10 frame, pushed in, is drawn
 * about 1.2 times the frame's width.
 */
function pick(srcset, width) {
  const files = srcset
    .split(",")
    .map((entry) => entry.trim().split(/\s+/))
    .map(([url, w]) => ({ url, width: parseInt(w, 10) }))
    .sort((a, b) => a.width - b.width);
  return (files.find((file) => file.width >= width) || files[files.length - 1]).url;
}

/** A picture, decoded, or null if it can't load (the loop draws without it). */
function loadImage(url) {
  const image = new Image();
  image.decoding = "async";
  image.src = url;
  return image.decode().then(() => image, () => null);
}

/** Mounts `loop` (a loop module's default export) on `figure`, drawing with `g` on `canvas`. */
export function mount(figure, canvas, g, loop) {
  const root = document.documentElement;
  const toggle = figure.querySelector("[data-loop-toggle]");
  const labels = deepFreeze(JSON.parse(figure.dataset.labels));
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  // On the desktop stage only the current pillar's item is shown (home.js sets data-on).
  const stageItem = figure.closest("[data-stage-item]");

  let size = logicalSize(figure);
  let palette = readPalette(root);
  let context = null;
  let raf = 0;
  let last = null; // the previous frame's timestamp while running
  let onScreen = false;
  let userPaused = reduce.matches;
  let time = reduce.matches ? loop.still : 0;

  const drawLayer = groupLayer(canvas, g);
  function layer(alpha, draw) {
    drawLayer(context, alpha, draw);
  }
  // Pictures a loop draws (data-capture: the renderer capture, for the wipe), each null until loaded.
  let images = Object.freeze({ capture: null });
  function rebuildContext() {
    context = Object.freeze({ g, colors: palette, labels, images, layer });
  }

  function draw() {
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, canvas.width, canvas.height);
    // A frame that isn't laid out (the inline copies on the desktop, display: none) has nothing to draw.
    if (size.width < 2 || size.height < 2) return;
    useLogicalPixels(g, canvas, size);
    g.save();
    loop.render(context, time, size);
    g.restore();
  }

  function frame(now) {
    raf = 0;
    if (last !== null) time = (time + Math.min(MAX_STEP, Math.max(0, (now - last) / 1000))) % loop.duration;
    last = now;
    draw();
    raf = requestAnimationFrame(frame);
  }

  function shouldRun() {
    return (
      !userPaused &&
      onScreen &&
      document.visibilityState === "visible" &&
      (!stageItem || stageItem.hasAttribute("data-on"))
    );
  }

  function update() {
    const running = shouldRun();
    if (running && !raf) {
      last = null;
      raf = requestAnimationFrame(frame);
    } else if (!running) {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      last = null;
      draw();
    }
    figure.dataset.state = running ? "playing" : "paused";
    // Reading `reduce` here keeps the MediaQueryList reachable: one held only by its own
    // listener can be garbage-collected, and its change event never fires.
    figure.dataset.motion = reduce.matches ? "reduced" : "full";
    toggle.dataset.intent = userPaused ? "paused" : "playing";
    toggle.setAttribute("aria-label", userPaused ? toggle.dataset.playLabel : toggle.dataset.pauseLabel);
  }

  // Tests and screenshots show any moment: dispatch new CustomEvent("loop-seek", { detail: seconds }).
  figure.addEventListener("loop-seek", (event) => {
    const seconds = Number(event.detail);
    time = Number.isFinite(seconds) ? ((seconds % loop.duration) + loop.duration) % loop.duration : 0;
    last = null;
    draw();
  });

  toggle.addEventListener("click", () => {
    userPaused = !userPaused;
    update();
  });

  new IntersectionObserver(
    (entries) => {
      const entry = entries[entries.length - 1];
      onScreen = entry.isIntersecting && entry.intersectionRatio >= VISIBLE_SHARE - 0.001;
      update();
    },
    { threshold: [0, VISIBLE_SHARE] }
  ).observe(figure);

  document.addEventListener("visibilitychange", update);
  if (stageItem) new MutationObserver(update).observe(stageItem, { attributes: true, attributeFilter: ["data-on"] });

  reduce.addEventListener("change", () => {
    userPaused = reduce.matches;
    if (reduce.matches) time = loop.still;
    update();
  });

  new MutationObserver(() => {
    palette = readPalette(root);
    rebuildContext();
    draw();
  }).observe(root, { attributes: true, attributeFilter: ["data-scheme"] });

  function resize() {
    size = logicalSize(figure);
    fit(canvas, size, pixelRatio());
    draw();
    figure.dataset.size = `${size.width}x${size.height}`;
  }
  new ResizeObserver(resize).observe(figure);
  window.addEventListener("resize", resize);

  rebuildContext();
  toggle.hidden = false;
  figure.dataset.live = "";
  resize();
  update();

  const capture = figure.dataset.capture
    ? loadImage(pick(figure.dataset.capture, size.width * pixelRatio() * 1.2))
    : Promise.resolve(null);
  Promise.all([capture, ...FONTS.map((spec) => document.fonts.load(spec).catch(() => null))]).then(([picture]) => {
    images = Object.freeze({ capture: picture });
    rebuildContext();
    draw();
    figure.dataset.ready = "";
  });
}
