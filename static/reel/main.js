// The reel's entry point (loaded as a module by templates/marketing/media/reel.html).
// It checks that this browser can draw the reel, then loads the player. If the
// canvas isn't available, or any reel module fails to load or mount, the
// renderer capture shows instead (data-fallback) and the controls stay hidden.

const reel = document.querySelector("[data-reel]");

function fallBack(error) {
  delete reel.dataset.pending;
  delete reel.dataset.live;
  reel.dataset.fallback = "";
  const controls = document.getElementById(reel.dataset.controls);
  if (controls) controls.hidden = true;
  if (error) console.warn("The showcase reel can't run here, so the still image shows instead.", error);
}

if (reel) {
  const canvas = reel.querySelector("canvas");
  let g = null;
  try {
    g = canvas && canvas.getContext ? canvas.getContext("2d") : null;
  } catch (error) {
    g = null;
  }
  if (!g) {
    fallBack();
  } else {
    import("./player.js")
      .then((player) => player.mount(reel, canvas, g))
      .catch(fallBack);
  }
}
