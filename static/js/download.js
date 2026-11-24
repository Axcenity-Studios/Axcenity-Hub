// /download/'s license agreement. Every Download link (a[data-download]) opens the
// agreement dialog instead of leaving the page: it names the file, and "Agree and
// download" stays disabled until the box is ticked. The dialog's form posts to
// /download/agree/, which checks the agreement again and redirects to the file, so the
// page stays put while the browser downloads it.
// Without this script (or without <dialog>), and on a modified click (new tab or
// window), the links go to /download/agree/: the same agreement as a page.
(function () {
  var dialog = document.querySelector("[data-agreement]");
  if (!dialog || typeof dialog.showModal !== "function") return;
  var form = dialog.querySelector("form");
  var file = form.elements.file;
  var box = form.elements.agree;
  var submit = form.querySelector('[type="submit"]');
  var named = dialog.querySelector("[data-agreement-file]");

  function sync() {
    submit.disabled = !box.checked;
  }

  document.addEventListener("click", function (event) {
    var link = event.target.closest("a[data-download]");
    if (!link || event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    file.value = link.dataset.file;
    named.textContent = link.dataset.file + " · " + link.dataset.size;
    box.checked = false;
    sync();
    dialog.showModal();
  });

  box.addEventListener("change", sync);
  dialog.querySelector("[data-agreement-cancel]").addEventListener("click", function () {
    dialog.close();
  });
  // Close once the form has gone (the download starts; the page doesn't change).
  form.addEventListener("submit", function () {
    setTimeout(function () {
      dialog.close();
    }, 0);
  });
  // A click on the backdrop (the dialog element itself, outside its content) closes it.
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) dialog.close();
  });
})();
