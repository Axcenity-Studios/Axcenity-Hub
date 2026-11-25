"""/credits/ in headless Chromium: it fits a phone and a desktop in dark and light with no
sideways scroll, a licence group opens and closes, and the NOTICE draws its dividers (the
download agreement's NOTICE tab uses the same markup). Screenshots go to screenshots/credits/ for review by eye."""

import os

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_the_credits_page_fits_the_screen(open_home, width, scheme):
    page, errors = open_home(path="/credits/", width=width, scheme=scheme)
    assert page.locator("h1").inner_text() == "Built on other people's work"
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    groups = page.locator(".cr-group")
    assert groups.first.evaluate("d => d.open")
    second = groups.nth(1)
    assert not second.evaluate("d => d.open")
    second.locator("summary").click()
    assert second.evaluate("d => d.open")
    assert second.locator(".cr-item").first.is_visible()
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    rules = page.locator("[data-credits=notice] hr.dl-legal-rule")
    assert rules.count() == 2
    rules.first.scroll_into_view_if_needed()
    assert rules.first.bounding_box()["height"] >= 1
    page.locator("#notice").screenshot(path=f"screenshots/credits/notice-{width}-{scheme}.png")
    page.screenshot(path=f"screenshots/credits/credits-{width}-{scheme}.png", full_page=True)
    page.locator("#hub").screenshot(path=f"screenshots/credits/hub-{width}-{scheme}.png")
    assert errors == []
