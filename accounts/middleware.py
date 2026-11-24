"""Session lifetimes: an idle limit and an absolute limit, both enforced on the server.

The cookie's own expiry is only advice to the browser. This middleware records when a
signed-in session began and when it was last used, and signs it out (deleting the
session on the server) once either settings.SESSION_IDLE_TIMEOUT passes without a
request or settings.SESSION_ABSOLUTE_TIMEOUT passes since sign-in.
"""

import time

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

SIGNED_IN_AT = "ax_signed_in_at"
LAST_SEEN_AT = "ax_last_seen_at"
# Write the last-seen time at most this often, so a busy page doesn't save the session
# on every request. The idle limit is a day, so a minute's slack doesn't matter.
LAST_SEEN_RESOLUTION = 60


@receiver(user_logged_in)
def stamp_sign_in(sender, request, user, **kwargs) -> None:
    """Start both clocks at sign-in (Django has just given the session a new key)."""
    if request is not None and hasattr(request, "session"):
        now = time.time()
        request.session[SIGNED_IN_AT] = now
        request.session[LAST_SEEN_AT] = now


class SessionAgeMiddleware:
    """Signs out a session that has been idle too long or has lived too long."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = time.time()
            session = request.session
            # A session from before this middleware existed starts its clocks now.
            signed_in = session.setdefault(SIGNED_IN_AT, now)
            last_seen = session.setdefault(LAST_SEEN_AT, now)
            idle = settings.SESSION_IDLE_TIMEOUT.total_seconds()
            absolute = settings.SESSION_ABSOLUTE_TIMEOUT.total_seconds()
            if now - last_seen > idle or now - signed_in > absolute:
                logout(request)  # flushes the session server-side
            elif now - last_seen >= LAST_SEEN_RESOLUTION:
                session[LAST_SEEN_AT] = now
        return self.get_response(request)
