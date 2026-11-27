"""The showcase list: browsing by tag (the open filter: only published showcases' tags offered,
an unknown or hidden tag never narrowing or echoed), search, the published filter, each sort,
24 a page and its boundaries, query counts, the HTMX part, the empty states, `OpenFilter`
itself, and the `seed_showcase_demo` command."""

import re
from datetime import timedelta

import pytest
from django.core.management import CommandError, call_command
from django.db import connection
from django.http import QueryDict
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from config.listing import Listing, OpenFilter, Sort
from reports.moderation import Visibility
from showcases import services, strings
from showcases.listing import SHOWCASES
from showcases.models import Like, Showcase, Tag
from tests.test_showcases import make_member, make_showcase, processed

LIST = "showcases:list"
HTMX = {"HX-Request": "true"}


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def slugs(client, query="", **headers) -> list[str]:
    html = client.get(f"{reverse(LIST)}?{query}", headers=headers).content.decode()
    return re.findall(r'data-showcase="([^"]+)"', html)


def tag_options(html: str) -> list[str]:
    select = re.search(r'<select id="showcase-list-tag".*?</select>', html, re.S)[0]
    return re.findall(r'<option value="([^"]*)"', select)


@pytest.fixture
def tagged():
    ada, grace = make_member("ada"), make_member("grace")
    hall = make_showcase(ada, "Hall", tags=["ray-tracing", "lighting"], ago=timedelta(days=3))
    meadow = make_showcase(grace, "Meadow", tags=["terrain", "foliage"], ago=timedelta(days=2))
    canyon = make_showcase(ada, "Canyon", tags=["terrain"], ago=timedelta(hours=30))
    return {"hall": hall, "meadow": meadow, "canyon": canyon}


# ---------- Browsing by tag ----------


@pytest.mark.django_db
def test_a_tag_narrows_the_list_to_the_showcases_carrying_it(client, tagged):
    assert slugs(client, "tag=terrain") == ["canyon", "meadow"]
    assert slugs(client, "tag=lighting") == ["hall"]
    html = client.get(f"{reverse(LIST)}?tag=terrain").content.decode()
    assert strings.TAGGED.format(tag="terrain") in html
    assert '<option value="terrain" selected>' in html


@pytest.mark.django_db
def test_every_tag_on_a_card_and_a_page_links_to_its_list(client, tagged):
    html = client.get(reverse(LIST)).content.decode()
    for name in ["ray-tracing", "lighting", "terrain", "foliage"]:
        assert f'href="{reverse(LIST)}?tag={name}"' in html
    page = client.get(tagged["meadow"].get_absolute_url()).content.decode()
    assert f'href="{reverse(LIST)}?tag=foliage"' in page


@pytest.mark.django_db
def test_the_tag_select_offers_published_showcases_tags_by_name(client, tagged):
    Tag.objects.create(name="unused")
    html = client.get(reverse(LIST)).content.decode()
    assert tag_options(html) == ["", "foliage", "lighting", "ray-tracing", "terrain"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    [
        "unknown",
        "Terrain",
        "TERRAIN",
        " terrain",
        "terrain ",
        "terr",
        "<b>x</b>",
        "1 OR 1=1",
        "unused",
    ],
)
def test_an_unknown_tag_doesnt_narrow_the_list_and_isnt_echoed(client, tagged, value):
    Tag.objects.create(name="unused")
    query = QueryDict(mutable=True)
    query["tag"] = value
    html = client.get(f"{reverse(LIST)}?{query.urlencode()}").content.decode()
    assert re.findall(r'data-showcase="([^"]+)"', html) == ["canyon", "meadow", "hall"]
    assert "selected" in re.search(r'<option value=""[^>]*>', html)[0]
    assert "<b>x</b>" not in html and "Tagged" not in html


@pytest.mark.django_db
def test_a_tag_given_twice_is_ignored(client, tagged):
    assert slugs(client, "tag=terrain&tag=lighting") == ["canyon", "meadow", "hall"]
    assert slugs(client, "tag=terrain&tag=terrain") == ["canyon", "meadow", "hall"]


@pytest.mark.django_db
def test_a_tag_only_hidden_showcases_carry_is_neither_offered_nor_used(client, tagged):
    secret = make_showcase(make_member("lin"), "Secret", tags=["secret-tag"])
    Showcase.objects.filter(pk=secret.pk).update(state=Visibility.HIDDEN)
    html = client.get(reverse(LIST)).content.decode()
    assert "secret-tag" not in html
    assert slugs(client, "tag=secret-tag") == ["canyon", "meadow", "hall"]
    # A tag on both a hidden and a published showcase finds only the published one.
    Showcase.objects.filter(pk=tagged["hall"].pk).update(state=Visibility.REMOVED)
    assert "lighting" not in tag_options(client.get(reverse(LIST)).content.decode())
    assert slugs(client, "tag=terrain") == ["canyon", "meadow"]


