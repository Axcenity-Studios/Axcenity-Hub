"""Accounts: the email-verification gate, unique usernames and emails, sign-up, sign-in
and the profile (see docs/architecture/accounts.md)."""

import re

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.signals import post_delete, post_save
from django.test import Client
from django.urls import reverse

from accounts import signals as account_signals
from accounts.access import EmailNotVerified, ensure_can_contribute
from accounts.integrity import CaseDuplicatesFound
from accounts.models import Profile
from accounts.views import EmailView
from tests import gate_urls

User = get_user_model()
PASSWORD = "a-Long-pass-7731"


@pytest.fixture
def contributions():
    gate_urls.CONTRIBUTIONS.clear()
    yield gate_urls.CONTRIBUTIONS
    gate_urls.CONTRIBUTIONS.clear()


def make_member(username="ada", email="ada@example.com", *, verified: bool) -> User:
    user = User.objects.create_user(username, email, PASSWORD)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    return user


# ---------- The email-verification gate ----------


@pytest.mark.django_db
@pytest.mark.urls("tests.gate_urls")
def test_an_unverified_member_signs_in_but_cannot_contribute_until_verified(client, contributions):
    user = make_member(verified=False)

    # They can sign in with their password...
    response = client.post(
        reverse("account_login"), {"login": "ada@example.com", "password": PASSWORD}
    )
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)

    # ...but a contribution is refused: sent to verify, nothing created, the link re-sent.
    response = client.post("/contribute/")
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:verify_email"))
    assert contributions == []
    assert [m.to for m in mail.outbox] == [["ada@example.com"]]
    with pytest.raises(EmailNotVerified):
        ensure_can_contribute(user)

    # Once the address is verified, the same request goes through.
    EmailAddress.objects.filter(user=user).update(verified=True)
    response = client.post("/contribute/")
    assert response.status_code == 200
    assert contributions == [user.pk]
    ensure_can_contribute(user)  # doesn't raise


# ---------- Unique usernames and emails, whatever their case ----------


