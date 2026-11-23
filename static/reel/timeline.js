// The reel's timeline: the registered segments, the scene markers, wrapping,
// seeking and the master clock. It knows nothing about drawing.
//
// Every segment is a scene module that satisfies the same contract (see
// docs/frontend/reel.md): a frozen default export with an `id`, a `start` and
// a `duration` in seconds, and `render(context, time, size)`, where `time` is
// seconds into that segment. Swapping a scene means swapping its module; the
// timeline and the player don't change.

import workspace from "./scenes/workspace.js";
import toolbox from "./scenes/toolbox.js";
import animation from "./scenes/animation.js";
import renderer from "./scenes/renderer.js";
import world from "./scenes/world.js";
import logic from "./scenes/logic.js";
import lockup from "./scenes/lockup.js";

/** The loop's length in seconds. Time `DURATION` is the loop's first frame again. */
export const DURATION = 26;

/** The six scenes, in order. Each start is a scene marker on the scrubber. */
export const SCENES = Object.freeze([workspace, toolbox, animation, renderer, world, logic]);

/** The closing logo lockup: a segment that follows the scenes but isn't a scene (no marker). */
export const OUTRO = lockup;

/** Every segment in order, covering [0, DURATION) with no gaps or overlaps. */
export const SEGMENTS = Object.freeze([...SCENES, OUTRO]);

/** Where each scene starts: the scrubber's markers and the stops for ← and →. */
export const MARKERS = Object.freeze(SCENES.map((scene) => scene.start));

/** The lockup frame: the logo fully shown. Reduced motion opens here. */
export const LOCKUP_FRAME = OUTRO.start + 1;

/** ← within this many seconds after a marker goes to the marker before it. */
export const BACK_GRACE = 0.3;

const EPSILON = 1e-6;

function check(segments) {
  let expected = 0;
  for (const segment of segments) {
    const name = (segment && segment.id) || "a segment";
    if (!Object.isFrozen(segment)) throw new Error(`reel: ${name} must be a frozen object`);
    if (typeof segment.id !== "string" || !segment.id) throw new Error(`reel: ${name} needs an id`);
    if (!Number.isFinite(segment.start) || !Number.isFinite(segment.duration) || segment.duration <= 0) {
      throw new Error(`reel: ${name} needs a finite start and a positive duration`);
    }
    if (typeof segment.render !== "function" || segment.render.length !== 3) {
      throw new Error(`reel: ${name} needs render(context, time, size)`);
    }
    if (Math.abs(segment.start - expected) > EPSILON) {
      throw new Error(`reel: ${name} starts at ${segment.start}s, not ${expected}s (a gap or an overlap)`);
    }
    expected = segment.start + segment.duration;
  }
  if (Math.abs(expected - DURATION) > EPSILON) {
    throw new Error(`reel: the segments end at ${expected}s, not ${DURATION}s`);
  }
}
check(SEGMENTS);

/** Any time as a time within the loop, [0, DURATION). DURATION itself is 0; anything not finite is 0. */
export function wrap(time) {
  if (!Number.isFinite(time)) return 0;
  const within = time % DURATION;
  const wrapped = within < 0 ? within + DURATION : within;
  return wrapped >= DURATION - EPSILON ? 0 : wrapped;
}

/** The segment showing at `time` and the time into it: { segment, time }. */
export function segmentAt(time) {
  const at = wrap(time);
  for (const segment of SEGMENTS) {
    if (at < segment.start + segment.duration) return Object.freeze({ segment, time: at - segment.start });
  }
  return Object.freeze({ segment: SEGMENTS[0], time: 0 }); // unreachable: check() covers the loop
}

/** The next scene marker after `time`. After the last scene it's the loop's first frame (0). */
export function nextMarker(time) {
  const at = wrap(time);
  const next = MARKERS.find((marker) => marker > at + EPSILON);
  return next === undefined ? MARKERS[0] : next;
}

/**
 * The scene marker before `time`: the start of the current scene, or of the one
 * before when `time` is within BACK_GRACE of that start. Before the first
 * scene's grace it wraps round to the last scene.
 */
export function previousMarker(time) {
  const at = wrap(time);
  const earlier = MARKERS.filter((marker) => marker <= at - BACK_GRACE + EPSILON);
  return earlier.length ? earlier[earlier.length - 1] : MARKERS[MARKERS.length - 1];
}

/**
 * The master clock. Play, pause and seek only move the clock; what's drawn is
 * always the frame for `time(now)`. `now` is a performance.now() timestamp in
 * milliseconds, passed in so the clock reads no global time itself.
 */
export function createClock() {
  let base = 0; // the loop time at the last play, pause or seek
  let startedAt = null; // when it started playing, or null while paused
  const clock = {
    get playing() {
      return startedAt !== null;
    },
    time(now) {
      return startedAt === null ? base : wrap(base + (now - startedAt) / 1000);
    },
    play(now) {
      if (startedAt === null) startedAt = now;
    },
    pause(now) {
      base = clock.time(now);
      startedAt = null;
    },
    seek(time, now) {
      base = wrap(time);
      if (startedAt !== null) startedAt = now;
    },
  };
  return Object.freeze(clock);
}
