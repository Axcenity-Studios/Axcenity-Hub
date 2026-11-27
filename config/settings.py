"""Django settings for Axcenity Hub.

Development defaults live here. Secrets and anything that differs in
production come from environment variables only. Production is DEBUG off
(`DJANGO_DEBUG=false`): it refuses to start without a real secret key and
allowed hosts, and turns on HTTPS, HSTS and a shared cache (see
docs/architecture/accounts.md). Never put a real secret in this file.
"""

import mimetypes
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    """Read a true/false environment variable ("1", "true", "yes", "on" are true)."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable as a list, skipping blanks."""
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)
PRODUCTION = not DEBUG

# The fallback key is for local development only; production must set its own.
DEVELOPMENT_SECRET_KEY = "django-insecure-axcenity-hub-development-key-not-for-production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "" if PRODUCTION else DEVELOPMENT_SECRET_KEY)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "" if PRODUCTION else "localhost,127.0.0.1")

# The Hub's address on the internet, as GitHub must reach it (https://hub.example.com, or a
# tunnel's address in development). Webhook payload URLs are built on it, and its host is
# allowed. Unset, they're built on the address the page was opened at.
HUB_PUBLIC_URL = os.environ.get("HUB_PUBLIC_URL", "").strip().rstrip("/")
if HUB_PUBLIC_URL:
    _public = urlsplit(HUB_PUBLIC_URL)
    if _public.scheme not in ("http", "https") or not _public.hostname or _public.path:
        raise ImproperlyConfigured(
            "HUB_PUBLIC_URL must be a scheme and host only, such as https://hub.example.com"
        )
    if _public.hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_public.hostname)

if PRODUCTION:
    # The same rules as `check --deploy`'s security.W009: long, varied, not a default.
    if (
        len(SECRET_KEY) < 50
        or len(set(SECRET_KEY)) < 5
        or SECRET_KEY.startswith("django-insecure-")
    ):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a random value of 50+ characters in production"
        )
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_tailwind_cli",
    "django_htmx",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.github",
    "marketing",
    "documentation",
    "accounts",
    "projects",
    "forums",
    "showcases",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.errors.ErrorPageMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.SessionAgeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",  # request.htmx
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
        # Every transaction takes SQLite's write lock when it begins, so a count-then-insert
        # limit (accounts.limits.lock_member) is serialized; PostgreSQL locks the member's row.
        "OPTIONS": {"transaction_mode": "IMMEDIATE"},
        # Tests use a file too (one per test process), not SQLite's shared in-memory
        # database: that one fails a waiting writer at once ("database table is locked")
        # instead of queueing it, so it can't show the lock above working.
        "TEST": {
            "NAME": str(Path(tempfile.gettempdir()) / f"axcenity-hub-test-{os.getpid()}.sqlite3")
        },
    }
}

# Local memory in development. Production shares one cache between every process, so the
# release list, its backoff and allauth's rate limits are the same for every worker: the
# database cache by default (run `manage.py createcachetable` once), or Redis when
# DJANGO_REDIS_URL is set (needs the redis package).
if not PRODUCTION:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "axcenity-hub",
        }
    }
