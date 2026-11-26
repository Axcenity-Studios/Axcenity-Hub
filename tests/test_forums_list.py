"""The forum list (Phase 12C): search, filters, sorting and pages, with their state in the
query string (config.listing, forums.listing)."""

import re
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qsl, quote, urlsplit

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.http import QueryDict
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from config.listing import (
    PAST_THE_END,
    Choice,
    Filter,
    Listing,
    Sort,
    clean_page,
    clean_search,
)
from forums import services, strings
from forums.listing import POSTS
from forums.models import Comment, ForumPost, Rating

User = get_user_model()
PASSWORD = "correct-horse-battery-staple-42"

# The parameters the list takes, and every value each may carry in a link the page writes.
SORTS = {"newest", "oldest", "top", "comments"}
FILTERS = {
    "posted": {"day", "week", "month"},
    "comments": {"none", "some"},
    "rating": {"4", "3", "2"},
}


def make_member(username="ada", *, verified: bool = True, **extra):
    email = f"{username}@example.com"
    user = User.objects.create_user(username, email, PASSWORD, **extra)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    return user


@pytest.fixture
def forum(db) -> dict[int, str]:
    """25 posts a minute apart, "Post 01" the oldest and "Post 25" the newest: two pages.
    Only Post 07's words hold "decal"; only Post 03 is rated (5 stars); only Post 05 has a
    comment. Returns each post's title by its pk."""
    ada, bob = make_member("ada"), make_member("bob")
    start = timezone.now() - timedelta(hours=2)
    titles = {}
    for number in range(1, 26):
        title = f"Post {number:02d}" + (" decal" if number == 7 else "")
        post = ForumPost.objects.create(author=ada, title=title, body="Text.")
        ForumPost.objects.filter(pk=post.pk).update(created=start + timedelta(minutes=number))
        titles[post.pk] = title
    by_title = {title: pk for pk, title in titles.items()}
    Rating.objects.create(post_id=by_title["Post 03"], user=bob, score=5)
    Comment.objects.create(post_id=by_title["Post 05"], author=bob, body="A comment.")
    return titles


class _Page(HTMLParser):
    """The list page as a visitor has it: the controls' values and every link."""

    def __init__(self):
        super().__init__()
        self.values: dict[str, str] = {}
        self.links: list[str] = []
        self._select = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.links += [attrs[name] for name in ("href", "hx-get", "action") if attrs.get(name)]
        if tag == "input" and attrs.get("name") == "q":
            self.values["q"] = attrs.get("value") or ""
        elif tag == "select":
            self._select = attrs.get("name", "")
        elif tag == "option" and self._select and "selected" in attrs:
            self.values[self._select] = attrs.get("value") or ""

    def handle_endtag(self, tag):
        if tag == "select":
            self._select = ""


def state(html: str, titles: dict[int, str]) -> dict:
    """What the page shows: the search box's text, the chosen sort and filters, the posts in
    order, and the page's place ((number, pages), or None when everything fits on one)."""
    page = _Page()
    page.feed(html)
    place = re.search(r'data-page="(\d+)" data-pages="(\d+)"', html)
    return {
        **page.values,
        "shown": [
            titles.get(int(pk), pk)
            for pk in re.findall(r'<li class="fm-row" data-post="(\d+)"', html)
        ],
        "page": (int(place[1]), int(place[2])) if place else None,
    }


def stray_links(html: str, q: str) -> list[str]:
    """The page's links to the list that carry anything but the list's own parameters, each
    once, with a value the list offers (`q`: the search the page shows)."""
    page = _Page()
    page.feed(html)
    stray = []
    for link in page.links:
        url = urlsplit(link)
        if url.path != reverse("forums:list") or url.netloc:
            continue
        pairs = parse_qsl(url.query, keep_blank_values=True)
        allowed = {"q": {q}, "sort": SORTS, **FILTERS}
        fine = len({name for name, _ in pairs}) == len(pairs) and all(
            re.fullmatch(r"[1-9][0-9]{0,5}", value, re.ASCII)
            if name == "page"
            else value in allowed.get(name, ())
            for name, value in pairs
        )
        if not fine:
            stray.append(link)
    return stray


