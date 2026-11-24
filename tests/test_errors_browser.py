"""The error pages in headless Chromium: the 404 a visitor meets, and the CSRF and 500 pages
(through the development preview), fit a phone and a desktop in dark and light with no
sideways scroll. Screenshots go to screenshots/errors/ for review by eye."""

import os

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_the_error_pages_fit_the_screen(open_home, settings, width, scheme):
    page, errors = open_home(path="/no-such-page/", width=width, scheme=scheme)
    assert page.locator("main[data-error='404'] h1").inner_text() == "This page doesn't exist."
    for kind in ["404", "csrf", "500"]:
        if kind != "404":
            settings.DEBUG = True  # the preview exists on a development server only
            page.goto(page.url.split("/no-such-page/")[0].split("/errors/")[0] + f"/errors/{kind}/")
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        assert page.evaluate(
            "[...document.querySelectorAll('.err-panel .btn, .err-code, .err-detail')]"
            ".every(box => box.getBoundingClientRect().right <= innerWidth + 0.5)"
        )
        page.wait_for_timeout(1200)  # the motif draws in
        page.screenshot(path=f"screenshots/errors/{kind}-{width}-{scheme}.png", full_page=True)
    # The page's own 404 is the only console error a 404 may log (the browser's, for its status).
    assert all("404" in e or "500" in e or "403" in e for e in errors)
