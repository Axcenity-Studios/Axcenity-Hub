// Scene 4 (12–16 s): logic. Phase 4 replaces this module with When touched → Spawn decal blocks and their Luau.
// Until then it shows the finished workspace from Scene 1, its viewport still
// turning, so the hero never goes blank. It's a full scene like any other: a
// frozen module with an id, a start, a duration and a pure render().

import { restingWorkspace } from "./workspace.js";

const START = 12;
const DURATION = 4;

export default Object.freeze({
  id: "logic",
  start: START,
  duration: DURATION,
  render(context, time, size) {
    restingWorkspace(context, size, START + time);
  },
});