NEWEST = [f"Post {n:02d}" + (" decal" if n == 7 else "") for n in range(25, 5, -1)]
OLDEST = [f"Post {n:02d}" + (" decal" if n == 7 else "") for n in range(1, 21)]
LAST = [f"Post {n:02d}" for n in range(5, 0, -1)]
# What the list shows when it's asked for nothing: the newest 20 of 25.
DEFAULT = {
    "q": "",
    "sort": "newest",
    "posted": "",
    "comments": "",
    "rating": "",
    "shown": NEWEST,
    "page": (1, 2),
}
MARKUP = quote("<img src=x onerror=alert(1)>")
ARABIC_TWO, ARABIC_FOUR = quote("٢"), quote("٤")

# Each query string, and how what it shows differs from DEFAULT ({}: not at all).
SAFELY = [
    # The parameters work, so falling back is something this test can see.
    ("sort=oldest", {"sort": "oldest", "shown": OLDEST}),
    ("page=2", {"shown": LAST, "page": (2, 2)}),
    ("rating=4", {"rating": "4", "shown": ["Post 03"], "page": None}),
    ("q=decal", {"q": "decal", "shown": ["Post 07 decal"], "page": None}),
    # A bad page is the first page.
    ("page=abc", {}),
    ("page=-1", {}),
    ("page=0", {}),
    ("page=1.5", {}),
    ("page=2abc", {}),
    ("page=1e1", {}),
    ("page=0x2", {}),
    ("page=%202", {}),
    ("page=2%00", {}),
    (f"page={ARABIC_TWO}", {}),  # int("٢") is 2: digits, but not a page number
    ("page=", {}),
    # A page past the end is the last page, however long the number.
    ("page=999", {"shown": LAST, "page": (2, 2)}),
    ("page=" + "9" * 40, {"shown": LAST, "page": (2, 2)}),
    ("page=" + "9" * 5000, {"shown": LAST, "page": (2, 2)}),  # past int()'s digit limit
    # An unknown sort is the default one: never a field name, a lookup or an ordering.
    ("sort=author__password", {}),
    ("sort=-created", {}),
    ("sort=pk", {}),
    ("sort=%3F", {}),  # "?": order_by's random order
    ("sort=NEWEST", {}),
    ("sort=Oldest", {}),
    ("sort=%20oldest", {}),
    ("sort=oldest%00", {}),
    (f"sort={MARKUP}", {}),
    ("sort=", {}),
    # A filter value that isn't one of its choices doesn't narrow the list.
    ("rating=abc", {}),
    ("rating=4.5", {}),
    ("rating=-1", {}),
    ("rating=0", {}),
    ("rating=99", {}),
    (f"rating={ARABIC_FOUR}", {}),
    ("rating=4%3BDROP%20TABLE%20forums_forumpost", {}),
    ("rating=4%20OR%201%3D1", {}),
    (f"rating={MARKUP}", {}),
    ("posted=created__gte", {}),
    ("posted=yesterday", {}),
    ("comments=1", {}),
    ("comments=NONE", {}),
    # One bad parameter doesn't take the others with it.
    ("sort=oldest&rating=abc&page=zzz", {"sort": "oldest", "shown": OLDEST}),
    # A parameter given twice is ignored, not guessed at (even twice the same).
    ("sort=oldest&sort=top", {}),
    ("page=2&page=2", {}),
    ("q=decal&q=decal", {}),
    ("rating=4&rating=3", {}),
    ("sort=oldest&sort=oldest&page=2", {"shown": LAST, "page": (2, 2)}),
    # Parameters the list doesn't have are ignored, and never copied into its links.
    ("sort[]=oldest", {}),
    ("sort%5B%24ne%5D=x", {}),
    ("next=//evil.example/&page=1", {}),
    ("__proto__=x&constructor=y", {}),
    # A search is text, whatever it holds: trimmed to 100 characters and 8 words, control
    # characters read as spaces, wildcards as themselves, markup escaped.
    ("q=" + "a" * 5000, {"q": "a" * 100, "shown": [], "page": None}),
    ("q=" + "Post+" * 8 + "zzz", {"q": " ".join(["Post"] * 8)}),
    ("q=dec%00al", {"q": "dec al", "shown": ["Post 07 decal"], "page": None}),
    ("q=%FF%FE", {"q": "��", "shown": [], "page": None}),  # not UTF-8
    ("q=%25", {"q": "%", "shown": [], "page": None}),
    ("q=_", {"q": "_", "shown": [], "page": None}),
    (f"q={MARKUP}", {"q": "<img src=x onerror=alert(1)>", "shown": [], "page": None}),
]


