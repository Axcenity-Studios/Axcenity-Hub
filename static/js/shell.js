// The shell's behaviour: the hover gate, the colour-scheme switch, the nav's
// scrolled state, the cursor spotlight and the motifs (animated line icons). It
// listens on the document (delegation), so it works for any page in either shell.
(function () {
  var root = document.documentElement;
  var reduce = matchMedia("(prefers-reduced-motion: reduce)");

  // ---------- Hover gate ----------
  // After a click, the next page appears under a cursor that hasn't moved, and
  // the browser hovers whatever is now beneath it, so things flip the moment the
  // page appears. Every :hover style waits for <html data-pointer>, set only
  // once the pointer really moves (more than a few pixels, so the browser's own
  // synthetic move doesn't count).
  var start = null;

  function onMove(event) {
    if (start === null) {
      start = { x: event.clientX, y: event.clientY };
      return;
    }
    if (Math.abs(event.clientX - start.x) + Math.abs(event.clientY - start.y) < 4) return;
    root.dataset.pointer = "";
    removeEventListener("pointermove", onMove);
  }
  addEventListener("pointermove", onMove, { passive: true });

  // ---------- Colour scheme ----------
  // The nav's switch steps System → Light → Dark. It switches at once and saves
  // the ax-theme cookie, which the server reads (and validates) for the next
  // page's first paint. Only the three known values are ever written. Without
  // JavaScript the form posts to marketing:theme instead.
  var SCHEMES = ["system", "light", "dark"];
  var SCHEME_LABELS = { system: "System", light: "Light", dark: "Dark" };
  var COOKIE_MAX_AGE = 365 * 24 * 60 * 60; // one year, as config/theme.py

  function setScheme(choice) {
    if (SCHEMES.indexOf(choice) === -1) return;
    root.dataset.schemeChoice = choice;
    var cookie = "ax-theme=" + choice + "; path=/; max-age=" + COOKIE_MAX_AGE + "; SameSite=Lax";
    if (location.protocol === "https:") cookie += "; Secure";
    document.cookie = cookie;
    if (window.axScheme) window.axScheme.apply();
    syncScheme();
  }

  function syncScheme() {
    var choice = root.dataset.schemeChoice;
    if (SCHEMES.indexOf(choice) === -1) choice = "system";
    var next = SCHEMES[(SCHEMES.indexOf(choice) + 1) % SCHEMES.length];
    document.querySelectorAll("#theme-toggle").forEach(function (button) {
      button.value = next;
      button.title = "Theme: " + SCHEME_LABELS[choice];
      button.setAttribute("aria-label", "Theme: " + SCHEME_LABELS[choice] + ". Switch to " + SCHEME_LABELS[next]);
    });
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("#theme-toggle");
    if (!button) return;
    event.preventDefault();
    setScheme(button.value);
  });
  syncScheme();

  // ---------- The nav turns solid on scroll ----------
  // <html data-scrolled> once the page is more than 40 px down; the nav is
  // transparent over the hero above that. Checked once per frame at most.
  var scrollFrame = 0;

  function checkScroll() {
    scrollFrame = 0;
    if (window.scrollY > 40) root.dataset.scrolled = "";
    else delete root.dataset.scrolled;
  }
  addEventListener(
    "scroll",
    function () {
      if (!scrollFrame) scrollFrame = requestAnimationFrame(checkScroll);
    },
    { passive: true }
  );
  checkScroll();

  // ---------- Cursor spotlight ----------
  // The .spotlight element under the mouse gets data-spot and the pointer's
  // position in --spot-x and --spot-y, once per frame. Mouse only (a touch has
  // no hover), and never under reduced motion.
  var lit = null;
  var spotFrame = 0;
  var last = null;

  function light(element) {
    if (lit === element) return;
    if (lit) delete lit.dataset.spot;
    lit = element;
    if (element) element.dataset.spot = "";
  }

  document.addEventListener(
    "pointermove",
    function (event) {
      if (event.pointerType !== "mouse" || reduce.matches) {
        light(null);
        return;
      }
      last = event;
      if (spotFrame) return;
      spotFrame = requestAnimationFrame(function () {
        spotFrame = 0;
        var target = last.target;
        var element = target && target.closest ? target.closest(".spotlight") : null;
        light(element);
        if (!element) return;
        var box = element.getBoundingClientRect();
        element.style.setProperty("--spot-x", Math.round(last.clientX - box.left) + "px");
        element.style.setProperty("--spot-y", Math.round(last.clientY - box.top) + "px");
      });
    },
    { passive: true }
  );
  root.addEventListener("mouseleave", function () {
    light(null);
  });

  // ---------- Motifs ----------
  // Line icons with class="motif" (Home's workflow and stat band, /download/'s
  // systems and files) play each time they come into view: data-on starts them
  // once one is well in view (60 %), and only leaving the screen entirely takes
  // it off, so scrolling back plays it again and a small scroll at the edge
  // doesn't. Under reduced motion, or without IntersectionObserver, they rest drawn.
  var motifs = Array.prototype.slice.call(document.querySelectorAll(".motif"));
  var observes = "IntersectionObserver" in window;
  if (observes && !reduce.matches && motifs.length) {
    var player = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.intersectionRatio >= 0.6) entry.target.dataset.on = "";
          else if (!entry.isIntersecting) delete entry.target.dataset.on;
        });
      },
      { threshold: [0, 0.6] }
    );
    motifs.forEach(function (motif) {
      player.observe(motif);
    });
    root.dataset.motifs = "";
  }
})();