@pytest.mark.django_db
def test_a_showcase_with_several_tags_is_listed_once(client):
    make_showcase(make_member(), "Many", tags=["one", "two", "three"])
    assert slugs(client) == ["many"]
    assert slugs(client, "sort=liked") == ["many"]


# ---------- Search, the published filter, sorts ----------


@pytest.mark.django_db
def test_search_looks_in_titles_and_descriptions_for_every_word(client):
    ada, grace = make_member("ada"), make_member("grace")
    make_showcase(ada, "Mirror hall", description="Reflections everywhere.")
    make_showcase(grace, "Canyon", description="Sculpted hills and a MIRROR lake.")
    assert slugs(client, "q=mirror") == ["canyon", "mirror-hall"]
    assert slugs(client, "q=mirror+hills") == ["canyon"]
    assert slugs(client, "q=nothing") == []
    html = client.get(f"{reverse(LIST)}?q=nothing").content.decode()
    assert "data-no-match" in html and strings.NO_MATCH_TITLE in html


@pytest.mark.django_db
def test_the_published_filter_counts_back_from_now(client):
    ada, grace, lin = make_member("ada"), make_member("grace"), make_member("lin")
    make_showcase(ada, "Today", ago=timedelta(hours=2))
    make_showcase(grace, "This week", ago=timedelta(days=3))
    make_showcase(lin, "Long ago", ago=timedelta(days=60))
    assert slugs(client, "posted=day") == ["today"]
    assert slugs(client, "posted=week") == ["today", "this-week"]
    assert slugs(client, "posted=month") == ["today", "this-week"]
    assert slugs(client, "posted=year") == ["today", "this-week", "long-ago"]


@pytest.mark.django_db
def test_each_sort(client):
    ada, grace, lin, max_ = (make_member(n) for n in ["ada", "grace", "lin", "max"])
    old = make_showcase(ada, "Old", ago=timedelta(days=9))
    mid = make_showcase(grace, "Mid", ago=timedelta(days=5))
    make_showcase(lin, "Fresh", ago=timedelta(days=1, hours=1))
    for fan in [grace, lin, max_]:
        services.like(fan, old)
    services.like(max_, mid)
    assert slugs(client) == ["fresh", "mid", "old"]
    assert slugs(client, "sort=oldest") == ["old", "mid", "fresh"]
    assert slugs(client, "sort=liked") == ["old", "mid", "fresh"]
    assert slugs(client, "sort=-created") == ["fresh", "mid", "old"]  # unknown: the default


# ---------- Pages ----------


def fill(count: int, *, at=None) -> None:
    """`count` showcases by new members, all at the same moment (ties ordered by pk)."""
    at = at or timezone.now() - timedelta(days=2)
    start = Showcase.objects.count()
    for i in range(count):
        author = make_member(f"m{start + i}")
        showcase = services.create_showcase(
            author, title=f"Showcase {start + i}", description="D", image=processed()
        )
        Showcase.objects.filter(pk=showcase.pk).update(created=at)


@pytest.mark.django_db
def test_24_a_page_with_ties_in_one_order_across_pages(client):
    fill(49)
    first, second, third = (slugs(client, f"page={n}") for n in (1, 2, 3))
    assert (len(first), len(second), len(third)) == (24, 24, 1)
    assert len(set(first + second + third)) == 49
    assert slugs(client, "page=99") == third  # past the end: the last page
    assert slugs(client, "page=0") == first and slugs(client, "page=-1") == first
    html = client.get(f"{reverse(LIST)}?page=2").content.decode()
    assert f'href="{reverse(LIST)}?page=3"' in html and f'href="{reverse(LIST)}"' in html
    assert "Page 2 of 3" in html


@pytest.mark.django_db
def test_the_pager_keeps_the_tag(client):
    at = timezone.now() - timedelta(days=2)
    for i in range(26):
        author = make_member(f"t{i}")
        showcase = services.create_showcase(
            author, title=f"Tagged {i}", description="D", image=processed(), tags=["terrain"]
        )
        Showcase.objects.filter(pk=showcase.pk).update(created=at)
    html = client.get(f"{reverse(LIST)}?tag=terrain").content.decode()
    assert f'href="{reverse(LIST)}?tag=terrain&amp;page=2"' in html
    assert len(slugs(client, "tag=terrain&page=2")) == 2


@pytest.mark.django_db
def test_the_list_costs_the_same_queries_however_many_showcases(client):
    def queries() -> int:
        with CaptureQueriesContext(connection) as captured:
            assert client.get(f"{reverse(LIST)}?tag=terrain").status_code == 200
        return len(captured)

    make_showcase(make_member("ada"), "First", tags=["terrain", "foliage"])
    few = queries()
    for i in range(10):
        make_showcase(make_member(f"x{i}"), f"More {i}", tags=["terrain", f"tag-{i}"])
    assert queries() == few
    # The tags offered, the count, the page's rows, and their tags.
    assert few == 4


