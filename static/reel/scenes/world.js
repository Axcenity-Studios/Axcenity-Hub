// Scene 3 (8–12 s): world. Phase 4 replaces this module with terrain rising and foliage scattering.
// Until then it shows the finished workspace from Scene 1, its viewport still
// turning, so the hero never goes blank. It's a full scene like any other: a
// frozen module with an id, a start, a duration and a pure render().

import { restingWorkspace } from "./workspace.js";

const START = 8;
const DURATION = 4;

export default Object.freeze({
  id: "world",
  start: START,
  duration: DURATION,
  render(context, time, size) {
    restingWorkspace(context, size, START + time);
  },
});