def test_invalid_or_hostile_query_parameters_fall_back_safely(forum):
    """Whatever the query string holds, the list answers 200 with the state each parameter
    falls back to, echoes no markup, and writes none of it into its own links."""
    client = Client(raise_request_exception=False)  # a crash is a 500 to assert on
    problems = []
    for query, changes in SAFELY:
        label = query if len(query) < 60 else f"{query[:40]}… ({len(query)} characters)"
        response = client.get(f"{reverse('forums:list')}?{query}")
        if response.status_code != 200:
            problems.append(f"{label}: answered {response.status_code}")
            continue
        html = response.content.decode()
        expected = {**DEFAULT, **changes}
        shown = state(html, forum)
        differs = {name: shown.get(name) for name in expected if shown.get(name) != expected[name]}
        if differs:
            summary = {
                name: f"{len(value)} posts from {value[:1]}" if name == "shown" else value
                for name, value in differs.items()
            }
            problems.append(f"{label}: showed {summary}")
        if "<img src=x" in html:
            problems.append(f"{label}: echoed markup unescaped")
        if stray := stray_links(html, expected["q"]):
            problems.append(f"{label}: wrote it into a link, {stray[0][:80]}")
    assert not problems, f"{len(problems)} of {len(SAFELY)} fell back badly:\n" + "\n".join(
        problems
    )


# ---------- Helpers for the rest ----------

HTMX = {"HX-Request": "true"}
LIST = "forums:list"


def make_post(author, title="A post", body="Text.", *, age: timedelta = timedelta(0)) -> ForumPost:
    """A post published `age` ago."""
    post = ForumPost.objects.create(author=author, title=title, body=body)
    if age:
        ForumPost.objects.filter(pk=post.pk).update(created=timezone.now() - age)
        post.refresh_from_db()
    return post


def titles(client, query: str = "", **headers) -> list[str]:
    """The titles the list shows for `query`, in order."""
    html = client.get(f"{reverse(LIST)}?{query}", headers=headers).content.decode()
    return [
        match.strip()
        for match in re.findall(r'<h3 class="fm-row-title"><a href="[^"]+">([^<]*)</a>', html)
    ]


def page_of(client, query: str = "", **headers) -> str:
    response = client.get(f"{reverse(LIST)}?{query}", headers=headers)
    assert response.status_code == 200
    return response.content.decode()


def set_state(obj, state: str) -> None:
    type(obj).objects.filter(pk=obj.pk).update(state=state)


# ---------- Search ----------


@pytest.mark.django_db
def test_search_finds_every_word_in_the_title_or_the_post_in_any_case(client):
    ada = make_member()
    make_post(ada, "Spawning a decal", "Use the When touched block.", age=timedelta(minutes=3))
    make_post(ada, "Terrain tips", "A DECAL can sit on terrain too.", age=timedelta(minutes=2))
    make_post(ada, "Luau basics", "part.Touched:Connect(...)", age=timedelta(minutes=1))
    assert titles(client, "q=decal") == ["Terrain tips", "Spawning a decal"]
    assert titles(client, "q=DeCaL") == ["Terrain tips", "Spawning a decal"]
    # Every word must be there, in the title or the post, in any order.
    assert titles(client, "q=terrain+decal") == ["Terrain tips"]
    assert titles(client, "q=touched+spawning") == ["Spawning a decal"]
    assert titles(client, "q=touched") == ["Luau basics", "Spawning a decal"]
    assert titles(client, "q=++decal++") == ["Terrain tips", "Spawning a decal"]
    assert titles(client, "q=nothing-like-this") == []
    # Part of a word matches; the author's name isn't searched.
    assert titles(client, "q=spawn") == ["Spawning a decal"]
    assert titles(client, "q=ada") == []


@pytest.mark.django_db
def test_a_search_is_shown_back_in_its_box_and_counted(client):
    ada = make_member()
    make_post(ada, "Spawning a decal")
    make_post(ada, "Terrain tips")
    html = page_of(client, "q=decal")
    assert 'name="q" value="decal"' in html
    assert re.search(r"data-post-count>1<", html)
    assert "data-pager" not in html


