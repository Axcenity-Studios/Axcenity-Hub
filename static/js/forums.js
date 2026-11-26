// The forum's pages (templates/forums/list.html, detail.html). htmx swaps a part in place; focus
// moves by the `autofocus` attribute the swapped part carries (htmx focuses it). htmx 2
// doesn't swap an error answer, which would leave a dead click: a post deleted in another tab
// (404), or a form whose CSRF token went stale with the session (403). Load the page in full
// instead, so the Hub's own page for that answer shows.
document.addEventListener("htmx:responseError", function (event) {
  var detail = event.detail;
  if (detail.requestConfig && detail.requestConfig.verb === "get") {
    window.location.assign(detail.pathInfo.requestPath);
  } else {
    window.location.reload();
  }
});
