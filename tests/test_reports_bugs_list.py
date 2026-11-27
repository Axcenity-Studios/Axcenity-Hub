"""The reports list (Phase 14) on the shared list pattern: only the reports the member may
see, the status, kind, about and assigned filters, search, the three orders, pages, hostile
parameters falling back, the HTMX part and the query count."""

import re
from datetime import timedelta

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from projects.models import Project, ProjectMembership, Role
from reports.models import BugReport

from .test_reports_bugs import make_member, make_report, signed_in

URL = reverse("reports:bug_list")


def shown(client, query: str = "") -> list[int]:
    """The pks of the reports on the page, in order."""
    html = client.get(URL + ("?" + query if query else "")).content.decode()
    return [int(pk) for pk in re.findall(r'<li class="fm-row" data-bug="(\d+)"', html)]


@pytest.fixture
def world(db):
    """Olive owns Space Game (Max maintains it); Otto is in no project; Adam is an admin."""
    olive, max_, otto = make_member("olive"), make_member("max"), make_member("otto")
    project = Project.objects.create_with_owner(olive, name="Space Game")
    ProjectMembership.objects.create(project=project, user=max_, role=Role.MAINTAINER)
    other = Project.objects.create_with_owner(otto, name="Otto's Racer")
    return {
        "olive": olive,
        "max": max_,
        "otto": otto,
        "admin": make_member("adam", is_staff=True),
        "project": project,
        "other": other,
    }


def test_the_list_holds_only_what_the_member_may_see(world):
    mine = make_report(world["otto"], None, title="Otto's engine bug")
    theirs = make_report(world["max"], world["project"], title="Space bug")
    racer = make_report(world["olive"], None, title="Olive's engine idea", kind="feedback")
    assert shown(signed_in(world["otto"])) == [mine.pk]
    assert shown(signed_in(world["olive"])) == [racer.pk, theirs.pk]
    assert shown(signed_in(world["max"])) == [theirs.pk]
    assert shown(signed_in(world["admin"])) == [racer.pk, theirs.pk, mine.pk]


def test_about_offers_only_what_the_member_sees_and_narrows(world):
    space = make_report(world["max"], world["project"])
    engine = make_report(world["olive"], None)
    make_report(world["otto"], world["other"])  # Otto's own project; Olive never sees it
    client = signed_in(world["olive"])
    html = client.get(URL).content.decode()
    assert '<option value="engine">Axcenity Engine</option>' in html
    assert '<option value="space-game">Space Game</option>' in html
    assert "Racer" not in html
    assert shown(client, "about=space-game") == [space.pk]
    assert shown(client, "about=engine") == [engine.pk]
    # A project she can't see isn't a choice: the list isn't narrowed, and nothing is echoed.
    page = client.get(URL + "?about=otto-s-racer").content.decode()
    assert shown(client, "about=otto-s-racer") == [engine.pk, space.pk]
    assert "otto-s-racer" not in page[page.index('id="bug-list-controls"') :]


def test_status_kind_and_assigned_filters(world):
    olive = signed_in(world["olive"])
    new = make_report(world["max"], world["project"])
    fixing = make_report(
        world["max"], world["project"], status="in_progress", assignee=world["olive"]
    )
    done = make_report(world["max"], world["project"], status="closed", assignee=world["max"])
    idea = make_report(world["max"], world["project"], kind="feedback", status="wont_fix")
    assert shown(olive, "status=open") == [fixing.pk, new.pk]
    assert shown(olive, "status=closed") == [done.pk]
    assert shown(olive, "status=wont_fix") == [idea.pk]
    assert shown(olive, "kind=feedback") == [idea.pk]
    assert shown(olive, "kind=bug") == [done.pk, fixing.pk, new.pk]
    assert shown(olive, "assigned=me") == [fixing.pk]
    assert shown(olive, "assigned=nobody") == [idea.pk, new.pk]
    assert shown(signed_in(world["max"]), "assigned=me") == [done.pk]
    assert shown(olive, "status=open&assigned=nobody") == [new.pk]


def test_search_finds_every_word_in_the_title_or_description(world):
    olive = signed_in(world["olive"])
    decal = make_report(world["olive"], None, title="Decals at the origin", description="Touched")
    door = make_report(world["olive"], None, title="Door script", description="Decals too")
    make_report(world["olive"], None, title="Terrain seams", description="Chunks")
    assert shown(olive, "q=decal") == [door.pk, decal.pk]
    assert shown(olive, "q=decal+touched") == [decal.pk]
    assert shown(olive, "q=DOOR") == [door.pk]
    assert shown(olive, "q=nothing") == []


