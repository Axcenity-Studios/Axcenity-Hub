// The outro (16–18 s): the workspace draws in towards its centre and fades as
// the Axcenity logo (the wordmark, which includes the mark) comes up; then the logo fades to the
// empty page, which is exactly the first frame of Scene 1, so the loop wraps
// without a visible reset. Phase 4 adds the panels collapsing into the logo.
// The lockup frame (the logo fully shown, for reduced motion) is 1 s in.

import { clamp, expoOut, lerp, progress } from "../easing.js";
import { restingWorkspace, stageRect } from "./workspace.js";

const START = 16;
const DURATION = 2;

function logo(context, size, alpha, scale) {
  const { g, images } = context;
  if (alpha <= 0 || !images.wordmark) return;
  const stage = stageRect(size);
  const width = clamp(stage.width * 0.5, 160, 520);
  const height = width * (images.wordmark.height / images.wordmark.width);
  const cx = stage.x + stage.width / 2;
  const cy = stage.y + stage.height / 2;
  g.save();
  g.globalAlpha = alpha;
  g.translate(cx, cy);
  g.scale(scale, scale);
  g.drawImage(images.wordmark, -width / 2, -height / 2, width, height);
  g.restore();
}

export default Object.freeze({
  id: "lockup",
  start: START,
  duration: DURATION,
  render(context, time, size) {
    const { g } = context;
    const away = expoOut(progress(time, 0, 0.7));
    if (away < 1) {
      const stage = stageRect(size);
      const cx = stage.x + stage.width / 2;
      const cy = stage.y + stage.height / 2;
      const scale = lerp(1, 0.9, away);
      g.save();
      g.globalAlpha = 1 - away;
      g.translate(cx, cy);
      g.scale(scale, scale);
      g.translate(-cx, -cy);
      restingWorkspace(context, size, START + time);
      g.restore();
    }
    const arrive = expoOut(progress(time, 0.25, 0.6));
    const leave = progress(time, 1.45, 0.55);
    logo(context, size, arrive * (1 - leave * leave), lerp(0.94, 1, arrive));
  },
});