@pytest.mark.django_db
def test_nothing_matching_says_so_and_offers_to_clear_while_an_empty_forum_has_no_controls(client):
    html = page_of(client)
    assert "data-empty" in html and "data-list-controls" not in html and "data-no-match" not in html
    make_post(make_member(), "Terrain tips")
    html = page_of(client, "q=zzz&rating=4")
    assert "data-no-match" in html and "data-empty" not in html and "data-list-controls" in html
    assert strings.NO_MATCH_TITLE in html
    # Clear is a plain link to the list: the page loads whole, and the form resets with it.
    clear = re.search(r"<a [^>]*data-clear[^>]*>", html)[0]
    assert f'href="{reverse(LIST)}"' in clear and "hx-get" not in clear


# ---------- Filters ----------


@pytest.mark.django_db
def test_the_posted_filter_keeps_posts_from_the_last_day_week_or_month(client):
    ada = make_member()
    make_post(ada, "An hour ago", age=timedelta(hours=1))
    make_post(ada, "Three days ago", age=timedelta(days=3))
    make_post(ada, "Three weeks ago", age=timedelta(days=21))
    make_post(ada, "Three months ago", age=timedelta(days=90))
    assert titles(client, "posted=day") == ["An hour ago"]
    assert titles(client, "posted=week") == ["An hour ago", "Three days ago"]
    assert titles(client, "posted=month") == ["An hour ago", "Three days ago", "Three weeks ago"]
    assert len(titles(client, "posted=")) == 4


@pytest.mark.django_db
def test_the_posted_filter_is_a_rolling_window():
    ada = make_member()
    now = timezone.now()
    for title, age in (("Inside", timedelta(hours=23, minutes=59)), ("Edge", timedelta(days=1))):
        post = ForumPost.objects.create(author=ada, title=title, body="Text.")
        ForumPost.objects.filter(pk=post.pk).update(created=now - age)
    selection = POSTS.read(QueryDict("posted=day"))
    found = selection.apply(ForumPost.objects.with_stats(ada), now=now)
    # A post exactly a day old is no longer "in the past 24 hours" (as the posting limit counts).
    assert [post.title for post in found] == ["Inside"]


@pytest.mark.django_db
def test_the_comments_filter_splits_posts_with_and_without_comments(client):
    ada, bob = make_member("ada"), make_member("bob")
    quiet = make_post(ada, "Quiet", age=timedelta(minutes=2))
    busy = make_post(ada, "Busy", age=timedelta(minutes=1))
    Comment.objects.create(post=busy, author=bob, body="Hello.")
    assert titles(client, "comments=none") == ["Quiet"]
    assert titles(client, "comments=some") == ["Busy"]
    # A hidden comment isn't one a visitor may see, so it doesn't count for them; staff see it.
    hidden = Comment.objects.create(post=quiet, author=bob, body="Hidden.")
    set_state(hidden, "hidden")
    assert titles(client, "comments=some") == ["Busy"]
    staff = Client()
    staff.force_login(make_member("mod", is_staff=True))
    assert titles(staff, "comments=some") == ["Busy", "Quiet"]


@pytest.mark.django_db
def test_the_rating_filter_keeps_posts_averaging_at_least_that_many_stars(client):
    ada = make_member()
    raters = [make_member(f"rater{n}") for n in range(2)]
    scores = {"Five": (5, 5), "Three and a half": (4, 3), "Two": (2,), "Unrated": ()}
    for age, (title, given) in enumerate(scores.items()):
        post = make_post(ada, title, age=timedelta(minutes=age + 1))
        for rater, score in zip(raters, given, strict=False):
            Rating.objects.create(post=post, user=rater, score=score)
    assert titles(client, "rating=4") == ["Five"]
    assert titles(client, "rating=3") == ["Five", "Three and a half"]
    assert titles(client, "rating=2") == ["Five", "Three and a half", "Two"]
    assert len(titles(client)) == 4


@pytest.mark.django_db
def test_search_filters_and_sort_combine(client):
    ada, bob = make_member("ada"), make_member("bob")
    old = make_post(ada, "Decal on terrain", age=timedelta(days=3))
    new = make_post(ada, "Decal on a part", age=timedelta(hours=1))
    make_post(ada, "Terrain tips", age=timedelta(hours=2))
    Comment.objects.create(post=old, author=bob, body="Hello.")
    Comment.objects.create(post=new, author=bob, body="Hello.")
    assert titles(client, "q=decal&comments=some&sort=oldest") == [
        "Decal on terrain",
        "Decal on a part",
    ]
    assert titles(client, "q=decal&comments=some&posted=day") == ["Decal on a part"]
    html = page_of(client, "q=decal&comments=some&sort=oldest")
    shown = state(html, {})
    assert (shown["q"], shown["comments"], shown["sort"], shown["posted"]) == (
        "decal",
        "some",
        "oldest",
        "",
    )


