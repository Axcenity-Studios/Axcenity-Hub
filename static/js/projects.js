// The project pages' one progressive extra: a copy button beside each webhook value
// (templates/projects/detail.html). Without JavaScript the buttons stay hidden and the
// values are plain selectable text.
(function () {
  var buttons = document.querySelectorAll("[data-copy]");
  if (!buttons.length) return;

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

  buttons.forEach(function (button) {
    var target = document.getElementById(button.getAttribute("data-copy"));
    var label = button.querySelector("[data-copy-text]");
    if (!target || !label) return;
    var idle = label.textContent;
    var timer = null;
    function show(text) {
      label.textContent = text;
      clearTimeout(timer);
      timer = setTimeout(function () { label.textContent = idle; }, 2000);
    }
    button.hidden = false;
    button.addEventListener("click", function () {
      copy(target.textContent.trim()).then(
        function () { show(button.dataset.copied); },
        function () { show(button.dataset.copyFailed); }
      );
    });
  });
})();
