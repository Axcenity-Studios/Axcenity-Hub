"""The error pages (config/errors.py): every status renders the Hub's page, with no session or
database, nothing the visitor sent echoed back, and developer details only under DEBUG."""

import re
from html import unescape

import pytest
from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from config import errors, urls

STATUSES = {"400": 400, "403": 403, "csrf": 403, "404": 404, "405": 405, "429": 429, "500": 500}


def is_hub_page(response, kind: str) -> str:
    html = unescape(response.content.decode())
    page = errors.PAGES[kind]
    assert response.status_code == STATUSES[kind]
    assert f'data-error="{kind}"' in html
    assert page.title in html and page.lede in html
    assert f"<title>{page.status} {page.name} · Axcenity</title>" in html
    assert reverse("marketing:home") in html and reverse("documentation:index") in html
    assert "no-store" in response["Cache-Control"]
    return html


def test_every_page_has_its_words_and_the_handlers_are_wired():
    assert set(errors.PAGES) == set(STATUSES)
    assert {k: p.status for k, p in errors.PAGES.items()} == STATUSES
    assert urls.handler400 == "config.errors.bad_request"
    assert urls.handler403 == "config.errors.permission_denied"
    assert urls.handler404 == "config.errors.page_not_found"
    assert urls.handler500 == "config.errors.server_error"
    assert urls.handler429 == "config.errors.too_many_requests"


@pytest.mark.django_db
def test_an_unknown_address_gets_the_hubs_404_without_echoing_it(client):
    hostile = "/no-such-page/<script>alert(1)</script>/"
    response = client.get(hostile)
    html = is_hub_page(response, "404")
    assert "<script>alert(1)</script>" not in response.content.decode()
    assert "no-such-page" not in html


@pytest.mark.django_db
def test_another_members_project_is_the_same_404(client):
    from django.contrib.auth import get_user_model

    from projects.models import Project

    User = get_user_model()
    Project.objects.create(owner=User.objects.create_user("grace"), name="Space Game")
    client.force_login(User.objects.create_user("ada"))
    is_hub_page(client.get("/projects/space-game/"), "404")


@pytest.mark.django_db
def test_a_refused_form_gets_the_csrf_page_with_the_reason_only_in_development(settings):
    client = Client(enforce_csrf_checks=True)
    html = is_hub_page(client.post(reverse("account_login"), {"login": "x"}), "csrf")
    assert "data-error-debug" not in html and "HUB_PUBLIC_URL" not in html
    settings.DEBUG = True
    html = is_hub_page(
        client.post(reverse("account_login"), {"login": "x"}, HTTP_ORIGIN="https://evil.example"),
        "csrf",
    )
    assert "data-error-debug" in html and "HUB_PUBLIC_URL" in html
    assert "Origin checking failed" in html  # Django's own reason, for the developer


@pytest.mark.django_db
def test_a_host_the_hub_doesnt_serve_gets_the_400_page(client):
    is_hub_page(client.get("/", HTTP_HOST="evil.example"), "400")


@pytest.mark.django_db
def test_an_empty_405_gets_the_page_and_keeps_allow(client):
    # The webhook takes POST only.
    response = client.get("/projects/hooks/github/00000000-0000-0000-0000-000000000000/")
    is_hub_page(response, "405")
    assert response["Allow"] == "POST"


@pytest.mark.django_db  # (to count queries: there must be none)
def test_the_500_and_429_pages_need_no_database_or_session():
    request = RequestFactory().get("/", HTTP_COOKIE="ax-theme=light")
    with CaptureQueriesContext(connection) as queries:
        for kind, handler in [("500", errors.server_error), ("429", errors.too_many_requests)]:
            html = is_hub_page(handler(request), kind)
            # The theme cookie still applies.
            assert 'data-scheme-choice="light"' in html
    assert len(queries) == 0


def test_allauths_rate_limit_uses_the_hubs_429():
    from allauth.core.ratelimit import respond_429

    is_hub_page(respond_429(RequestFactory().get("/accounts/login/")), "429")


def test_a_permission_error_gets_the_403_page():
    is_hub_page(errors.permission_denied(RequestFactory().get("/")), "403")


@pytest.mark.django_db
def test_the_preview_works_only_on_a_development_server(client, settings):
    for kind in STATUSES:
        response = client.get(reverse("errors:preview", args=[kind]))
        is_hub_page(response, "404")
    settings.DEBUG = True
    for kind in STATUSES:
        is_hub_page(client.get(reverse("errors:preview", args=[kind])), kind)
    assert client.get(reverse("errors:preview", args=["418"])).status_code == 404


def test_the_page_is_one_template_in_tokens_only():
    from django.conf import settings

    source = (settings.BASE_DIR / "templates" / "errors" / "page.html").read_text()
    assert "{% csrf_token %}" not in source and "user." not in source and "request." not in source
    css = (settings.BASE_DIR / "styles" / "source.css").read_text()
    block = css[css.index("/* ---------- Error pages") : css.index(".entrance { display: grid;")]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)  # colours come from the tokens
