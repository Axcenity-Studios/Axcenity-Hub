"""Django settings for Axcenity Hub.

Development defaults live here. Secrets and anything that differs in
production come from environment variables only (Phase 8 hardens the
production settings). Never put a real secret in this file.
"""

import mimetypes
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    """Read a true/false environment variable ("1", "true", "yes", "on" are true)."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = env_bool("DJANGO_DEBUG", True)

# The fallback key is for local development only; production must set it.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "django-insecure-axcenity-hub-development-key-not-for-production"
)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_tailwind_cli",
    "marketing",
    "documentation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.theme",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "axcenity-hub",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Cookies: Lax everywhere; Secure whenever DEBUG is off (production is HTTPS).
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# The colour-scheme cookie (config/theme.py) follows the same rule.
THEME_COOKIE_SECURE = not DEBUG

STATIC_URL = "static/"
# The docs snapshot's diagrams are served from /static/docs/images/ straight from the
# snapshot (documentation/content/images/), so there's one copy of each.
DOCS_SNAPSHOT_DIR = BASE_DIR / "documentation" / "content"
STATICFILES_DIRS = [BASE_DIR / "static", ("docs/images", DOCS_SNAPSHOT_DIR / "images")]

# The engine checkout `sync_engine_docs` copies the docs from (read-only to the Hub).
AXCENITY_ENGINE_DIR = Path(
    os.environ.get(
        "AXCENITY_ENGINE_DIR", Path.home() / "Documents" / "VSCode Projects" / "Axcenity-Engine"
    )
)

# Python's mimetypes may not know .ttf (it doesn't on Windows), so the static
# server would send the fonts as application/octet-stream.
mimetypes.add_type("font/ttf", ".ttf")

# Tailwind + DaisyUI through django-tailwind-cli's standalone binary (no Node).
# DaisyUI loads as the official plugin bundle, which the library downloads into
# .django_tailwind_cli/ (git-ignored) next to the CLI. The source CSS sits
# outside STATICFILES_DIRS; the build writes static/css/tailwind.css (git-ignored).
TAILWIND_CLI_USE_DAISY_UI = True
TAILWIND_CLI_DAISY_UI_SOURCE = "plugin"
TAILWIND_CLI_SRC_CSS = "styles/source.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