# ---------- Sorting ----------


@pytest.mark.django_db
def test_each_sort_orders_the_list(client):
    ada, bob, cy = make_member("ada"), make_member("bob"), make_member("cy")
    a = make_post(ada, "A", age=timedelta(minutes=5))
    b = make_post(ada, "B", age=timedelta(minutes=4))
    c = make_post(ada, "C", age=timedelta(minutes=3))
    make_post(ada, "D", age=timedelta(minutes=2))
    make_post(ada, "E", age=timedelta(minutes=1))
    Rating.objects.create(post=a, user=bob, score=5)
    Rating.objects.create(post=b, user=bob, score=5)
    Rating.objects.create(post=b, user=cy, score=5)
    Rating.objects.create(post=c, user=bob, score=3)
    for post, count in ((c, 3), (a, 1)):
        for n in range(count):
            Comment.objects.create(post=post, author=bob, body=f"Comment {n}.")
    assert titles(client) == titles(client, "sort=newest") == ["E", "D", "C", "B", "A"]
    assert titles(client, "sort=oldest") == ["A", "B", "C", "D", "E"]
    # Top rated: the higher average first; of equal averages, the one more members rated;
    # unrated posts last, newest first.
    assert titles(client, "sort=top") == ["B", "A", "C", "E", "D"]
    # Most comments: posts with as many, newest first.
    assert titles(client, "sort=comments") == ["C", "A", "E", "D", "B"]


@pytest.mark.django_db
@pytest.mark.parametrize("sort", sorted(SORTS))
def test_ties_keep_one_order_so_no_post_repeats_or_goes_missing_across_pages(client, sort):
    """45 posts published at the same instant, unrated and uncommented but for a few that tie
    with each other: every sort still walks each post exactly once, the same way each time."""
    ada, bob = make_member("ada"), make_member("bob")
    moment = timezone.now() - timedelta(hours=1)
    posts = [
        ForumPost.objects.create(author=ada, title=f"Tie {n:02d}", body="Text.") for n in range(45)
    ]
    ForumPost.objects.update(created=moment)
    for post in posts[10:16]:
        Rating.objects.create(post=post, user=bob, score=4)
        Comment.objects.create(post=post, author=bob, body="Same count.")

    def walk() -> list[str]:
        return [title for page in (1, 2, 3) for title in titles(client, f"sort={sort}&page={page}")]

    first = walk()
    assert len(first) == 45 and sorted(first) == sorted(post.title for post in posts)
    assert walk() == first
    # The pk settles what the sort leaves equal: newest pk first, except oldest first.
    plain = [post.title for post in posts if post not in posts[10:16]]
    assert [title for title in first if title in plain] == (
        plain if sort == "oldest" else plain[::-1]
    )


def test_a_sort_that_could_leave_ties_unordered_is_refused():
    with pytest.raises(ValueError, match="pk"):
        Sort("title", "Title", ("title",))
    with pytest.raises(ValueError, match="pk"):
        Sort("none", "None", ())
    assert all(sort.ordering[-1] in ("pk", "-pk") for sort in POSTS.sorts)


# ---------- Pages ----------


@pytest.mark.django_db
def test_twenty_posts_fit_one_page_and_the_twenty_first_starts_another(client):
    ada = make_member()
    for n in range(20):
        make_post(ada, f"Post {n:02d}", age=timedelta(minutes=60 - n))
    html = page_of(client)
    assert len(titles(client)) == 20 and "data-pager" not in html
    assert re.search(r"data-post-count>20<", html)
    make_post(ada, "The newest")
    html = page_of(client)
    assert len(titles(client)) == 20 and titles(client)[0] == "The newest"
    assert strings_page(1, 2) in html and re.search(r"data-post-count>21<", html)
    # The first page has only Next, the last only Previous; each is a real link.
    assert (
        f'href="{reverse(LIST)}?page=2"' in html
        and 'rel="next"' in html
        and 'rel="prev"' not in html
    )
    html = page_of(client, "page=2")
    assert titles(client, "page=2") == ["Post 00"]
    assert strings_page(2, 2) in html
    assert f'id="post-list-previous" class="ls-page-link" href="{reverse(LIST)}"' in html
    assert 'rel="next"' not in html