@pytest.mark.django_db
def test_usernames_and_emails_are_unique_whatever_their_case(client):
    alice = make_member("alice", "alice@example.com", verified=True)

    # Through sign-up: a username that differs only in case is refused...
    response = client.post(
        reverse("account_signup"),
        {
            "email": "new@example.com",
            "username": "ALICE",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert response.status_code == 200
    assert "username" in response.context["form"].errors
    # ...and an email that differs only in case creates no second account.
    client.post(
        reverse("account_signup"),
        {
            "email": "Alice@Example.COM",
            "username": "bob",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    assert list(User.objects.values_list("username", flat=True)) == ["alice"]

    # Around the forms (the admin, the shell, two signups racing): the database refuses too.
    for username, email in [("Alice", "other@example.com"), ("carol", "ALICE@example.com")]:
        with pytest.raises(IntegrityError), transaction.atomic():
            User.objects.create_user(username, email, PASSWORD)
    carol = User.objects.create_user("carol", "carol@example.com", PASSWORD)
    with pytest.raises(IntegrityError), transaction.atomic():
        EmailAddress.objects.create(user=carol, email="ALICE@EXAMPLE.COM", verified=False)

    assert User.objects.filter(username__iexact="alice").get() == alice
    assert EmailAddress.objects.filter(email__iexact="alice@example.com").count() == 1


def _migrate_accounts(to: str = "") -> None:
    """Migrate the accounts app to `to`, or to its latest migration."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    target = ("accounts", to) if to else executor.loader.graph.leaf_nodes("accounts")[0]
    executor.migrate([target])


@pytest.mark.django_db(transaction=True)
def test_the_index_migration_stops_on_existing_case_duplicates_and_changes_nothing():
    _migrate_accounts("0001_initial")  # before the indexes
    # Profiles at 0001 have no photo column yet: the receivers that read the current model
    # stay out of the way until the migrations are back at the latest.
    post_save.disconnect(account_signals.create_profile, sender=settings.AUTH_USER_MODEL)
    post_delete.disconnect(account_signals.delete_photo, sender=Profile)
    try:
        ann = User.objects.create_user("ann", "ann@example.com", PASSWORD)
        ann2 = User.objects.create_user("Ann", "ANN@example.com", PASSWORD)
        EmailAddress.objects.create(user=ann, email="ann@example.com")
        EmailAddress.objects.create(user=ann2, email="Ann@Example.com")
        before = list(User.objects.order_by("pk").values_list("pk", "username", "email"))

        with pytest.raises(CaseDuplicatesFound) as refused:
            _migrate_accounts("0002_case_insensitive_unique_indexes")

        message = str(refused.value)
        for expected in [
            f"auth_user.username 'ann': id {ann.pk} 'ann', id {ann2.pk} 'Ann'",
            f"auth_user.email 'ann@example.com': id {ann.pk} 'ann@example.com', id {ann2.pk} 'ANN@example.com'",
            "account_emailaddress.email 'ann@example.com'",
            "nothing was deleted or merged",
        ]:
            assert expected in message
        # Nothing was deleted, merged or renamed.
        assert list(User.objects.order_by("pk").values_list("pk", "username", "email")) == before
        assert EmailAddress.objects.count() == 2
    finally:
        User.objects.filter(username="Ann").delete()
        _migrate_accounts()  # back to the latest, for the tests after this one
        post_save.connect(account_signals.create_profile, sender=settings.AUTH_USER_MODEL)
        post_delete.connect(account_signals.delete_photo, sender=Profile)


# ---------- The verification policy end to end, through allauth's real views ----------


def _page(response) -> str:
    """A page's HTML without its CSRF token, so two responses can be compared exactly."""
    html = response.content.decode()
    return re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', 'name="csrfmiddlewaretoken"', html)


def _signup(client, email: str, username: str):
    return client.post(
        reverse("account_signup"),
        {"email": email, "username": username, "password1": PASSWORD, "password2": PASSWORD},
    )


def _signed_in(client) -> bool:
    return "_auth_user_id" in client.session


@pytest.mark.django_db
@pytest.mark.urls("tests.gate_urls")
def test_signup_and_password_login_hold_the_whole_verification_policy(contributions):
    # A new address: allauth's mandatory signup. No account is signed in yet, a verification
    # link is sent, and the "check your inbox" page is shown.            (requirement 3)
    newcomer = Client()
    fresh = _signup(newcomer, "ada@example.com", "ada")
    assert fresh.status_code == 302 and fresh["Location"] == reverse(
        "account_email_verification_sent"
    )
    fresh_page = _page(newcomer.get(fresh["Location"]))
    assert not _signed_in(newcomer)
    ada = User.objects.get(username="ada")
    assert [(m.to, "confirm" in m.subject.lower()) for m in mail.outbox] == [
        (["ada@example.com"], True)
    ]
    link = re.search(r"http://testserver(/accounts/confirm-email/[^\s]+/)", mail.outbox[0].body)[1]

    # The same address again, as typed and in another case: the same response and page as a
    # new address, nobody signed in, no second account; the owner is told once (allauth's
    # per-address cooldown holds back the second notice, a few minutes after the first;
    # clearing the cache stands for that time passing).             (requirements 4, 5)
    mail.outbox.clear()
    cache.clear()
    for n, typed in enumerate(["ada@example.com", "ADA@Example.COM"]):
        stranger = Client()
        taken = _signup(stranger, typed, f"someone{n}")
        assert (taken.status_code, taken["Location"]) == (fresh.status_code, fresh["Location"])
        assert _page(stranger.get(taken["Location"])) == fresh_page
        assert not _signed_in(stranger)
    assert list(User.objects.values_list("username", flat=True)) == ["ada"]
    assert list(EmailAddress.objects.values_list("email", flat=True)) == ["ada@example.com"]
    assert [(m.to, m.subject) for m in mail.outbox] == [
        (["ada@example.com"], "[Axcenity Hub] Account Already Exists")
    ]

    # The new account, still unverified, signs in with its password.       (requirement 1)
    mail.outbox.clear()
    cache.clear()  # a few minutes later, past the cooldown, so the gate's re-send goes out
    member = Client()
    response = member.post(
        reverse("account_login"), {"login": "ada@example.com", "password": PASSWORD}
    )
    assert response.status_code == 302 and response["Location"] == reverse("accounts:profile")
    assert member.session["_auth_user_id"] == str(ada.pk)
    assert EmailAddress.objects.get(user=ada).verified is False

    # It can't contribute until verified; the gate re-sends the link.         (requirement 2)
    response = member.post("/contribute/")
    assert response["Location"].startswith(reverse("accounts:verify_email"))
    assert contributions == [] and [m.to for m in mail.outbox] == [["ada@example.com"]]

    # Following the first email's link verifies it, and contributing works.
    assert member.post(link).status_code == 302
    assert EmailAddress.objects.get(user=ada).verified is True
    assert member.post("/contribute/").status_code == 200 and contributions == [ada.pk]

    # And a failed sign-in reads the same for an unknown email and a wrong password. (5)
    unknown = Client().post(
        reverse("account_login"), {"login": "nobody@example.com", "password": PASSWORD}
    )
    wrong = Client().post(
        reverse("account_login"), {"login": "ada@example.com", "password": "wrong-Pass-1"}
    )
    assert unknown.status_code == wrong.status_code == 200
    assert _page(unknown).replace("nobody@example.com", "EMAIL") == _page(wrong).replace(
        "ada@example.com", "EMAIL"
    )


# ---------- Registration rules ----------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("username", "reason"),
    [
        ("ab", "at least 3"),
        ("a" * 31, "at most 30"),
        ("has space", "letters, digits"),
        ("dot.name", "letters, digits"),
        ("émile", "letters, digits"),
        ("<b>x</b>", "letters, digits"),
        ("Admin", "can not be used"),
        ("MODERATOR", "can not be used"),
    ],
)
def test_signup_refuses_invalid_usernames(client, username, reason):
    response = _signup(client, "new@example.com", username)
    assert response.status_code == 200
    errors = " ".join(response.context["form"].errors["username"])
    assert reason in errors.lower()
    assert not User.objects.exists()
    assert "<b>x</b>" not in response.content.decode()


@pytest.mark.django_db
def test_signup_refuses_weak_or_mismatched_passwords(client):
    weak = client.post(
        reverse("account_signup"),
        {
            "email": "a@example.com",
            "username": "ada",
            "password1": "password",
            "password2": "password",
        },
    )
    assert "password1" in weak.context["form"].errors
    mismatched = client.post(
        reverse("account_signup"),
        {
            "email": "a@example.com",
            "username": "ada",
            "password1": PASSWORD,
            "password2": PASSWORD + "x",
        },
    )
    assert mismatched.context["form"].errors
    assert not User.objects.exists()


@pytest.mark.django_db
def test_a_valid_signup_stores_the_username_as_typed_and_the_email_lower_cased(client):
    _signup(client, "Ada.Lovelace@Example.COM", "AdaL")
    user = User.objects.get()
    assert (user.username, user.email) == ("AdaL", "ada.lovelace@example.com")
    assert EmailAddress.objects.get(user=user).email == "ada.lovelace@example.com"


@pytest.mark.django_db
def test_the_admin_refuses_case_only_duplicates_with_a_message():
    from accounts.admin import EMAIL_TAKEN, USERNAME_TAKEN, HubUserChangeForm, HubUserCreationForm

    make_member("alice", "alice@example.com", verified=True)
    form = HubUserCreationForm(
        data={
            "username": "ALICE",
            "email": "Alice@Example.com",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
    )
    assert not form.is_valid()
    assert USERNAME_TAKEN in form.errors["username"] and EMAIL_TAKEN in form.errors["email"]
    bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
    change = HubUserChangeForm(
        instance=bob,
        data={"username": "bob", "email": "ALICE@example.com", "date_joined": bob.date_joined},
    )
    assert not change.is_valid() and EMAIL_TAKEN in change.errors["email"]


# ---------- Profile ----------


@pytest.mark.django_db
def test_every_new_user_gets_a_profile():
    user = User.objects.create_user("ada", "ada@example.com", PASSWORD)
    assert Profile.objects.get(user=user).name == "ada"


@pytest.mark.django_db
def test_a_member_edits_their_own_profile(client):
    user = make_member(verified=False)  # editing a profile isn't a contribution
    client.force_login(user)
    response = client.post(
        reverse("accounts:profile"), {"display_name": "  Ada   Lovelace ", "bio": "Hi."}
    )
    assert response.status_code == 302 and response["Location"] == reverse("accounts:profile")
    user.profile.refresh_from_db()
    assert (user.profile.display_name, user.profile.bio) == ("Ada Lovelace", "Hi.")
    page = client.get(reverse("accounts:profile")).content.decode()
    assert "Profile saved." in page and "Ada Lovelace" in page


@pytest.mark.django_db
def test_profile_limits_and_markup_are_refused_or_escaped(client):
    user = make_member(verified=True)
    client.force_login(user)
    too_long = client.post(
        reverse("accounts:profile"), {"display_name": "x" * 51, "bio": "y" * 501}
    )
    assert set(too_long.context["form"].errors) == {"display_name", "bio"}
    client.post(reverse("accounts:profile"), {"display_name": "<script>x</script>", "bio": ""})
    assert "<script>x</script>" not in client.get(reverse("accounts:profile")).content.decode()


@pytest.mark.django_db
def test_a_user_made_before_profiles_existed_gets_one_on_first_visit(client):
    user = make_member(verified=True)
    Profile.objects.filter(user=user).delete()
    client.force_login(user)
    assert client.get(reverse("accounts:profile")).status_code == 200
    assert Profile.objects.filter(user=user).exists()


# ---------- Email page (status and resend only) ----------


@pytest.mark.django_db
def test_the_email_page_is_the_hubs_and_offers_no_way_to_add_an_address(client):
    client.force_login(make_member(verified=True))
    response = client.get(reverse("account_email"))
    assert response.resolver_match.func.view_class is EmailView
    html = response.content.decode()
    assert "ada@example.com" in html and "Verified" in html
    assert 'name="action_add"' not in html and 'type="email"' not in html
    # allauth's add action posted directly does nothing either.
    client.post(reverse("account_email"), {"action_add": "", "email": "second@example.com"})
    assert list(EmailAddress.objects.values_list("email", flat=True)) == ["ada@example.com"]


@pytest.mark.django_db
def test_an_unverified_member_can_resend_the_link(client):
    client.force_login(make_member(verified=False))
    response = client.post(reverse("account_email"))
    assert response.status_code == 302
    assert [m.to for m in mail.outbox] == [["ada@example.com"]]
    # Straight away again: allauth's cooldown holds it back, and the page says so.
    client.post(reverse("account_email"))
    assert len(mail.outbox) == 1
    assert "sent a moment ago" in client.get(reverse("account_email")).content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target", ["https://evil.example/", "//evil.example/x", "javascript:alert(1)"]
)
def test_the_verify_page_never_continues_off_site(client, target):
    client.force_login(make_member(verified=True))
    html = client.get(reverse("accounts:verify_email"), {"next": target}).content.decode()
    hrefs = re.findall(r'(?:href|action|value)="([^"]*)"', html)
    assert not [h for h in hrefs if h.startswith(("http", "//", "javascript:"))]
    assert 'name="next"' not in html.split('id="content"')[1]  # no hidden next carried on


@pytest.mark.django_db
def test_the_verify_page_explains_the_gate_and_continues_once_verified(client):
    client.force_login(make_member(verified=True))
    html = client.get(reverse("accounts:verify_email"), {"next": "/docs/"}).content.decode()
    assert "Verify your email address before you post" in html
    assert 'href="/docs/"' in html


# ---------- The app shell ----------


@pytest.mark.django_db
def test_the_app_shell_frames_account_pages_as_tabs_of_account_settings(client):
    client.force_login(make_member(verified=True))
    for name, current in [
        ("accounts:profile", "Profile"),
        ("account_email", "Email"),
        ("account_change_password", "Password"),
        ("mfa_index", "Two-factor"),
        ("socialaccount_connections", "Connected accounts"),
    ]:
        html = client.get(reverse(name)).content.decode()
        assert 'class="app-bar"' in html and 'id="app-rail"' in html, name
        assert "Account center" in html  # the bar names the place, not "Hub"
        rail = html[
            html.index('id="app-rail"') : html.index("</details>", html.index('id="app-rail"'))
        ]
        # The rail has one Account item; every account page is its current page.
        assert re.findall(
            r'class="app-rail-link"[^>]*>\s*<svg.*?</svg>\s*([^<]+?)\s*<', rail, re.S
        ) == ["Projects", "Forums", "Showcases", "Account settings"]
        assert re.findall(r'aria-current="page">\s*<svg.*?</svg>\s*([^<]+?)\s*<', rail, re.S) == [
            "Account settings"
        ], name
        # The page itself shows the settings' tabs, with its own tab current.
        tabs = html[
            html.index('class="ac-tabs"') : html.index("</nav>", html.index('class="ac-tabs"'))
        ]
        assert re.findall(r'class="ac-tab"[^>]*>\s*<svg.*?</svg>\s*([^<]+?)\s*<', tabs, re.S) == [
            "Profile",
            "Email",
            "Password",
            "Two-factor",
            "Connected accounts",
        ]
        assert re.findall(r'aria-current="page">\s*<svg.*?</svg>\s*([^<]+?)\s*<', tabs, re.S) == [
            current
        ], name
        # Signing out is a POST with a CSRF token, never a link.
        assert re.search(
            rf'<form method="post" action="{reverse("account_logout")}">\s*<input type="hidden" name="csrfmiddlewaretoken"',
            html,
        )
        # The rail is open without JavaScript; a script folds it on phones.
        assert '<details id="app-rail" class="app-rail" open>' in html


@pytest.mark.django_db
def test_the_settings_header_shows_the_account_at_a_glance(client):
    member = make_member(verified=True)
    client.force_login(member)
    html = client.get(reverse("account_email")).content.decode()
    head = html[html.index('class="panel pj-panel ac-head"') : html.index('class="ac-tabs"')]
    assert "@" + member.username in head and "Member since" in head
    # Each state links to its tab: verified email, two-factor off, no GitHub.
    stats = re.findall(
        r'href="([^"]+)" class="ac-stat">.*?class="ac-stat-value"( data-on)?>([^<]+)<', head, re.S
    )
    assert stats == [
        (reverse("account_email"), " data-on", "Verified"),
        (reverse("mfa_index"), "", "Off"),
        (reverse("socialaccount_connections"), "", "Not linked"),
    ]


@pytest.mark.django_db
def test_entrance_pages_use_the_slim_entrance_layout(client):
    for name in ["account_login", "account_signup", "account_reset_password"]:
        html = client.get(reverse(name)).content.decode()
        assert 'class="entrance grid-bg"' in html and 'class="entrance-panel panel"' in html, name
        assert 'id="app-rail"' not in html and 'id="site-nav"' not in html, name


@pytest.mark.django_db
def test_the_settings_header_shows_a_github_link_that_needs_reconnecting(client):
    from allauth.socialaccount.models import SocialAccount

    member = make_member(verified=True)
    # A link with no stored token can't be used (as on Connected accounts): it needs reconnecting.
    SocialAccount.objects.create(user=member, provider="github", uid="1", extra_data={})
    client.force_login(member)
    html = client.get(reverse("accounts:profile")).content.decode()
    assert re.search(
        rf'href="{reverse("socialaccount_connections")}" class="ac-stat">.*?class="ac-stat-value">Reconnect<',
        html,
        re.S,
    )
