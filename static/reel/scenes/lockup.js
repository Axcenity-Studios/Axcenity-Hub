// The outro (24–26 s): the workspace, as the Logic scene left it, draws in
// towards its centre and fades as one picture (an offscreen layer, so
// overlapping windows never show through each other mid-fade), the Axcenity
// wordmark (which includes the mark) comes up once it's mostly gone, then
// fades to the empty page: exactly Scene 1's first frame, so the loop wraps
// without a visible reset. The lockup frame (the logo fully shown, for reduced
// motion) is 1 s in.

import { clamp, expoOut, lerp, progress } from "../easing.js";
import { stageRect } from "../drawing/layout.js";
import { viewWorkspace } from "./workspace.js";
import { logicEnd } from "./logic.js";

const START = 24;
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
    const away = expoOut(progress(time, 0, 0.6));
    if (away < 1) {
      const stage = stageRect(size);
      const cx = stage.x + stage.width / 2;
      const cy = stage.y + stage.height / 2;
      const scale = lerp(1, 0.94, away);
      context.layer(1 - away, (layer) => {
        layer.g.translate(cx, cy);
        layer.g.scale(scale, scale);
        layer.g.translate(-cx, -cy);
        viewWorkspace(layer, size, START + time, logicEnd(layer, size));
      });
    }
    const arrive = expoOut(progress(time, 0.3, 0.6));
    const leave = progress(time, 1.45, 0.55);
    logo(context, size, arrive * (1 - leave * leave), lerp(0.96, 1, arrive));
  },
});
