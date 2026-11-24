// The Home's motion: the hero's film, the rotating headline, scroll reveals and the
// feature pillars' sticky stage (the motifs play through shell.js, on every page).
// Without this script every section shows at rest, the film shows its poster, the
// headline shows its first phrase and the stage shows the first pillar.
// Under reduced motion nothing rotates, reveals or plays; the stage still follows the
// pillars, instantly (the stylesheet turns every transition off).
(function () {
  var root = document.documentElement;
  var reduce = matchMedia("(prefers-reduced-motion: reduce)");
  var observes = "IntersectionObserver" in window;

  // ---------- The hero's film ----------
  // It plays only while the visitor hasn't paused it, at least 30% of it is on
  // screen and the tab is visible; otherwise it's paused. Under reduced motion it
  // doesn't autoplay (the poster shows) and its button plays it. The setting is
  // followed live.
  var film = document.querySelector("[data-film]");
  var filmToggle = document.querySelector("[data-film-toggle]");
  if (film && filmToggle) {
    var video = film.querySelector("video");
    var filmPaused = reduce.matches;
    var filmOnScreen = !observes;

    var updateFilm = function () {
      var running = !filmPaused && filmOnScreen && document.visibilityState === "visible";
      if (running) {
        var playing = video.play();
        if (playing) playing.catch(function () {}); // a refused autoplay leaves the poster
      } else {
        video.pause();
      }
      film.dataset.state = running ? "playing" : "paused";
      filmToggle.dataset.intent = filmPaused ? "paused" : "playing";
      filmToggle.setAttribute("aria-label", filmPaused ? filmToggle.dataset.playLabel : filmToggle.dataset.pauseLabel);
    };

    filmToggle.addEventListener("click", function () {
      filmPaused = !filmPaused;
      updateFilm();
    });
    if (observes) {
      new IntersectionObserver(
        function (entries) {
          var entry = entries[entries.length - 1];
          filmOnScreen = entry.isIntersecting && entry.intersectionRatio >= 0.3 - 0.001;
          updateFilm();
        },
        { threshold: [0, 0.3] }
      ).observe(film);
    }
    document.addEventListener("visibilitychange", updateFilm);
    reduce.addEventListener("change", function () {
      filmPaused = reduce.matches;
      updateFilm();
    });
    filmToggle.hidden = false;
    updateFilm();
  }

  // ---------- Scroll reveals ----------
  // Whatever is already on screen is marked shown first, so turning reveals on
  // (html[data-reveals]) never hides something the visitor can already see.
  var reveals = Array.prototype.slice.call(document.querySelectorAll("[data-reveal]"));

  function onScreen(element) {
    var box = element.getBoundingClientRect();
    return box.top < window.innerHeight && box.bottom > 0;
  }

  if (observes && !reduce.matches && reveals.length) {
    var revealer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.dataset.in = "";
          revealer.unobserve(entry.target);
        });
      },
      { threshold: 0.15 }
    );
    reveals.forEach(function (element) {
      if (onScreen(element)) element.dataset.in = "";
      else revealer.observe(element);
    });
    root.dataset.reveals = "";
  }

  // ---------- Rotating headline ----------
  // Every phrase sits in the same grid cell; one at a time carries data-on. The
  // outgoing phrase rises away (data-out) while the next rises in from below.
  var rotator = document.querySelector("[data-rotator]");
  if (rotator) {
    var phrases = rotator.children;
    var current = 0;
    setInterval(function () {
      if (reduce.matches || document.hidden || phrases.length < 2) return;
      var leaving = phrases[current];
      current = (current + 1) % phrases.length;
      delete leaving.dataset.on;
      leaving.dataset.out = "";
      setTimeout(function () {
        delete leaving.dataset.out;
      }, 800);
      phrases[current].dataset.on = "";
    }, 2800);
  }

  // ---------- Feature pillars ----------
  // The pillar crossing the middle of the screen becomes current: its text goes
  // full strength and the sticky stage shows its media.
  var pillars = document.querySelector("[data-pillars]");
  if (pillars && observes) {
    var texts = pillars.querySelectorAll("[data-pillar]");
    var stage = pillars.querySelectorAll("[data-stage-item]");

    var show = function (index) {
      texts.forEach(function (text) {
        text.toggleAttribute("data-on", text.dataset.pillar === index);
      });
      stage.forEach(function (item) {
        item.toggleAttribute("data-on", item.dataset.stageItem === index);
      });
    };

    var watcher = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) show(entry.target.dataset.pillar);
        });
      },
      { rootMargin: "-45% 0px -45% 0px" }
    );
    // Start on whichever pillar is already across the middle (a #feature-… link),
    // before the observer's first report.
    var middle = window.innerHeight / 2;
    texts.forEach(function (text) {
      var box = text.getBoundingClientRect();
      if (box.top <= middle && box.bottom >= middle) show(text.dataset.pillar);
      watcher.observe(text);
    });
    pillars.dataset.live = "";
  }
})();
