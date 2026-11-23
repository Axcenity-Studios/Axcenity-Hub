// Easing and interpolation for the reel's scenes. Every function here is pure:
// the same arguments always give the same answer, with no state between calls,
// so a scene drawn from them is a pure function of time.

/** `value` limited to [low, high]. */
export function clamp(value, low = 0, high = 1) {
  return Math.min(high, Math.max(low, value));
}

/** The point `amount` of the way from `from` to `to` (not clamped). */
export function lerp(from, to, amount) {
  return from + (to - from) * amount;
}

/** How far `time` is through the span starting at `start` and lasting `duration`, 0 to 1. */
export function progress(time, start, duration) {
  return clamp((time - start) / duration);
}

/** Expo-out: the site's cubic-bezier(0.16, 1, 0.3, 1) feel, for progress 0 to 1. */
export function expoOut(amount) {
  const p = clamp(amount);
  return p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
}

/** Ease in and out (cubic): a hand moving the pointer, slow to start and to stop. */
export function easeInOut(amount) {
  const p = clamp(amount);
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
}

/**
 * A damped spring released `seconds` ago, from 0 towards 1, overshooting and
 * settling (closed form, so any moment can be computed directly without
 * stepping through the ones before it). `frequency` is in hertz; `damping`
 * below 1 overshoots.
 */
export function spring(seconds, frequency = 2.2, damping = 0.55) {
  if (seconds <= 0) return 0;
  const omega = 2 * Math.PI * frequency;
  const damped = omega * Math.sqrt(1 - damping * damping);
  const decay = Math.exp(-damping * omega * seconds);
  return 1 - decay * (Math.cos(damped * seconds) + ((damping * omega) / damped) * Math.sin(damped * seconds));
}

/** A rectangle `amount` of the way from `from` to `to`. Returns a new frozen rectangle. */
export function lerpRect(from, to, amount) {
  return Object.freeze({
    x: lerp(from.x, to.x, amount),
    y: lerp(from.y, to.y, amount),
    width: lerp(from.width, to.width, amount),
    height: lerp(from.height, to.height, amount),
  });
}

/** A frozen rectangle. */
export function rect(x, y, width, height) {
  return Object.freeze({ x, y, width, height });
}
