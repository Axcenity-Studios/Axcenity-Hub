// The project pages' progressive extras. Without JavaScript both pages work as plain forms.
//
// 1. A copy button beside each webhook value (templates/projects/detail.html). Without
//    JavaScript the buttons stay hidden and the values are plain selectable text.
// 2. The team page's invite field (templates/projects/members.html) becomes a combobox:
//    as an Owner types, matching members appear under it (views.MemberSearchView); choosing
//    one adds them to "Inviting" as a chip (with a × to take them out), so several people
//    are invited at once. Without JavaScript the field takes comma-separated usernames.
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

(function () {
  var input = document.querySelector("[data-member-search]");
  var form = input && input.form;
  if (!form || !form.dataset.searchUrl || !window.fetch) return;
  var words = form.dataset;
  var field = input.closest(".app-field") || input.parentNode;
  var submit = form.querySelector("[data-invite-submit]");
  var max = parseInt(words.batchMax, 10) || 10;

  function fill(text, values) {
    return text.replace(/\{(\w+)\}/g, function (_, key) { return values[key]; });
  }

  // "Inviting": a chip for each chosen member, above the field. Each chip carries a hidden
  // username input, so the form sends one username per chip (the view reads them all).
  var chosen = document.createElement("div");
  chosen.className = "grid gap-2";
  chosen.hidden = true;
  chosen.setAttribute("data-inviting", "");
  var heading = document.createElement("p");
  heading.className = "micro text-fg-weak";
  var chips = document.createElement("ul");
  chips.className = "flex flex-wrap gap-2";
  chips.setAttribute("aria-label", words.invitingLabel);
  chosen.appendChild(heading);
  chosen.appendChild(chips);
  input.insertAdjacentElement("beforebegin", chosen);

  // The field's help explains commas for a form without JavaScript; here it explains
  // the suggestions instead.
  var help = field.querySelector(".app-help");
  if (help && words.hint) {
    help.id = "invite-search-hint";
    help.textContent = words.hint;
    input.setAttribute("aria-describedby", help.id);
  }

  var box = document.createElement("div");
  box.id = "invite-suggestions";
  box.className = "overflow-hidden rounded-md bg-surface ring-1 ring-line-strong ring-inset";
  box.hidden = true;
  var status = document.createElement("p");
  status.className = "sr-only";
  status.setAttribute("aria-live", "polite");
  input.insertAdjacentElement("afterend", box);
  box.insertAdjacentElement("afterend", status);

  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", "invite-suggestions-list");

  var timer = null;
  var request = null;
  var active = -1;

  function usernames() {
    return Array.prototype.map.call(chips.children, function (chip) {
      return chip.dataset.chip.toLowerCase();
    });
  }
  function refresh() {
    var count = chips.children.length;
    chosen.hidden = count === 0;
    heading.textContent = words.inviting + " · " + count;
    if (submit) submit.textContent = count > 1 ? fill(words.sendMany, { count: count }) : words.sendOne;
  }
  function options() {
    return Array.prototype.slice.call(box.querySelectorAll('[role="option"]'));
  }
  function choosable() {
    return options().filter(function (o) { return o.getAttribute("aria-disabled") !== "true"; });
  }
  // Members already chosen show as "Added" and can't be chosen twice.
  function markChosen() {
    var taken = usernames();
    options().forEach(function (option) {
      if (taken.indexOf(option.dataset.username.toLowerCase()) === -1) return;
      option.setAttribute("aria-disabled", "true");
      option.dataset.state = "chosen";
      if (!option.querySelector("[data-chosen-tag]")) {
        var tag = document.createElement("span");
        tag.className = "pj-tag micro shrink-0";
        tag.setAttribute("data-chosen-tag", "");
        tag.textContent = words.chosen;
        option.appendChild(tag);
      }
    });
  }
  function close() {
    box.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    active = -1;
  }
  function highlight(index) {
    var list = choosable();
    options().forEach(function (o) { o.setAttribute("aria-selected", "false"); });
    if (!list.length) { active = -1; return; }
    active = (index + list.length) % list.length;
    list[active].setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", list[active].id);
    list[active].scrollIntoView({ block: "nearest" });
  }
  function removeChip(chip) {
    var name = chip.dataset.name;
    chip.remove();
    refresh();
    status.textContent = fill(words.chipRemoved, { name: name, count: chips.children.length });
    input.focus();
  }
  function addChip(option) {
    if (!option || option.getAttribute("aria-disabled") === "true") return;
    var username = option.dataset.username;
    if (usernames().indexOf(username.toLowerCase()) !== -1 || chips.children.length >= max) return;
    var name = option.querySelector("[data-name]").textContent.trim();
    var chip = document.createElement("li");
    chip.className = "inline-flex max-w-full items-center gap-2 rounded-full bg-inset py-1 pr-1 pl-1 ring-1 ring-line-strong ring-inset";
    chip.dataset.chip = username;
    chip.dataset.name = name;
    var avatar = option.querySelector(".app-avatar");
    if (avatar) {
      avatar = avatar.cloneNode(true);
      avatar.style.setProperty("--avatar", "24px");
      chip.appendChild(avatar);
    }
    var label = document.createElement("span");
    label.className = "truncate text-sm text-fg-strong";
    label.textContent = name;
    chip.appendChild(label);
    if (name !== username) {
      var handle = document.createElement("span");
      handle.className = "truncate font-mono text-xs text-fg-secondary";
      handle.textContent = username;
      chip.appendChild(handle);
    }
    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "grid size-6 shrink-0 place-items-center rounded-full text-fg-secondary";
    remove.setAttribute("aria-label", fill(words.chipRemove, { name: name }));
    remove.textContent = "×";
    remove.addEventListener("click", function () { removeChip(chip); });
    chip.appendChild(remove);
    var hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "username";
    hidden.value = username;
    chip.appendChild(hidden);
    chips.appendChild(chip);
    refresh();
    // Ready for the next person: the typed text goes, the list closes.
    input.value = "";
    box.innerHTML = "";
    close();
    status.textContent = fill(words.chipAdded, { name: name, count: chips.children.length });
    input.focus();
  }
  function show(html) {
    box.innerHTML = html;
    markChosen();
    var summary = box.querySelector("[data-count-text]");
    status.textContent = summary ? summary.dataset.countText : "";
    if (!html.trim()) { close(); return; }
    box.hidden = false;
    input.setAttribute("aria-expanded", options().length ? "true" : "false");
    active = -1;
  }
  function search() {
    var query = input.value.trim();
    if (request) request.abort();
    if (query.length < 2) { box.innerHTML = ""; status.textContent = ""; close(); return; }
    request = window.AbortController ? new AbortController() : null;
    fetch(form.dataset.searchUrl + "?q=" + encodeURIComponent(query), {
      credentials: "same-origin",
      headers: { "X-Requested-With": "fetch" },
      signal: request ? request.signal : undefined
    })
      .then(function (response) { return response.ok ? response.text() : ""; })
      .then(function (html) { if (input.value.trim() === query) show(html); })
      .catch(function () { /* aborted by the next keystroke, or offline: the form still works */ });
  }

  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(search, 150);
  });
  input.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (box.hidden) return;
      event.preventDefault();
      highlight(active + (event.key === "ArrowDown" ? 1 : -1));
    } else if (event.key === "Enter" && !box.hidden && active >= 0) {
      event.preventDefault();
      addChip(choosable()[active]);
    } else if (event.key === "Escape" && !box.hidden) {
      event.preventDefault();
      close();
    } else if (event.key === "Backspace" && input.value === "" && chips.lastElementChild) {
      removeChip(chips.lastElementChild);
    }
  });
  // Pressing on a suggestion keeps the focus in the field; moving over one highlights it.
  box.addEventListener("mousedown", function (event) { event.preventDefault(); });
  box.addEventListener("click", function (event) {
    addChip(event.target.closest('[role="option"]'));
  });
  box.addEventListener("pointermove", function (event) {
    var option = event.target.closest('[role="option"]');
    var index = choosable().indexOf(option);
    if (index >= 0 && index !== active) highlight(index);
  });
  input.addEventListener("blur", function () { setTimeout(close, 100); });
  input.addEventListener("focus", function () {
    if (box.innerHTML.trim() && input.value.trim().length >= 2) {
      box.hidden = false;
      input.setAttribute("aria-expanded", options().length ? "true" : "false");
    }
  });
})();
