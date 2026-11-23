// The Home's motion: the rotating headline, scroll reveals and the feature
// pillars' sticky stage. Without this script every section shows at rest, the
// headline shows its first phrase and the stage shows the first pillar.
// Under reduced motion nothing rotates or reveals; the stage still follows the
// pillars, instantly (the stylesheet turns every transition off).
(function () {
  var root = document.documentElement;
  var reduce = matchMedia("(prefers-reduced-motion: reduce)");
  var observes = "IntersectionObserver" in window;

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