def strings_page(number: int, total: int) -> str:
    return POSTS.words.page.format(number=number, total=total)


@pytest.mark.django_db
def test_the_pagers_links_keep_the_search_filters_and_sort(client):
    ada = make_member()
    for n in range(45):
        make_post(ada, f"Decal {n:02d}", age=timedelta(minutes=n + 1))
    html = page_of(client, "q=decal&sort=oldest&posted=day&page=2")
    assert strings_page(2, 3) in html
    base = reverse(LIST)
    assert f'href="{base}?q=decal&amp;sort=oldest&amp;posted=day"' in html  # page 1: no page=
    assert f'href="{base}?q=decal&amp;sort=oldest&amp;posted=day&amp;page=3"' in html
    assert titles(client, "q=decal&sort=oldest&posted=day&page=3") == [
        f"Decal {n:02d}" for n in (4, 3, 2, 1, 0)
    ]


def test_one_state_has_one_url_with_defaults_left_out():
    def url(query: str, **page) -> str:
        return POSTS.read(QueryDict(query)).query(**page)

    assert url("") == url("sort=newest&q=&rating=&page=1") == ""
    assert (
        url("page=3&rating=4&sort=top&q=a+b&comments=some")
        == "?q=a+b&sort=top&comments=some&rating=4"
    )
    assert url("rating=4", page=2) == "?rating=4&page=2"
    assert url("q=a%26b%3Dc+%23d") == "?q=a%26b%3Dc+%23d"  # a search can't add parameters
    assert url("q=%C3%A9") == "?q=%C3%A9"


# ---------- Hidden content ----------


@pytest.mark.django_db
@pytest.mark.parametrize("state_", ["hidden", "removed"])
def test_search_filters_and_counts_never_reach_hidden_posts(client, state_):
    ada, bob = make_member("ada"), make_member("bob")
    make_post(ada, "Visible decal", age=timedelta(minutes=2))
    secret = make_post(ada, "Secret decal", age=timedelta(minutes=1))
    Rating.objects.create(post=secret, user=bob, score=5)
    Comment.objects.create(post=secret, author=bob, body="Hello.")
    set_state(secret, state_)
    author, member, staff = Client(), Client(), Client()
    author.force_login(ada)
    member.force_login(bob)
    staff.force_login(make_member("mod", is_staff=True))
    for viewer in (client, member, author):
        for query in (
            "q=decal",
            "q=secret",
            "rating=4",
            "comments=some",
            "sort=top",
            "sort=comments",
            "",
        ):
            html = page_of(viewer, query)
            assert "Secret decal" not in html, query
        assert re.search(r"data-post-count>1<", page_of(viewer, "q=decal"))
        assert "data-no-match" in page_of(viewer, "q=secret")
    assert titles(staff, "q=decal") == ["Secret decal", "Visible decal"]
    assert titles(staff, "rating=4") == ["Secret decal"]


# ---------- Queries ----------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query", ["", "sort=top", "sort=comments", "q=post&rating=2&comments=some"]
)
def test_the_list_takes_the_same_few_queries_however_many_posts_it_shows(client, query):
    """Comment counts and averages come with the rows (annotations), authors and their
    profiles are joined: no query per post."""
    authors = [make_member(f"author{n}") for n in range(4)]

    def fill(count: int) -> None:
        for n in range(count):
            post = make_post(authors[n % 4], f"Post {n}", age=timedelta(minutes=n + 1))
            for other in authors:
                if other != post.author:
                    Rating.objects.create(post=post, user=other, score=3 + n % 3)
                    Comment.objects.create(post=post, author=other, body="A comment.")

    def queries(viewer) -> int:
        with CaptureQueriesContext(connection) as captured:
            assert viewer.get(f"{reverse(LIST)}?{query}").status_code == 200
        return len(captured)

    member = Client()
    member.force_login(authors[0])
    fill(3)
    few = queries(client), queries(member)
    fill(17)
    assert len(titles(client, query)) == 20
    assert (queries(client), queries(member)) == few
    # A visitor's page is two queries: the count, and the page's rows with everything on them.
    assert few[0] == 2
    fill(25)  # A second and third page change nothing either.
    assert (queries(client), queries(member)) == few