# ---------- The HTMX part ----------


@pytest.mark.django_db
def test_htmx_gets_the_lists_part_and_the_address_to_show(client, tagged):
    response = client.get(f"{reverse(LIST)}?tag=terrain&sort=newest&junk=1", headers=HTMX)
    html = response.content.decode()
    assert response.status_code == 200 and "<html" not in html
    assert html.count('id="showcase-list"') == 1
    assert response["HX-Push-Url"] == f"{reverse(LIST)}?tag=terrain"
    assert 'hx-swap-oob="innerHTML:#showcase-list-status"' in html and "2 showcases" in html
    assert {"HX-Request", "HX-History-Restore-Request"} <= {
        v.strip() for v in response["Vary"].split(",")
    }
    restore = client.get(reverse(LIST), headers={**HTMX, "HX-History-Restore-Request": "true"})
    assert "<html" in restore.content.decode()


@pytest.mark.django_db
def test_the_controls_are_a_plain_form_first(client, tagged):
    html = client.get(reverse(LIST)).content.decode()
    form = re.search(r'<form id="showcase-list-controls".*?</form>', html, re.S)[0]
    assert 'method="get"' in form and f'action="{reverse(LIST)}"' in form
    for name in ["q", "tag", "posted", "sort"]:
        assert f'name="{name}"' in form
    assert 'hx-target="#showcase-list"' in form


@pytest.mark.django_db
def test_without_showcases_the_list_says_so_and_has_no_controls(client):
    html = client.get(reverse(LIST)).content.decode()
    assert "data-empty" in html and strings.EMPTY_TITLE in html
    assert "showcase-list-controls" not in html


# ---------- OpenFilter ----------


def test_an_open_filter_reads_its_choices_once_per_request():
    calls = []

    def options():
        calls.append(1)
        return [("a", "A"), ("b", "B"), ("", "never")]

    listing = Listing(
        search_fields=(),
        sorts=(Sort("x", "X", ("pk",)),),
        filters=(OpenFilter("letter", "Letter", "Any", options, lambda qs, v: (qs, v)),),
    )
    selection = listing.read(QueryDict("letter=b"))
    assert selection.chosen == {"letter": "b"} and len(calls) == 1
    assert selection.controls()["selects"][0]["options"] == [
        {"value": "", "label": "Any", "selected": False},
        {"value": "a", "label": "A", "selected": False},
        {"value": "b", "label": "B", "selected": True},
    ]
    assert selection.query() == "?letter=b" and len(calls) == 1
    assert listing.read(QueryDict("letter=c")).chosen == {"letter": ""}
    assert listing.read(QueryDict("letter=")).chosen == {"letter": ""}


def test_an_open_filter_may_not_take_a_shared_parameters_name():
    with pytest.raises(ValueError):
        Listing(
            search_fields=(),
            sorts=(Sort("x", "X", ("pk",)),),
            filters=(OpenFilter("page", "P", "Any", list, lambda qs, v: qs),),
        )


def test_the_showcase_list_declares_its_filters():
    assert [f.name for f in SHOWCASES.filters] == ["tag", "posted"]
    assert [s.value for s in SHOWCASES.sorts] == ["newest", "oldest", "liked"]
    assert SHOWCASES.per_page == 24


# ---------- seed_showcase_demo ----------


@pytest.mark.django_db
def test_the_demo_seed_fills_two_pages_once(settings, client, media):
    settings.DEBUG = True
    call_command("seed_showcase_demo", stdout=open("/dev/null", "w"))  # noqa: SIM115
    count = Showcase.objects.count()
    assert count == 30 and Like.objects.exists()
    assert len(slugs(client)) == 24 and len(slugs(client, "page=2")) == 6
    files = sorted(p.name for p in (media / "showcases").rglob("*.webp"))
    assert len(files) == 60
    call_command("seed_showcase_demo", stdout=open("/dev/null", "w"))  # noqa: SIM115
    assert Showcase.objects.count() == count
    assert sorted(p.name for p in (media / "showcases").rglob("*.webp")) == files
    # Every demo image says it's an illustrative placeholder, never an engine capture.
    for showcase in Showcase.objects.all():
        assert "illustrative placeholder" in showcase.description
        assert showcase.image_alt.startswith("Illustrative placeholder")
    # Only alice is at the one-a-day limit; nobody was made staff.
    from django.contrib.auth import get_user_model

    people = get_user_model().objects.filter(username__in=["alice", "bob"])
    limits = {p.username: bool(services.limit_message(p)) for p in people}
    assert limits == {"alice": True, "bob": False}
    assert not get_user_model().objects.filter(is_staff=True).exists()


def test_the_demo_seed_refuses_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_showcase_demo")
