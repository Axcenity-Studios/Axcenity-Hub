// The docs' progressive extras (templates/documentation/layout.html). Without
// JavaScript the docs work in full: code is plain selectable text, and the
// sidebar's disclosure simply stays open.
(function () {
  var docs = document.querySelector(".docs");
  if (!docs) return;
  var words = docs.dataset;

  // ---------- A copy button on every code block ----------
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      var copied = false;
      try { copied = document.execCommand("copy"); } catch (error) { copied = false; }
      area.remove();
      if (copied) resolve(); else reject();
    });
  }

  docs.querySelectorAll(".doc-code").forEach(function (block) {
    var code = block.querySelector("code");
    if (!code) return;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "doc-copy micro";
    button.textContent = words.copy;
    button.setAttribute("aria-label", words.copyLabel);
    var timer = null;
    function show(text) {
      button.textContent = text;
      button.setAttribute("aria-label", text);
      clearTimeout(timer);
      timer = setTimeout(function () {
        button.textContent = words.copy;
        button.setAttribute("aria-label", words.copyLabel);
      }, 2000);
    }
    button.addEventListener("click", function () {
      copy(code.textContent).then(
        function () { show(words.copied); },
        function () { show(words.copyFailed); }
      );
    });
    block.appendChild(button);
  });

  // ---------- The sidebar's disclosure ----------
  // Open beside the article on wide screens; a closed disclosure below 1024 px (the
  // inline script after it closes it before first paint).
  var nav = document.getElementById("docs-nav");
  var wide = matchMedia("(min-width: 1024px)");
  if (nav) {
    var follow = function () { nav.open = wide.matches; };
    if (wide.addEventListener) wide.addEventListener("change", follow);
    else wide.addListener(follow);

    // On wide screens the sidebar scrolls on its own: bring the current page into view
    // (a class deep in the API reference would otherwise sit below its fold).
    var box = nav.closest(".docs-sidebar");
    var current = nav.querySelector('.docs-link[aria-current="page"]');
    if (box && current && wide.matches) {
      var offset = current.getBoundingClientRect().top - box.getBoundingClientRect().top;
      if (offset > box.clientHeight - 48) box.scrollTop += offset - box.clientHeight / 3;
    }
  }
})();