# ---------- HTMX ----------


def is_fragment(html: str) -> bool:
    return "<html" not in html and "<body" not in html


@pytest.mark.django_db
def test_an_htmx_request_gets_the_lists_part_and_the_states_own_url(forum):
    client = Client()
    response = client.get(
        f"{reverse(LIST)}?q=&posted=&comments=&rating=3&sort=newest", headers=HTMX
    )
    html = response.content.decode()
    assert response.status_code == 200 and is_fragment(html)
    assert html.count('id="post-list"') == 1 and "data-list-controls" not in html
    assert "Post 03" in html and "Post 25" not in html
    # The address bar gets the state's URL, not the form's (empty fields, the default sort).
    assert response["HX-Push-Url"] == f"{reverse(LIST)}?rating=3"
    assert "HX-Request" in response["Vary"]
    # The count fills the page's live region, out of band.
    assert '<div hx-swap-oob="innerHTML:#post-list-status"><p>1 post</p></div>' in html
    # The form's request never moves focus: the visitor is still typing.
    assert "autofocus" not in html
    nothing = client.get(f"{reverse(LIST)}?q=zzz", headers=HTMX).content.decode()
    assert f"<p>{strings.NO_MATCH_TITLE}</p>" in nothing and "data-no-match" in nothing


@pytest.mark.django_db
def test_the_plain_page_holds_the_same_part_and_no_swap_markup(forum):
    client = Client()
    response = client.get(f"{reverse(LIST)}?rating=3")
    html = response.content.decode()
    assert not is_fragment(html) and html.count('id="post-list"') == 1
    assert "hx-swap-oob" not in html and "autofocus" not in html
    assert "HX-Push-Url" not in response and "HX-Request" in response["Vary"]
    assert 'id="post-list-status" class="sr-only" role="status"' in html


@pytest.mark.django_db
def test_the_pager_through_htmx_focuses_the_lists_heading(forum):
    client = Client()
    for trigger in ("post-list-next", "post-list-previous"):
        response = client.get(f"{reverse(LIST)}?page=2", headers={**HTMX, "HX-Trigger": trigger})
        html = response.content.decode()
        assert is_fragment(html) and response["HX-Push-Url"] == f"{reverse(LIST)}?page=2"
        assert re.search(r'<h2 id="posts-title"[^>]*tabindex="-1" autofocus>', html)
    # Only the pager's own ids: anything else in the header is just not the pager.
    for trigger in ("post-list-q", "post-list-sort", "post-list-controls", "<img src=x>", ""):
        html = client.get(reverse(LIST), headers={**HTMX, "HX-Trigger": trigger}).content.decode()
        assert "autofocus" not in html and "<img src=x>" not in html


@pytest.mark.django_db
def test_going_back_through_history_gets_the_whole_page(forum):
    """htmx asks for a page it no longer holds with HX-History-Restore-Request, and swaps the
    answer in as the whole page: a fragment there would leave only the list on screen."""
    client = Client()
    response = client.get(
        f"{reverse(LIST)}?sort=oldest", headers={**HTMX, "HX-History-Restore-Request": "true"}
    )
    html = response.content.decode()
    assert not is_fragment(html) and "data-list-controls" in html
    assert "HX-Push-Url" not in response and "hx-swap-oob" not in html
    assert "HX-History-Restore-Request" in response["Vary"]
    assert state(html, forum)["sort"] == "oldest"


@pytest.mark.django_db
def test_the_controls_are_one_get_form_that_works_without_javascript(forum):
    client = Client()
    html = page_of(client)
    form = re.search(r"<form [^>]*data-list-controls>", html)[0]
    assert (
        'method="get"' in form and f'action="{reverse(LIST)}"' in form and 'role="search"' in form
    )
    assert 'hx-target="#post-list"' in form and 'hx-sync="this:replace"' in form
    assert "csrfmiddlewaretoken" not in html.split("data-list-controls")[1].split("</form>")[0]
    # Every control is labelled, and the search box holds no more than a search may.
    for name in ("q", "posted", "comments", "rating", "sort"):
        assert f'<label for="post-list-{name}">' in html and f'id="post-list-{name}"' in html
    assert 'maxlength="100"' in html and 'type="submit"' in html
    for label in (strings.SORT_TOP, strings.POSTED_WEEK, strings.COMMENTS_NONE, strings.RATING_ANY):
        assert label in html
    # What a browser sends for the untouched form (every field, most of them empty) is the
    # default list; the pager's links are real links.
    assert titles(client, "q=&posted=&comments=&rating=&sort=newest") == NEWEST
    assert f'href="{reverse(LIST)}?page=2"' in html


