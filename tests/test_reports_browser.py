"""Bug reports in headless Chromium: the list, the form and a report's page at 360 and 1280
px, dark and light, with no sideways scroll; the status filter swaps the list in place with
the address following; an Owner confirms and assigns a report and a comment joins the
timeline. Screenshots go to screenshots/reports/."""

import os

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model

from projects.models import Project, ProjectMembership, Role
from reports.models import BugReport

from .test_reports_bugs import make_report

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

PASSWORD = "a-Long-pass-7731"
ROWS = "document.querySelectorAll('#bug-list .fm-row').length"


def make_member(username: str):
    email = f"{username}@example.com"
    user = get_user_model().objects.create_user(username, email, PASSWORD)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=True)
    return user


def fill() -> BugReport:
    """Olive owns Space Game, Max maintains it, Vera views it and sent three reports."""
    olive, max_, vera = make_member("olive"), make_member("max"), make_member("vera")
    project = Project.objects.create_with_owner(olive, name="Space Game")
    ProjectMembership.objects.create(project=project, user=max_, role=Role.MAINTAINER)
    ProjectMembership.objects.create(project=project, user=vera, role=Role.VIEWER)
    make_report(vera, project, title="Reflections flicker on the lake", status="closed")
    make_report(vera, project, title="Terrain brush leaves seams", status="in_progress")
    return make_report(
        vera,
        project,
        title="Decals spawn at the origin after Touched, every time the part is hit",
        description="part.Touched:Connect(function(otherPart) … workspace:SpawnDecal(…)) "
        "puts the decal at 0, 0, 0.",
    )


def sign_in(page, username: str) -> None:
    page.fill("input[name=login]", f"{username}@example.com")
    page.fill("input[name=password]", PASSWORD)
    page.click("button[type=submit].btn-primary")


def fits(page, width: int) -> None:
    """No sideways scroll and nothing past a panel's edge."""
    assert page.evaluate("document.documentElement.scrollWidth") <= width
    assert page.evaluate(
        "[...document.querySelectorAll('.pj-panel, .app-panel, select, textarea')].every(box =>"
        " box.getBoundingClientRect().right <= innerWidth + 0.5)"
    )


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_an_owner_filters_confirms_assigns_and_comments(open_home, width, scheme):
    report = fill()
    shots = f"screenshots/reports/{{}}-{width}-{scheme}.png"
    page, errors = open_home(
        path="/accounts/login/?next=/reports/bugs/", width=width, scheme=scheme
    )
    sign_in(page, "olive")
    page.wait_for_url("**/reports/bugs/")
    page.wait_for_function(f"{ROWS} === 3")
    fits(page, width)
    page.screenshot(path=shots.format("list"), full_page=True)

    page.evaluate("window.__noReload = 1")
    page.select_option("#bug-list-status", "open")
    page.wait_for_url("**/reports/bugs/?status=open")
    page.wait_for_function(f"{ROWS} === 2")
    assert page.evaluate("window.__noReload") == 1

    page.goto(page.url.split("/reports/")[0] + report.get_absolute_url())
    fits(page, width)
    page.screenshot(path=shots.format("detail"), full_page=True)
    page.select_option("#bug-status", "confirmed")
    page.click("[data-status-form] button")
    page.wait_for_selector("text=Status changed to Confirmed.")
    page.select_option("#bug-assignee", label="max (max)")
    page.click("[data-assign-form] button")
    page.wait_for_selector("text=Assigned to max.")
    page.fill("textarea[name=body]", "Confirmed on Linux too.")
    page.click("[data-comment-form] button")
    page.wait_for_selector("[data-entry=comment] >> text=Confirmed on Linux too.")
    assert page.locator("[data-activity] .fm-comment").count() == 3
    report.refresh_from_db()
    assert (report.status, report.assignee.username) == ("confirmed", "max")
    fits(page, width)
    page.screenshot(path=shots.format("handled"), full_page=True)
    assert errors == []


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize("width", [360, 1280])
def test_the_form_fits_and_shows_its_errors(open_home, width, scheme):
    fill()
    page, errors = open_home(
        path="/accounts/login/?next=/reports/bugs/new/", width=width, scheme=scheme
    )
    sign_in(page, "vera")
    page.wait_for_url("**/reports/bugs/new/")
    fits(page, width)
    page.click("[data-bug-form] button[type=submit]")
    page.wait_for_selector("text=Give the report a title.")
    fits(page, width)
    page.screenshot(path=f"screenshots/reports/form-{width}-{scheme}.png", full_page=True)
    assert errors == []
