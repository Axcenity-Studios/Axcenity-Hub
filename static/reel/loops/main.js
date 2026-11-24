// The animated recreations' entry point (loaded as a module at the end of
// templates/marketing/home.html). Each [data-loop] figure names its
// loop; this loads the player and that loop, and mounts it. Where a loop can't
// run (no 2D canvas, or a module fails to load or mount) its static drawing
// simply stays, as it does without JavaScript.

const LOOPS = Object.freeze({
  editor: () => import("./editor.js"),
  terrain: () => import("./terrain.js"),
  logic: () => import("./logic.js"),
  toolbox: () => import("./toolbox.js"),
  wipe: () => import("./wipe.js"),
  animation: () => import("./animation.js"),
});

for (const figure of document.querySelectorAll("[data-loop]")) {
  const canvas = figure.querySelector("canvas");
  const load = LOOPS[figure.dataset.loop];
  let g = null;
  try {
    g = canvas && canvas.getContext ? canvas.getContext("2d") : null;
  } catch (error) {
    g = null;
  }
  if (g && load) {
    Promise.all([import("./player.js"), load()])
      .then(([player, loop]) => player.mount(figure, canvas, g, loop.default))
      .catch((error) => console.warn("An animated recreation can't run here; its drawing shows instead.", error));
  }
}
