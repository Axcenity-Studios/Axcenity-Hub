// The reel's player: draws the frame for the clock's time, and runs the
// controls, visibility pausing and reduced motion. Play, pause, seek and resize
// only change the clock or the canvas size; what's drawn is always
// segmentAt(time).render(context, time into it, logical size).

import * as timeline from "./timeline.js";
import { FONTS, fit, logicalSize, pixelRatio, readPalette, tint, useLogicalPixels } from "./canvas.js";

/** How much of the reel must be on screen for it to play. */
const VISIBLE_SHARE = 0.3;

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

function loadImage(src) {
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null); // the lockup just leaves the logo out
    image.src = src;
  });
}

function clockText(seconds) {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/** Mounts the reel on `reel` (the figure), drawing with `g` on `canvas`. */
export function mount(reel, canvas, g) {
  const root = document.documentElement;
  const controls = document.getElementById(reel.dataset.controls);
  const toggle = controls.querySelector("[data-reel-toggle]");
  const range = controls.querySelector('input[type="range"]');
  const scrub = range.parentElement;
  const labels = deepFreeze(JSON.parse(document.getElementById(reel.dataset.labels).textContent));
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const clock = timeline.createClock();
  const now = () => performance.now();

  let size = logicalSize(reel);
  let palette = readPalette(root);
  let wordmark = null;
  let context = null;
  let raf = 0;
  let onScreen = false; // at least VISIBLE_SHARE in view (the observer says so first)
  let userPaused = reduce.matches; // reduced motion never autoplays
  let scrubbing = false;
  let spoken = "";

  // An offscreen layer the size of the canvas, for drawing something at a lower
  // opacity as one picture (group opacity). It's cleared on every use, so a
  // frame never depends on what it held before.
  const layerCanvas = document.createElement("canvas");
  const layerG = layerCanvas.getContext("2d");

  function layer(alpha, draw) {
    if (alpha <= 0) return;
    if (layerCanvas.width !== canvas.width) layerCanvas.width = canvas.width;
    if (layerCanvas.height !== canvas.height) layerCanvas.height = canvas.height;
    layerG.setTransform(1, 0, 0, 1, 0, 0);
    layerG.globalAlpha = 1;
    layerG.clearRect(0, 0, layerCanvas.width, layerCanvas.height);
    layerG.setTransform(g.getTransform());
    layerG.save();
    // A layer inside a layer draws straight into this one at its own alpha (no second buffer).
    const inside = Object.freeze({
      ...context,
      g: layerG,
      layer: (nestedAlpha, nested) => {
        layerG.save();
        layerG.globalAlpha *= nestedAlpha;
        nested(inside);
        layerG.restore();
      },
    });
    draw(inside);
    layerG.restore();
    g.save();
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalAlpha *= alpha;
    g.drawImage(layerCanvas, 0, 0);
    g.restore();
  }

  function rebuildContext() {
    const images = Object.freeze({ wordmark: tint(wordmark, palette.fgStrong) });
    context = Object.freeze({ g, colors: palette, labels, images, layer });
  }

  // ---------- Drawing ----------

  function draw(time) {
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, canvas.width, canvas.height);
    useLogicalPixels(g, canvas, size);
    const at = timeline.segmentAt(time);
    g.save();
    at.segment.render(context, at.time, size);
    g.restore();
  }

  function show(time, { moveThumb = true } = {}) {
    scrub.style.setProperty("--reel-progress", String(time / timeline.DURATION));
    if (moveThumb && !scrubbing) range.value = String(time);
    const segment = timeline.segmentAt(time).segment;
    const text = `${clockText(time)} ${controls.dataset.of} ${clockText(timeline.DURATION)}, ${labels.segments[segment.id] || segment.id}`;
    if (text !== spoken) {
      spoken = text;
      range.setAttribute("aria-valuetext", text);
    }
  }

  function redraw() {
    const time = clock.time(now());
    draw(time);
    show(time);
  }

  function frame() {
    raf = 0;
    redraw();
    raf = requestAnimationFrame(frame);
  }

  // ---------- Playing and pausing ----------
  // It runs only while the visitor wants it to (not paused, not reduced motion
  // unless they pressed Play), the reel is on screen and the tab is visible.
  // While it isn't running, no animation frame is requested at all.

  function shouldRun() {
    return !userPaused && onScreen && document.visibilityState === "visible";
  }

  function update() {
    const running = shouldRun();
    if (running) {
      clock.play(now());
      if (!raf) raf = requestAnimationFrame(frame);
    } else {
      clock.pause(now());
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      redraw();
    }
    reel.dataset.state = running ? "playing" : "paused";
    // Reading `reduce` here also keeps the MediaQueryList reachable: one held only by
    // its own listener can be garbage-collected, and its change event never fires.
    reel.dataset.motion = reduce.matches ? "reduced" : "full";
    controls.dataset.intent = userPaused ? "paused" : "playing";
    toggle.setAttribute("aria-label", userPaused ? toggle.dataset.playLabel : toggle.dataset.pauseLabel);
  }

  function togglePlay() {
    userPaused = !userPaused;
    update();
  }

  function seek(time) {
    scrubbing = false; // a jump always moves the thumb
    clock.seek(time, now());
    redraw();
  }

  // ---------- Controls ----------

  range.max = String(timeline.DURATION);
  for (const marker of timeline.MARKERS) {
    const tick = document.createElement("span");
    tick.className = "reel-marker";
    tick.style.setProperty("--at", String(marker / timeline.DURATION));
    scrub.querySelector(".reel-track").append(tick);
  }

  toggle.addEventListener("click", togglePlay);

  // Dragging or arrowing the range seeks; the thumb stays where the visitor put
  // it (seeking to the very end shows the loop's first frame).
  range.addEventListener("pointerdown", () => (scrubbing = true));
  range.addEventListener("input", () => {
    scrubbing = true;
    clock.seek(Number(range.value), now());
    const time = clock.time(now());
    draw(time);
    show(time, { moveThumb: false });
  });
  const endScrub = () => {
    scrubbing = false;
  };
  range.addEventListener("change", endScrub);
  range.addEventListener("pointerup", endScrub);
  range.addEventListener("blur", endScrub);

  // Space toggles anywhere in the controls. ← and → jump between scene markers,
  // except on the range, where they keep their own job (fine seeking).
  controls.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.key === " ") {
      if (event.target === toggle) return; // the button's own Space press clicks it
      event.preventDefault();
      togglePlay();
    } else if ((event.key === "ArrowRight" || event.key === "ArrowLeft") && event.target !== range) {
      event.preventDefault();
      const time = clock.time(now());
      seek(event.key === "ArrowRight" ? timeline.nextMarker(time) : timeline.previousMarker(time));
    }
  });

  // ---------- Visibility, reduced motion, theme and size ----------

  new IntersectionObserver(
    (entries) => {
      const entry = entries[entries.length - 1];
      onScreen = entry.isIntersecting && entry.intersectionRatio >= VISIBLE_SHARE - 0.001;
      update();
    },
    { threshold: [0, VISIBLE_SHARE] }
  ).observe(reel);

  document.addEventListener("visibilitychange", update);

  reduce.addEventListener("change", () => {
    if (reduce.matches) {
      userPaused = true;
      clock.seek(timeline.LOCKUP_FRAME, now());
    } else {
      userPaused = false;
    }
    update();
  });

  new MutationObserver(() => {
    palette = readPalette(root);
    rebuildContext();
    redraw();
  }).observe(root, { attributes: true, attributeFilter: ["data-scheme"] });

  function resize() {
    size = logicalSize(reel);
    fit(canvas, size, pixelRatio());
    redraw(); // resizing clears the canvas; the clock is untouched
    reel.dataset.size = `${size.width}x${size.height}`;
  }
  new ResizeObserver(resize).observe(reel);
  window.addEventListener("resize", resize); // also catches zoom (a new pixel ratio)

  // ---------- Start ----------

  if (reduce.matches) clock.seek(timeline.LOCKUP_FRAME, now());
  rebuildContext();
  reel.setAttribute("aria-describedby", reel.dataset.description);
  controls.hidden = false;
  delete reel.dataset.pending;
  reel.dataset.live = "";
  resize();
  update();

  // Text and the logo are drawn once their fonts and images arrive; until then
  // the frame uses fallbacks. Redraw then, and mark the reel ready.
  Promise.all([
    Promise.all(FONTS.map((spec) => document.fonts.load(spec).catch(() => null))),
    loadImage(reel.dataset.wordmark),
  ]).then(([, image]) => {
    wordmark = image;
    rebuildContext();
    redraw();
    reel.dataset.ready = "";
  });
}
