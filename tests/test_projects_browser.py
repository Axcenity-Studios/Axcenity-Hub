"""The project pages in headless Chromium: the empty list, the setup checklist at each stage,
the webhook values and their copy buttons, each step's help and the cards fit every screen
from a phone to a desktop, in dark and light, with no sideways scroll.

Screenshots go to screenshots/projects/ for review by eye. GitHub is mocked with `responses`
(it patches `requests` for the live server's thread too); nothing reaches the network.
"""

import os
from datetime import UTC, datetime

import pytest
import responses
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model

from accounts.models import GitHubLink
from projects.models import Project, RepositoryLink

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

PASSWORD = "a-Long-pass-7731"
KEY = "eE5nY3VhTnJ0d1lCV0lQZ3VHWHZmS2F6c0p6Q0JxS0Q="
REPO = {
    "id": 1296269,
    "full_name": "octocat/Hello-World",
    "html_url": "https://github.com/octocat/Hello-World",
    "description": "This your first repo!",
    "default_branch": "main",
    "private": False,
    "archived": False,
    "pushed_at": "2026-11-20T09:30:00Z",
    "permissions": {"admin": True, "push": True, "pull": True},
}


def fits(page, width: int) -> None:
    """No sideways scroll, and nothing inside a panel spills past it (the panel would clip it)."""
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    assert page.evaluate(
        "[...document.querySelectorAll('.pj-panel')].every(panel => {"
        "  const edge = Math.min(panel.getBoundingClientRect().right, innerWidth) + 0.5;"
        "  return [...panel.querySelectorAll('.btn, .pj-copy, .pj-value, .pj-fields, .pj-facts, .pj-tag')]"
        "    .every(box => box.getBoundingClientRect().right <= edge);"
        "})"
    )


def centred(page) -> None:
    """The page's column sits centred in the main area (beside the rail on a desktop)."""
    assert page.evaluate(
        "(() => { const main = document.querySelector('.app-main').getBoundingClientRect();"
        "  const col = document.querySelector('.app-column').getBoundingClientRect();"
        "  return Math.abs((col.left - main.left) - (main.right - col.right)) <= 1; })()"
    )


def shot(page, path: str) -> None:
    """A full-page screenshot once the motifs in view have drawn in."""
    page.wait_for_timeout(1600)
    page.screenshot(path=path, full_page=True)


def sign_in(page) -> None:
    page.fill("input[name=login]", "ada@example.com")
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit].btn-primary")
    page.wait_for_url("**/projects/")


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
@responses.activate
def test_the_project_pages_guide_setup_and_fit_the_screen(open_home, settings, width, scheme):
    settings.GITHUB_TOKEN_KEYS = [KEY]
    settings.GITHUB_WEBHOOK_SECRET = "root-secret-for-tests-only"
    responses.get("https://api.github.com/repos/octocat/Hello-World", json=REPO)
    user = get_user_model().objects.create_user("ada_lovelace", "ada@example.com", PASSWORD)
    EmailAddress.objects.create(user=user, email="ada@example.com", primary=True, verified=True)
    account = SocialAccount.objects.create(
        user=user, provider="github", uid="583231", extra_data={"login": "octocat"}
    )
    GitHubLink.objects.store(account, access_token="gho_test_only_not_real")
    shots = f"screenshots/projects/{{}}-{width}-{scheme}.png"

    # The empty list: a call to start, with the four steps previewed.
    page, errors = open_home(path="/accounts/login/?next=/projects/", width=width, scheme=scheme)
    sign_in(page)
    assert page.locator(".pj-preview > li").count() == 4
    fits(page, width)
    shot(page, shots.format("empty"))

    # A new project: step 2 is the current one, with the link form.
    project = Project.objects.create(owner=user, name="Space Game", description="A game in space.")
    page.goto(page.url.split("/projects/")[0] + project.get_absolute_url())
    assert page.locator("#setup-repository[data-state=current] input[name=repository]").is_visible()
    # A first repository: the current step's help is open, the others folded.
    assert page.locator("#setup-repository .pj-help[open]").is_visible()
    assert page.locator("#setup-webhook .pj-help[open]").count() == 0
    # The page sits in the middle of the space beside the rail.
    centred(page)
    fits(page, width)
    shot(page, shots.format("step-repository"))

    # Linked: the webhook's values, field by field, with working copy buttons.
    RepositoryLink.objects.create(
        project=project,
        github_id=REPO["id"],
        full_name=REPO["full_name"],
        html_url=REPO["html_url"],
        description=REPO["description"],
        default_branch="main",
        fetched_at=datetime.now(UTC),
    )
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.goto(page.url.split("?")[0] + "?webhook=show#setup-webhook")
    copy = page.locator(".pj-copy").first
    assert copy.is_visible()
    copy.click()
    page.wait_for_function(
        "el => el.textContent.trim() === 'Copied'",
        arg=copy.locator("[data-copy-text]").element_handle(),
    )
    url = page.locator("#webhook-value-0").inner_text().strip()
    assert page.evaluate("navigator.clipboard.readText()") == url
    # The last step's help holds the responses table, which scrolls in its own box.
    # (Showing the settings made step 4 current, so on a first repository it's already open.)
    assert page.evaluate("document.querySelector('#setup-delivery .pj-help').open") is True
    assert page.locator("#setup-delivery .pj-table").is_visible()
    fits(page, width)
    shot(page, shots.format("step-webhook"))

    # Connected: the checklist folds to its bar; the repository shows live updates.
    RepositoryLink.objects.update(first_webhook_at=datetime.now(UTC), webhook_at=datetime.now(UTC))
    page.goto(page.url.split("?")[0])
    assert page.evaluate("document.getElementById('setup').open") is False
    fits(page, width)
    shot(page, shots.format("connected"))

    # The cards.
    Project.objects.create(owner=user, name="Moon Base")
    page.goto(page.url.split("/projects/")[0] + "/projects/")
    assert page.locator(".pj-card").count() == 2
    fits(page, width)
    shot(page, shots.format("list"))
    assert errors == []
