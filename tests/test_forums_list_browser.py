"""The forum list in headless Chromium: searching, filtering, sorting and paging swap the
list in place through HTMX, with the address bar following (shareable URLs), focus staying
in the search box while typing and moving to the list's heading after the pager, Back
restoring the list and its controls together, and the same form and links working with
JavaScript off; at 360 and 1280 px, dark and light. Screenshots go to screenshots/forums/."""

import os
from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.utils import timezone

from forums import strings
from forums.listing import POSTS
from forums.models import Comment, ForumPost, Rating

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

PASSWORD = "a-Long-pass-7731"
ROWS = "document.querySelectorAll('#post-list .fm-row').length"


def make_member(username: str):
    email = f"{username}@example.com"
    user = get_user_model().objects.create_user(username, email, PASSWORD)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=True)
    return user


def fill_forum() -> None:
    """45 posts an hour apart, "… 00" the newest: three pages. Posts 00, 15 and 30 are about
    decals; 15 is rated 5 stars and 30 has a comment."""
    ada, bob = make_member("ada"), make_member("bob")
    now = timezone.now()
    for number in range(45):
        kind = "Decal question" if number % 15 == 0 else "Terrain note"
        post = ForumPost.objects.create(
            author=ada, title=f"{kind} {number:02d}", body="Some text about the engine."
        )
        ForumPost.objects.filter(pk=post.pk).update(created=now - timedelta(hours=number + 1))
        if number == 15:
            Rating.objects.create(post=post, user=bob, score=5)
        if number == 30:
            Comment.objects.create(post=post, author=bob, body="A comment.")


def fits(page, width: int) -> None:
    """No sideways scroll, and no control or panel wider than the page."""
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    assert page.evaluate(
        "[...document.querySelectorAll('.ls-controls input, .ls-controls select, .ls-controls"
        " .btn, .ls-pager > *, .pj-panel')].every(box => {"
        "  const sides = box.getBoundingClientRect();"
        "  return sides.left >= 0 && sides.right <= innerWidth + 0.5; })"
    )


def focused(page) -> str:
    return page.evaluate(
        "(() => { const e = document.activeElement;"
        "  return e.tagName.toLowerCase() + (e.id ? '#' + e.id : ''); })()"
    )


def titles(page) -> list[str]:
    return page.locator("#post-list .fm-row-title").all_inner_texts()


def at(page, query: str, rows: int) -> None:
    """Wait until the address bar holds `query` and the list shows `rows` posts."""
    page.wait_for_url(lambda url: url.endswith(f"/forums/{query}"))
    page.wait_for_function(f"{ROWS} === {rows}")


def watch(page) -> None:
    page.evaluate(
        "window.__noReload = 1; window.__loads = 0;"
        "document.addEventListener('htmx:load', () => window.__loads++)"
    )


def swap(page, action) -> None:
    """Do `action` and wait until htmx has swapped in its answer and set it up (`htmx:load`).
    The rows alone aren't enough to wait on: a key pressed on a link htmx hasn't set up yet
    follows it as a plain link."""
    before = page.evaluate("window.__loads")
    action()
    page.wait_for_function(f"window.__loads > {before}")