def test_each_order_and_ties_by_pk(world):
    olive = signed_in(world["olive"])
    now = timezone.now()
    first, second, third = (make_report(world["olive"], None) for _ in range(3))
    BugReport.objects.filter(pk__in=[first.pk, second.pk, third.pk]).update(created=now)
    BugReport.objects.filter(pk=first.pk).update(updated=now + timedelta(hours=1))
    BugReport.objects.filter(pk__in=[second.pk, third.pk]).update(updated=now)
    assert shown(olive) == [third.pk, second.pk, first.pk]
    assert shown(olive, "sort=oldest") == [first.pk, second.pk, third.pk]
    assert shown(olive, "sort=updated") == [first.pk, third.pk, second.pk]


def test_twenty_a_page_with_its_boundaries(world):
    olive = signed_in(world["olive"])
    reports = [make_report(world["olive"], None, title=f"Bug {n}") for n in range(21)]
    first_page = shown(olive)
    assert len(first_page) == 20 and first_page[0] == reports[-1].pk
    assert shown(olive, "page=2") == [reports[0].pk]
    assert shown(olive, "page=99") == [reports[0].pk]
    html = olive.get(URL).content.decode()
    assert 'href="/reports/bugs/?page=2"' in html and "Page 1 of 2" in html


@pytest.mark.parametrize(
    "query",
    ["page=-1", "page=abc", "page=٢", "sort=-created", "sort=submitter__password",
     "status=CLOSED", "status=1 OR 1=1", "kind=%00", "assigned=everyone", "about=../",
     "status=new&status=closed", "q=%00%00", "q=" + "x" * 500, "next=/evil/"],
)  # fmt: skip
def test_hostile_parameters_fall_back_and_are_never_echoed_into_links(world, query):
    olive = signed_in(world["olive"])
    for _ in range(2):
        make_report(world["olive"], None)
    response = Client(raise_request_exception=False)
    response.force_login(world["olive"])
    page = response.get(URL + "?" + query)
    assert page.status_code == 200
    html = page.content.decode()
    # The list's own part and its controls (the shell's theme switch returns to the address
    # as sent, as on every page).
    part = html[html.index('id="bug-list-controls"') :]
    assert "/evil/" not in part and "submitter__password" not in part and "OR 1=1" not in part
    assert len(shown(olive, query)) in (0, 2)


def test_htmx_gets_the_lists_part_with_its_address(world):
    make_report(world["olive"], None, kind="feedback")
    client = signed_in(world["olive"])
    response = client.get(URL + "?kind=feedback&sort=oldest", headers={"HX-Request": "true"})
    html = response.content.decode()
    assert 'id="bug-list"' in html
    assert "<html" not in html and 'hx-swap-oob="innerHTML:#bug-list-live"' in html
    assert response["HX-Push-Url"] == "/reports/bugs/?sort=oldest&kind=feedback"
    assert "HX-Request" in response["Vary"]


def test_every_id_on_the_page_is_unique(world):
    # The status filter's select is #bug-list-status, so the live region is #bug-list-live.
    make_report(world["olive"], None)
    html = signed_in(world["olive"]).get(URL).content.decode()
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids)) and "bug-list-live" in ids


def test_the_empty_and_no_match_states(world):
    client = signed_in(world["otto"])
    html = client.get(URL).content.decode()
    assert "data-empty" in html and "No reports yet" in html and "data-list-controls" not in html
    make_report(world["otto"], None)
    html = client.get(URL + "?q=zzz").content.decode()
    assert "data-no-match" in html and "No reports match" in html


def test_the_page_is_a_fixed_number_of_queries(world):
    client = signed_in(world["admin"])

    def count() -> int:
        with CaptureQueriesContext(connection) as queries:
            assert client.get(URL).status_code == 200
        return len(queries)

    for n in range(3):
        make_report(world["olive"], world["project"], assignee=world["max"], title=f"A{n}")
    few = count()
    for n in range(12):
        make_report(world["otto"], world["other"], assignee=world["otto"], title=f"B{n}")
    assert count() == few
