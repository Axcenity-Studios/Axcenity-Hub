"""The docs in headless Chromium: the longest API page fits a phone, and the copy button copies.

Each page may reach only the live server (browser_server); every other request is
aborted. They need the built stylesheet: `uv run python manage.py tailwind build`.
`open_home` is in tests/conftest.py.
"""

import os

import pytest

from documentation import library

# Playwright's sync API runs an event loop in this thread; the database teardown
# that the live server needs is synchronous and harmless here.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

LIBRARY = library.library()


def longest_api_page() -> library.Page:
    """The longest class or data type page (the API's longest code and member lists)."""
    api = [path for path in LIBRARY.paths if path.startswith(("api/classes/", "api/types/"))]
    path = max(api, key=lambda p: (LIBRARY.root / p).stat().st_size)
    return LIBRARY.page(path)


def test_a_long_api_page_fits_a_phone_and_its_copy_button_copies(open_home):
    page_data = longest_api_page()
    page, errors = open_home(
        path=page_data.url,
        width=375,
        height=812,
        permissions=["clipboard-read", "clipboard-write"],
    )
    page.wait_for_selector(".doc-copy")  # docs.js has run

    # Nothing pushes the page sideways: wide code and tables scroll in their own box.
    assert page.evaluate("document.documentElement.scrollWidth") <= 375
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    assert page.evaluate("document.documentElement.scrollWidth") <= 375
    assert page.evaluate(
        "[...document.querySelectorAll('.doc-code pre, .doc-table')]"
        ".every(box => box.getBoundingClientRect().right <= 375.5)"
    )

    # On a phone the sidebar is a closed disclosure at the top, and opens when asked.
    assert page.evaluate("document.getElementById('docs-nav').open") is False
    page.click(".docs-nav-toggle")
    assert page.evaluate("document.getElementById('docs-nav').open") is True

    # Every code block has a copy button, and it puts the block's exact text on the clipboard.
    blocks = page.locator(".doc-code")
    assert blocks.count() == page.locator(".doc-copy").count() > 1
    block = blocks.nth(1)
    block.scroll_into_view_if_needed()
    expected = block.locator("code").text_content()
    block.locator(".doc-copy").click()
    page.wait_for_function(
        "el => el.textContent === 'Copied'", arg=block.locator(".doc-copy").element_handle()
    )
    assert page.evaluate("navigator.clipboard.readText()") == expected
    assert errors == []