elif os.environ.get("DJANGO_REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.environ["DJANGO_REDIS_URL"],
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "axcenity_cache",
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

# ---------- Sessions and cookies ----------
# Lax everywhere; Secure whenever DEBUG is off (production is HTTPS only). The session
# cookie is HttpOnly. A session ends after a day without a request (idle) and two weeks
# after sign-in whatever happens (absolute): accounts.middleware.SessionAgeMiddleware.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
SESSION_IDLE_TIMEOUT = timedelta(hours=24)
SESSION_ABSOLUTE_TIMEOUT = timedelta(days=14)
SESSION_COOKIE_AGE = int(SESSION_ABSOLUTE_TIMEOUT.total_seconds())
# The colour-scheme cookie (config/theme.py) follows the same rule.
THEME_COOKIE_SECURE = PRODUCTION

# ---------- HTTPS and headers ----------
# Django's defaults, written out so they're documented and tested: no framing, no MIME
# sniffing, the referrer only to this site, and the opener isolated.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
# Origins whose form posts pass the CSRF check besides the page's own. The Hub's public
# address is one: behind a tunnel or a TLS proxy the browser posts from https://<host> while
# Django sees plain http, so without it every sign-in through that address is refused.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
# A refused form gets the Hub's own page (config/errors.py), not Django's.
CSRF_FAILURE_VIEW = "config.errors.csrf_failure"
if HUB_PUBLIC_URL and HUB_PUBLIC_URL not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(HUB_PUBLIC_URL)
if PRODUCTION:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 365 * 24 * 60 * 60
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Behind a TLS-terminating proxy that sets X-Forwarded-Proto (and only then).
    if env_bool("DJANGO_BEHIND_PROXY", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
        ALLAUTH_TRUSTED_PROXY_COUNT = int(os.environ.get("DJANGO_TRUSTED_PROXY_COUNT", "1"))

# ---------- Sign-in (django-allauth) ----------
# The policy and the reasons behind each setting: docs/architecture/accounts.md.
AUTHENTICATION_BACKENDS = [
    # The admin's own login form (username and password).
    "django.contrib.auth.backends.ModelBackend",
    # The Hub's sign-in (email and password, then two-factor when enrolled).
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "accounts:profile"
ACCOUNT_LOGOUT_REDIRECT_URL = "marketing:home"

ACCOUNT_ADAPTER = "accounts.adapter.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
# Mandatory at signup (enumeration-safe and email-unique); a password login by an
# unverified account is allowed (accounts.stages), and accounts.access gates contributions.
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Axcenity Hub] "
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_USERNAME_VALIDATORS = "accounts.validators.USERNAME_VALIDATORS"
ACCOUNT_USERNAME_BLACKLIST = [
    "admin", "administrator", "axcenity", "hub", "mod", "moderator", "root", "staff",
    "support", "system",
]  # fmt: skip
ACCOUNT_SIGNUP_FORM_HONEYPOT_FIELD = "website"
ACCOUNT_FORMS = {
    "login": "accounts.forms.LoginForm",
    "signup": "accounts.forms.SignupForm",
    "reset_password": "accounts.forms.ResetPasswordForm",
}
# The cache layer of the rate limits ("ip" per address, "key" per account, "user" per
# signed-in member). The database backstop behind it: accounts.throttle.LIMITS.
ACCOUNT_RATE_LIMITS = {
    "login": "30/m/ip",
    "login_failed": "10/m/ip,5/5m/key",
    "signup": "10/h/ip",
    "reset_password": "10/h/ip,3/h/key",
    "reset_password_from_key": "20/m/ip",
    "change_password": "5/m/user",
    "reauthenticate": "10/m/user",
    "manage_email": "10/m/user",
    "confirm_email": "1/3m/key",
}
# Password reset links last an hour, and die with any password change (Django's tokens).
PASSWORD_RESET_TIMEOUT = 60 * 60

# Two-factor sign-in: an authenticator app (TOTP) and one-time recovery codes.
MFA_ADAPTER = "accounts.adapter.MFAAdapter"
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Axcenity Hub"
MFA_RECOVERY_CODE_COUNT = 10
MFA_FORMS = {
    "authenticate": "accounts.forms.MFAAuthenticateForm",
    "reauthenticate": "accounts.forms.MFAReauthenticateForm",
}

# ---------- GitHub account linking (allauth.socialaccount) ----------
# GitHub is an account a member links, never a way to sign in (accounts.adapter
# .SocialAccountAdapter). An OAuth App with no scopes: public data only. Its id and secret
# come from the environment, never the database (SocialApp rows and their admin are unused).
# Access and refresh tokens are stored by the Hub, encrypted with GITHUB_TOKEN_KEYS
# (accounts.models.GitHubLink); allauth's own plain-text token table stays empty.
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
# Fernet keys, comma-separated: the first encrypts, every one decrypts (for rotation).
GITHUB_TOKEN_KEYS = env_list("GITHUB_TOKEN_KEYS")
if (GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET) and not GITHUB_TOKEN_KEYS and PRODUCTION:
    raise ImproperlyConfigured("GITHUB_TOKEN_KEYS must be set when GitHub linking is configured")
for _key in GITHUB_TOKEN_KEYS:
    try:
        Fernet(_key)
    except (ValueError, TypeError):
        # Never echo the value: it's a secret, even when malformed.
        raise ImproperlyConfigured(
            "GITHUB_TOKEN_KEYS holds a value that isn't a Fernet key"
        ) from None
SOCIALACCOUNT_ADAPTER = "accounts.adapter.SocialAccountAdapter"
SOCIALACCOUNT_PROVIDERS = {
    "github": {
        "SCOPE": [],
        "APPS": (
            [{"client_id": GITHUB_CLIENT_ID, "secret": GITHUB_CLIENT_SECRET, "key": ""}]
            if GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET
            else []
        ),
    }
}
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_QUERY_EMAIL = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_LOGIN_ON_GET = False
# Connecting needs no fresh re-authentication (allauth's would park the new token, in plain
# text, in the session); unlinking does (accounts.views.ConnectionsView).
SOCIALACCOUNT_REAUTHENTICATION_REQUIRED = False
# How long a successful check of a link's token stands before GitHub is asked again.
GITHUB_LINK_CHECK_INTERVAL = timedelta(minutes=15)

# ---------- Projects and repositories (projects.github, projects.webhooks) ----------
# The root secret for repository webhooks: each linked repository's own secret is derived
# from it and the link's random hook id, so no owner ever sees this value. Webhooks are off
# (their URL is a 404) while it's unset.
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
# How long a member's repository permission, as GitHub reported it, may be reused. Never
# longer: a revoked permission stops working within this time.
GITHUB_PERMISSION_TTL = timedelta(seconds=60)
# GitHub requests the Hub makes for one member in an hour, at most (a courtesy budget on
# top of GitHub's own rate limit).
GITHUB_CALLS_PER_MEMBER_PER_HOUR = 60
# Linked repositories' details older than this are fetched again when the project is viewed.
GITHUB_REPOSITORY_REFRESH = timedelta(hours=1)

# Cloudflare Turnstile on sign-up and the reset request (accounts.turnstile): on only when
# both keys are set. Cloudflare's test keys work on localhost (docs/architecture/accounts.md).
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

# ---------- Email ----------
# The console in development: accounts.mail prints each email decoded where runserver
# runs, its links whole and clickable. Django's test runner swaps every mailer for
# locmem. Production sends through SMTP, configured from the environment, until a
# provider (django-anymail) arrives with the domain.
if PRODUCTION:
    MAILERS = {
        "default": {
            "BACKEND": os.environ.get(
                "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
            ),
            "OPTIONS": {
                "host": os.environ.get("DJANGO_EMAIL_HOST", "localhost"),
                "port": int(os.environ.get("DJANGO_EMAIL_PORT", "587")),
                "username": os.environ.get("DJANGO_EMAIL_HOST_USER", ""),
                "password": os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", ""),
                "use_tls": env_bool("DJANGO_EMAIL_USE_TLS", True),
                "timeout": 10,
            },
        }
    }
else:
    MAILERS = {
        "default": {"BACKEND": os.environ.get("DJANGO_EMAIL_BACKEND", "accounts.mail.EmailBackend")}
    }
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "Axcenity Hub <noreply@localhost>")

STATIC_URL = "static/"

# Members' uploads (profile photos, accounts.avatars). The development server serves them
# (config/urls.py); in production the web server serves MEDIA_ROOT at /media/.
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))
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
