"""Cloudflare Turnstile: a check that a person, not a script, sent a form.

It supplements the server-side protections (the honeypot and the rate limits) and never
replaces them: those run whatever Turnstile says. It's on when both keys are set
(TURNSTILE_SITE_KEY, TURNSTILE_SECRET_KEY, from the environment) and off otherwise, as
in development by default. When it's on, it fails closed: a missing, refused or
unverifiable token (Cloudflare down, a timeout, a bad reply) refuses the form.
"""

import requests
from django.conf import settings

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js"
# The form field Cloudflare's widget fills in.
RESPONSE_FIELD = "cf-turnstile-response"
# Cloudflare's documented maximum token length.
MAX_TOKEN_LENGTH = 2048
TIMEOUT = 5  # seconds


def is_enabled() -> bool:
    """True when both Turnstile keys are configured."""
    return bool(settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY)


def verify(token: str, remote_ip: str = "") -> bool:
    """Ask Cloudflare whether `token` is a valid, unused Turnstile response.

    False for an empty or over-long token and for any failure to get a clear yes
    (network errors, timeouts, non-200 replies, malformed JSON): it fails closed.
    """
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return False
    data = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        response = requests.post(SITEVERIFY_URL, data=data, timeout=TIMEOUT)
        if response.status_code != 200:
            return False
        return response.json().get("success") is True
    except (requests.RequestException, ValueError, AttributeError):
        return False
