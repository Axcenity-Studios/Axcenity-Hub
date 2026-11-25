"""A forum post's page in headless Chromium: its author edits and deletes it in place through
HTMX, by keyboard, without the page reloading, with focus following each swap; the same
actions work as full pages with JavaScript off; and the pages fit a phone and a desktop in
dark and light. Screenshots go to screenshots/forums/ for review by eye."""

import os

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model

from forums import strings
from forums.models import ForumPost

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

PASSWORD = "a-Long-pass-7731"


def make_author():
    user = get_user_model().objects.create_user("ada", "ada@example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email="ada@example.com", primary=True, verified=True)
    return user


def sign_in(page) -> None:
    page.fill("input[name=login]", "ada@example.com")
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit].btn-primary")
    page.wait_for_url("**/forums/*/")


def fits(page, width: int) -> None:
    """No sideways scroll, and nothing in a panel spills past it."""
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    assert page.evaluate(
        "[...document.querySelectorAll('.pj-panel')].every(panel => {"
        "  const edge = Math.min(panel.getBoundingClientRect().right, innerWidth) + 0.5;"
        "  return [...panel.querySelectorAll('.btn, .pj-tag, h1, h2, input, textarea')]"
        "    .every(box => box.getBoundingClientRect().right <= edge);"
        "})"
    )


def focused(page) -> str:
    """The focused element, as `tag#id` or `tag[name]`."""
    return page.evaluate(
        "(() => { const e = document.activeElement;"
        "  return e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +"
        "    (e.name ? '[' + e.name + ']' : ''); })()"
    )


def press(page, selector: str, key: str = "Enter") -> None:
    """Focus `selector`, press `key`, and wait until htmx has swapped in its answer and set it
    up (`htmx:load` fires after the swapped part is processed and focused). Waiting on focus
    alone isn't enough: a field keeps its focus across a swap (htmx restores it by id), and a
    key pressed on a part htmx hasn't set up yet acts as a plain link or form."""
    before = page.evaluate("window.__loads")
    page.focus(selector)
    page.keyboard.press(key)
    page.wait_for_function(f"window.__loads > {before}")


def still_same_page(page) -> bool:
    """The marker set on the page survives: nothing reloaded it."""
    return page.evaluate("window.__noReload === 1")


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_the_author_edits_and_deletes_in_place_by_keyboard(open_home, width, scheme):
    post = ForumPost.objects.create(
        author=make_author(),
        title="How do I spawn a decal when a part is touched?",
        body="I wired When touched → Spawn decal.\nNothing appears yet.",
    )
    shots = f"screenshots/forums/{{}}-{width}-{scheme}.png"
    page, errors = open_home(
        path=f"/accounts/login/?next={post.get_absolute_url()}", width=width, scheme=scheme
    )
    sign_in(page)
    url = page.url
    page.evaluate(
        "window.__noReload = 1; window.__loads = 0;"
        "document.addEventListener('htmx:load', () => window.__loads++)"
    )
    fits(page, width)
    page.screenshot(path=shots.format("post"), full_page=True)

    # Edit, by keyboard: the post swaps for its form, the title field focused.
    press(page, "[data-edit]")
    assert page.locator("#post[data-editing]").count() == 1
    assert focused(page) == "input#id_title[title]"
    assert still_same_page(page) and page.url == url
    fits(page, width)
    page.screenshot(path=shots.format("editing"), full_page=True)

    # An empty title: the form comes back with the error, the title field focused again.
    page.fill("input[name=title]", "")
    press(page, "input[name=title]")
    assert page.locator("#post .app-field-errors").count() == 1
    assert focused(page) == "input#id_title[title]"
    assert page.get_attribute("input[name=title]", "aria-invalid") == "true"
    assert strings.TITLE_REQUIRED in page.inner_text("#post")

    # Save: the post swaps back, its heading focused, and the change is announced.
    page.fill("input[name=title]", "Decals on touch: solved")
    press(page, "#post button[type=submit]")
    assert focused(page) == "h1#post-title"
    assert page.inner_text("#post-title") == "Decals on touch: solved"
    assert page.inner_text("#post-status") == strings.SAVED
    assert page.locator("#post [data-edited]").is_visible()
    assert still_same_page(page) and page.url == url
    post.refresh_from_db()
    assert post.title == "Decals on touch: solved"

    # Cancel leaves the post as it was.
    press(page, "[data-edit]")
    press(page, "[data-cancel]")
    assert focused(page) == "h1#post-title"
    assert page.inner_text("#post-title") == "Decals on touch: solved"

    # Delete asks first (its question focused); Keep it brings the post back.
    press(page, "[data-delete]")
    assert page.locator("#post[data-confirming]").count() == 1
    assert focused(page) == "h2#delete-title"
    fits(page, width)
    page.screenshot(path=shots.format("confirm-delete"), full_page=True)
    press(page, "[data-keep]")
    assert focused(page) == "h1#post-title"
    assert ForumPost.objects.filter(pk=post.pk).exists()

    # Confirming leaves the notice where the post was, focused.
    press(page, "[data-delete]")
    press(page, "[data-confirm-delete]")
    assert page.locator("#post[data-deleted]").count() == 1
    assert focused(page) == "h2#deleted-title"
    assert still_same_page(page) and page.url == url
    assert not ForumPost.objects.filter(pk=post.pk).exists()
    fits(page, width)
    page.screenshot(path=shots.format("deleted"), full_page=True)
    assert errors == []


def test_every_action_works_as_a_full_page_without_javascript(open_home):
    post = ForumPost.objects.create(author=make_author(), title="No script", body="Plain.")
    page, errors = open_home(
        path=f"/accounts/login/?next={post.get_absolute_url()}", java_script_enabled=False
    )
    sign_in(page)
    # Edit is a link to the edit page.
    page.click("[data-edit]")
    page.wait_for_url(f"**/forums/{post.pk}/edit/")
    page.fill("input[name=title]", "Still works")
    page.click("button[type=submit].btn-primary")
    page.wait_for_url(f"**/forums/{post.pk}/")
    assert page.inner_text("#post-title") == "Still works"
    assert strings.SAVED in page.inner_text(".app-messages")
    # Delete is a link to the confirmation page.
    page.click("[data-delete]")
    page.wait_for_url(f"**/forums/{post.pk}/delete/")
    page.click("button[type=submit].btn-primary")
    page.wait_for_url("**/forums/")
    assert strings.DELETED in page.inner_text(".app-messages")
    assert not ForumPost.objects.exists()
    assert errors == []


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_the_list_and_new_post_pages_fit_the_screen(open_home, width, scheme):
    author = make_author()
    for n in range(3):
        ForumPost.objects.create(
            author=author,
            title=f"Post {n}: a fairly long title to see how it wraps on a phone screen",
            body="Body text " * 40,
        )
    page, errors = open_home(path="/accounts/login/?next=/forums/new/", width=width, scheme=scheme)
    page.fill("input[name=login]", "ada@example.com")
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit].btn-primary")
    page.wait_for_url("**/forums/new/")
    fits(page, width)
    page.screenshot(path=f"screenshots/forums/new-{width}-{scheme}.png", full_page=True)
    page.goto(page.url.replace("/new/", "/"))
    assert page.locator("[data-posts] > li").count() == 3
    fits(page, width)
    page.screenshot(path=f"screenshots/forums/list-{width}-{scheme}.png", full_page=True)
    assert errors == []