@pytest.mark.django_db
def test_a_listing_refuses_names_and_values_that_would_collide():
    newest = Sort("newest", "Newest", ("-pk",))
    choice = Choice("on", "On", lambda rows, now: rows)
    for name in ("q", "sort", "page"):
        with pytest.raises(ValueError):
            Listing(("title",), (newest,), (Filter(name, "X", "Any", (choice,)),))
    with pytest.raises(ValueError):
        Listing(("title",), ())
    with pytest.raises(ValueError):
        Listing(("title",), (newest, newest))
    with pytest.raises(ValueError):
        Listing(("title",), (newest,), (Filter("x", "X", "Any", (choice, choice)),))
    with pytest.raises(ValueError):
        Listing(
            ("title",), (newest,), (Filter("x", "X", "Any", (Choice("", "Empty", choice.narrow),)),)
        )


def test_page_numbers_and_searches_are_cleaned():
    assert [clean_page(raw) for raw in ("", "1", "2", "007", "0", "000")] == [1, 1, 2, 7, 1, 1]
    assert [clean_page(raw) for raw in ("-1", "1.5", " 2", "2\n", "٢", "²", "1_000", "+2")] == [
        1
    ] * 8
    assert clean_page("999999999") == 999_999_999 and clean_page("9" * 10) == PAST_THE_END
    assert clean_search("  two   words \n") == "two words"
    assert clean_search("a\x00b\tc\r\nd\x7fe") == "a b c d e"
    assert clean_search("x" * 300) == "x" * 100
    assert clean_search(" ".join(f"w{n}" for n in range(12))) == "w0 w1 w2 w3 w4 w5 w6 w7"
    assert clean_search("é" * 99 + " tail") == "é" * 99  # cut at 100, the space trimmed
    assert clean_search("\x00\x01") == ""


# ---------- The demo posts (seed_forum_demo) ----------


@pytest.mark.django_db
def test_the_forum_demo_seed_refuses_to_run_outside_development(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_forum_demo")
    assert not User.objects.exists() and not ForumPost.objects.exists()


@pytest.mark.django_db
def test_the_forum_demo_seed_fills_three_pages_once_and_leaves_what_exists_alone(settings, client):
    settings.DEBUG = True
    real_bob = User.objects.create_user("Bob", "real@example.com", "bobs-own-password-9")
    call_command("seed_forum_demo")
    counts = ForumPost.objects.count(), Comment.objects.count(), Rating.objects.count()
    call_command("seed_forum_demo")  # again: nothing changes
    assert (ForumPost.objects.count(), Comment.objects.count(), Rating.objects.count()) == counts
    assert counts[0] == 45 and ForumPost.objects.values("title").distinct().count() == 45

    assert User.objects.count() == 6
    assert not User.objects.filter(is_staff=True).exists()
    assert not User.objects.filter(is_superuser=True).exists()
    real_bob.refresh_from_db()
    assert real_bob.check_password("bobs-own-password-9") and real_bob.email == "real@example.com"

    # Three pages, and every filter and order has something to show.
    assert POSTS.words.page.format(number=1, total=3) in page_of(client)
    assert len(titles(client, "page=3")) == 5
    assert 0 < len(titles(client, "posted=day")) < len(titles(client, "posted=week")) < 20
    assert titles(client, "comments=none") and titles(client, "comments=some")
    assert 0 < len(titles(client, "rating=4")) < len(titles(client, "rating=2"))
    assert len(titles(client, "q=decal")) == 3
    assert titles(client, "sort=oldest")[0] == titles(client, "page=3")[-1]
    # Nothing is dated in the future, and every demo member can still post and comment.
    now = timezone.now()
    assert not ForumPost.objects.filter(created__gt=now).exists()
    assert not Comment.objects.filter(created__gt=now).exists()
    for member in User.objects.exclude(pk=real_bob.pk):  # (the real Bob never verified)
        services.create_post(member, title="One more", body="Still allowed.")
        services.add_comment(member, ForumPost.objects.exclude(author=member).first(), body="Yes.")
