"""Production settings (DJANGO_DEBUG=false): `check --deploy` passes, every security
setting is on, and the site refuses to start without a real secret key and allowed hosts.
Each case runs Django in a subprocess with its own environment (no network involved)."""

import json
import os
import re
import subprocess
import sys

import pytest
from django.conf import settings

# A made-up key in the shape `check --deploy` wants (50+ characters, varied, no prefix).
SECRET = "k3V9-pQ2_xR7#mT1$wL8&zN4!bH6^cJ0*fD5@gS2(yU9)eA3+oI7=qP1"
PRODUCTION = {
    "DJANGO_DEBUG": "false",
    "DJANGO_SECRET_KEY": SECRET,
    "DJANGO_ALLOWED_HOSTS": "hub.example.com",
}


def run(args: list[str], **env: str) -> subprocess.CompletedProcess:
    clean = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("DJANGO_", "TURNSTILE_", "GITHUB_", "HUB_"))
    }
    clean["DJANGO_SETTINGS_MODULE"] = "config.settings"
    return subprocess.run(
        [sys.executable, *args], cwd=settings.BASE_DIR, env={**clean, **env},
        capture_output=True, text=True, timeout=120,
    )  # fmt: skip


def production_settings(**env: str) -> dict:
    code = (
        "import json, django; django.setup(); from django.conf import settings as s; "
        "print(json.dumps({k: getattr(s, k, None) for k in ["
        "'DEBUG', 'ALLOWED_HOSTS', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE', "
        "'THEME_COOKIE_SECURE', 'SESSION_COOKIE_HTTPONLY', 'SESSION_COOKIE_SAMESITE', "
        "'CSRF_COOKIE_SAMESITE', 'SECURE_SSL_REDIRECT', 'SECURE_HSTS_SECONDS', "
        "'SECURE_HSTS_INCLUDE_SUBDOMAINS', 'SECURE_HSTS_PRELOAD', 'X_FRAME_OPTIONS', "
        "'SECURE_CONTENT_TYPE_NOSNIFF', 'SECURE_REFERRER_POLICY', 'SECURE_PROXY_SSL_HEADER', "
        "'CSRF_TRUSTED_ORIGINS']} | {'cache': s.CACHES['default']['BACKEND'], "
        "'mail': s.MAILERS['default']['BACKEND']}))"
    )
    result = run(["-c", code], **{**PRODUCTION, **env})
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_check_deploy_passes_with_no_warnings():
    result = run(["manage.py", "check", "--deploy", "--fail-level", "WARNING"], **PRODUCTION)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no issues" in result.stdout


def test_every_security_setting_is_on_in_production():
    values = production_settings()
    assert values == {
        "DEBUG": False,
        "ALLOWED_HOSTS": ["hub.example.com"],
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
        "THEME_COOKIE_SECURE": True,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "CSRF_COOKIE_SAMESITE": "Lax",
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 31536000,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
        "SECURE_HSTS_PRELOAD": True,
        "X_FRAME_OPTIONS": "DENY",
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_REFERRER_POLICY": "same-origin",
        "SECURE_PROXY_SSL_HEADER": None,
        "CSRF_TRUSTED_ORIGINS": [],
        # A cache every process shares, so rate limits hold across workers.
        "cache": "django.core.cache.backends.db.DatabaseCache",
        # Real email (SMTP from the environment), never the console.
        "mail": "django.core.mail.backends.smtp.EmailBackend",
    }