def page_label(number: int, total: int) -> str:
    return POSTS.words.page.format(number=number, total=total)


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_the_list_searches_filters_sorts_and_pages_in_place(open_home, width, scheme):
    fill_forum()
    shots = f"screenshots/forums/{{}}-{width}-{scheme}.png"
    page, errors = open_home(path="/forums/", width=width, scheme=scheme)
    watch(page)
    assert len(titles(page)) == 20 and titles(page)[0] == "Decal question 00"
    assert page.inner_text(".ls-page-label") == page_label(1, 3)
    fits(page, width)
    page.screenshot(path=shots.format("list-pages"), full_page=True)

    # Typing searches after a pause: the list swaps, the address follows, focus stays put.
    page.focus("#post-list-q")
    swap(page, lambda: page.keyboard.type("decal"))
    at(page, "?q=decal", 3)
    assert titles(page) == ["Decal question 00", "Decal question 15", "Decal question 30"]
    assert focused(page) == "input#post-list-q"
    assert page.input_value("#post-list-q") == "decal"
    assert page.inner_text("#post-list-status") == "3 posts"
    assert page.text_content("[data-post-count]") == "3"
    assert page.locator("[data-pager]").count() == 0

    # Choosing a sort and a filter does the same, each keeping the rest of the state.
    swap(page, lambda: page.select_option("#post-list-sort", "oldest"))
    at(page, "?q=decal&sort=oldest", 3)
    assert titles(page)[0] == "Decal question 30"
    swap(page, lambda: page.select_option("#post-list-rating", "4"))
    at(page, "?q=decal&sort=oldest&rating=4", 1)
    assert titles(page) == ["Decal question 15"]
    assert page.inner_text("#post-list-status") == "1 post"
    fits(page, width)
    page.screenshot(path=shots.format("list-narrowed"), full_page=True)

    # Nothing matching says so, in the list and to a screen reader.
    swap(page, lambda: page.select_option("#post-list-comments", "some"))
    at(page, "?q=decal&sort=oldest&comments=some&rating=4", 0)
    assert page.locator("[data-no-match]").is_visible()
    assert page.inner_text("#post-list-status") == strings.NO_MATCH_TITLE
    fits(page, width)
    page.screenshot(path=shots.format("list-no-match"), full_page=True)

    # Back: the earlier list and the controls that go with it, without leaving the page.
    swap(page, page.go_back)
    at(page, "?q=decal&sort=oldest&rating=4", 1)
    page.wait_for_function("document.querySelector('#post-list-comments').value === ''")
    assert page.input_value("#post-list-rating") == "4"
    assert page.input_value("#post-list-q") == "decal"
    swap(page, page.go_back)
    at(page, "?q=decal&sort=oldest", 3)
    page.wait_for_function("document.querySelector('#post-list-rating').value === ''")
    assert page.input_value("#post-list-sort") == "oldest"
    assert page.evaluate("window.__noReload === 1")

    # The pager, by keyboard: the list swaps, and its heading takes focus, in view.
    swap(page, lambda: page.fill("#post-list-q", ""))
    at(page, "?sort=oldest", 20)
    for query, label, rows, first in (
        ("?sort=oldest&page=2", page_label(2, 3), 20, "Terrain note 24"),
        ("?sort=oldest&page=3", page_label(3, 3), 5, "Terrain note 04"),
    ):
        page.focus("#post-list-next")
        swap(page, lambda: page.keyboard.press("Enter"))
        page.wait_for_url(lambda url, query=query: url.endswith(f"/forums/{query}"))
        page.wait_for_function(
            f"document.querySelector('.ls-page-label').textContent === '{label}'"
            " && document.activeElement.id === 'posts-title'"
        )
        assert len(titles(page)) == rows and titles(page)[0] == first
        assert page.evaluate(
            "(() => { const top = document.querySelector('#posts-title').getBoundingClientRect().top;"
            "  return top >= 0 && top < innerHeight; })()"
        )
    assert page.locator("#post-list-next").count() == 0
    fits(page, width)
    page.screenshot(path=shots.format("list-last-page"), full_page=True)
    page.focus("#post-list-previous")
    swap(page, lambda: page.keyboard.press("Enter"))
    at(page, "?sort=oldest&page=2", 20)
    page.wait_for_function("document.activeElement.id === 'posts-title'")
    assert page.evaluate("window.__noReload === 1")

    # Clear loads the list afresh, its form reset.
    swap(page, lambda: page.fill("#post-list-q", "zzz"))
    at(page, "?q=zzz&sort=oldest", 0)  # a new search starts at its first page
    page.click("[data-clear]")
    at(page, "", 20)
    assert (
        page.input_value("#post-list-q") == "" and page.input_value("#post-list-sort") == "newest"
    )
    assert errors == []


def test_a_copied_address_opens_the_same_list(open_home):
    fill_forum()
    page, errors = open_home(path="/forums/?q=terrain&sort=oldest&page=3")
    assert page.inner_text(".ls-page-label") == page_label(3, 3)
    assert titles(page) == ["Terrain note 02", "Terrain note 01"]
    assert page.input_value("#post-list-q") == "terrain"
    assert page.input_value("#post-list-sort") == "oldest"
    assert errors == []


def test_the_list_works_without_javascript(open_home):
    fill_forum()
    page, errors = open_home(path="/forums/", java_script_enabled=False)
    page.fill("#post-list-q", "decal")
    page.select_option("#post-list-sort", "oldest")
    page.click(".ls-apply")
    page.wait_for_url("**/forums/?q=decal*sort=oldest")
    assert titles(page) == ["Decal question 30", "Decal question 15", "Decal question 00"]
    assert page.input_value("#post-list-q") == "decal"
    page.fill("#post-list-q", "")
    page.select_option("#post-list-sort", "newest")
    page.click(".ls-apply")
    page.wait_for_url("**/forums/?q=*sort=newest")
    assert len(titles(page)) == 20
    page.click("#post-list-next")
    page.wait_for_url("**/forums/?page=2")
    assert page.inner_text(".ls-page-label") == page_label(2, 3)
    assert titles(page)[0] == "Terrain note 20"
    page.click("#post-list-previous")
    page.wait_for_url("**/forums/")
    assert titles(page)[0] == "Decal question 00"
    assert errors == []
