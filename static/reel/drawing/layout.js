// Where the workspace's windows and panels go, as pure functions of the
// logical size. The dock follows the editor's default layout
// (crates/editor/src/layout.rs default_dock): the Scene's tabs with the
// Console's tabs below them, and a right column with the Explorer above
// Properties. On wide screens two panels end up in windows of their own: the
// Properties on a monitor to the right, the Console on one to the left, in
// the upper left of the hero that the copy leaves free.

import { clamp, rect } from "../easing.js";

/** Compact mode's stage: its top and its height as a share of its width. The hero's
 * stylesheet reserves the same space above the copy on phones (.hero-copy). */
export const COMPACT_TOP = 108;
export const COMPACT_ASPECT = 0.62;

/** The main window's region: upper right on wide screens, above the copy on phones. */
export function stageRect(size) {
  if (size.compact) {
    const width = size.width - 32;
    return rect(16, COMPACT_TOP, width, width * COMPACT_ASPECT);
  }
  const right = size.width - Math.max(32, size.width * 0.04);
  const top = Math.max(112, size.height * 0.12);
  let width = Math.min(size.width * 0.54, 1120);
  let height = width * 0.6;
  const room = size.height * 0.6 - top;
  if (height > room) {
    height = Math.max(180, room);
    width = height / 0.6;
  }
  return rect(right - width, top, width, height);
}

/** The size unit: 1 at an 820 px wide stage, larger type in compact mode. */
export function unitFor(size, stage) {
  return size.compact ? 1.15 : clamp(stage.width / 820, 0.8, 1.35);
}

/** A window's body: the window less its title bar. */
export function bodyOf(frame, titleBar) {
  return rect(frame.x, frame.y + titleBar, frame.width, frame.height - titleBar);
}

/** Every rectangle the workspace needs, frozen. Panels are docked places; windows are whole windows. */
export function workspaceLayout(size) {
  const stage = stageRect(size);
  const u = unitFor(size, stage);
  const titleBar = 26 * u;
  const tabBar = 26 * u;
  const main = size.compact ? stage : rect(stage.x, stage.y, stage.width * 0.76, stage.height * 0.9);
  const body = bodyOf(main, titleBar);
  const split = body.x + body.width * (size.compact ? 0.58 : 0.68);
  const left = rect(body.x, body.y, split - body.x, body.height);
  const right = rect(split, body.y, body.x + body.width - split, body.height);

  if (size.compact) {
    return Object.freeze({ stage, u, titleBar, tabBar, main, scene: left, explorer: right });
  }

  const scene = rect(left.x, left.y, left.width, left.height * 0.7);
  const bottom = rect(left.x, scene.y + scene.height, left.width, left.height - scene.height);
  const explorer = rect(right.x, right.y, right.width, right.height * 0.48);
  const properties = rect(right.x, explorer.y + explorer.height, right.width, right.height - explorer.height);

  // Monitor 2, to the right: tall enough for the Properties' sections.
  const propertiesWidth = stage.width * 0.32;
  const propertiesWindow = rect(
    stage.x + stage.width - propertiesWidth,
    stage.y + stage.height * 0.14,
    propertiesWidth,
    stage.height * 0.94
  );

  // Monitor 3, to the left, above the hero's copy.
  const leftEdge = Math.max(32, size.width * 0.035);
  const leftRoom = stage.x - size.width * 0.035 - leftEdge;
  const consoleWidth = clamp(Math.min(size.width * 0.3, leftRoom), 160, 520);
  const consoleWindow = rect(leftEdge, stage.y + stage.height * 0.02, consoleWidth, Math.max(130 * u, consoleWidth * 0.5));

  return Object.freeze({
    stage,
    u,
    titleBar,
    tabBar,
    main,
    scene,
    console: bottom,
    explorer,
    properties,
    propertiesWindow,
    consoleWindow,
  });
}