def test_behind_a_proxy_https_is_read_from_the_forwarded_header_only_when_asked():
    values = production_settings(
        DJANGO_BEHIND_PROXY="true", DJANGO_CSRF_TRUSTED_ORIGINS="https://hub.example.com"
    )
    assert values["SECURE_PROXY_SSL_HEADER"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert values["CSRF_TRUSTED_ORIGINS"] == ["https://hub.example.com"]


def test_redis_is_the_shared_cache_when_configured():
    values = production_settings(DJANGO_REDIS_URL="redis://cache.internal:6379/0")
    assert values["cache"] == "django.core.cache.backends.redis.RedisCache"


@pytest.mark.parametrize(
    ("env", "complaint"),
    [
        ({"DJANGO_SECRET_KEY": ""}, "DJANGO_SECRET_KEY"),
        ({"DJANGO_SECRET_KEY": "django-insecure-" + "x1y2z3" * 10}, "DJANGO_SECRET_KEY"),
        ({"DJANGO_SECRET_KEY": "short-but-varied-123"}, "DJANGO_SECRET_KEY"),
        ({"DJANGO_SECRET_KEY": "a" * 60}, "DJANGO_SECRET_KEY"),
        ({"DJANGO_ALLOWED_HOSTS": ""}, "DJANGO_ALLOWED_HOSTS"),
    ],
)
def test_production_refuses_to_start_without_a_real_key_and_hosts(env, complaint):
    result = run(["manage.py", "check"], **{**PRODUCTION, **env})
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr and complaint in result.stderr


GITHUB_APP = {"GITHUB_CLIENT_ID": "Ov23liTestClientId", "GITHUB_CLIENT_SECRET": "test-secret"}
TOKEN_KEY = "eE5nY3VhTnJ0d1lCV0lQZ3VHWHZmS2F6c0p6Q0JxS0Q="


def test_production_refuses_github_linking_without_a_token_key():
    result = run(["manage.py", "check"], **{**PRODUCTION, **GITHUB_APP})
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr and "GITHUB_TOKEN_KEYS" in result.stderr
    # With a key it starts, and check --deploy still passes.
    result = run(
        ["manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        **{**PRODUCTION, **GITHUB_APP, "GITHUB_TOKEN_KEYS": TOKEN_KEY},
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_malformed_token_key_is_refused_without_echoing_it():
    bad = "not-a-fernet-key-but-a-secret-all-the-same"
    result = run(["manage.py", "check"], GITHUB_TOKEN_KEYS=bad)
    assert result.returncode != 0
    assert "GITHUB_TOKEN_KEYS" in result.stderr and bad not in result.stderr


def test_the_public_url_is_allowed_trusted_for_forms_and_must_be_a_scheme_and_host_only():
    code = (
        "import django; django.setup(); from django.conf import settings as s; "
        "print(s.ALLOWED_HOSTS, s.CSRF_TRUSTED_ORIGINS, s.HUB_PUBLIC_URL)"
    )
    result = run(["-c", code], HUB_PUBLIC_URL="https://hub-dev.example.com/")
    assert result.returncode == 0, result.stderr
    # Behind a tunnel the browser posts from https://hub-dev.example.com while Django sees
    # http: trusting the public origin is what lets sign-in through it pass the CSRF check.
    assert result.stdout.strip() == (
        "['localhost', '127.0.0.1', 'hub-dev.example.com'] ['https://hub-dev.example.com'] "
        "https://hub-dev.example.com"
    )
    # Development reads DJANGO_CSRF_TRUSTED_ORIGINS too, and trusts nothing extra by default.
    result = run(["-c", code], DJANGO_CSRF_TRUSTED_ORIGINS="https://other.example.com")
    assert "['https://other.example.com']" in result.stdout
    assert run(["-c", code]).stdout.strip() == "['localhost', '127.0.0.1'] []"
    for bad in [
        "hub-dev.example.com",
        "ftp://hub.example.com",
        "https://hub.example.com/hub",
        "https://",
    ]:
        result = run(["manage.py", "check"], HUB_PUBLIC_URL=bad)
        assert result.returncode != 0 and "HUB_PUBLIC_URL" in result.stderr, bad


def test_env_example_lists_every_variable_settings_reads_and_holds_no_values():
    source = (settings.BASE_DIR / "config" / "settings.py").read_text(encoding="utf-8")
    read = set(re.findall(r'(?:environ\.get|environ\[|env_bool|env_list)\(?\s*"([A-Z_]+)"', source))
    assert {"DJANGO_SECRET_KEY", "GITHUB_TOKEN_KEYS", "AXCENITY_ENGINE_DIR"} <= read
    example = (settings.BASE_DIR / ".env.example").read_text(encoding="utf-8")
    listed = set(re.findall(r"^#? ?([A-Z_]+)=", example, re.M))
    assert read <= listed, read - listed
    # Live (uncommented) lines are names only: the example never carries a value.
    live = [line for line in example.splitlines() if line and not line.startswith("#")]
    assert live and all(re.fullmatch(r"[A-Z_]+=", line) for line in live), live
    # The real .env stays out of git.
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".env"], cwd=settings.BASE_DIR, check=False
    )
    assert ignored.returncode == 0


def test_development_is_the_default_and_still_sends_the_security_headers(client):
    # (The test runner forces DEBUG off itself; the cookies show development's settings.)
    assert not settings.SESSION_COOKIE_SECURE and not settings.CSRF_COOKIE_SECURE
    response = client.get("/")
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"
