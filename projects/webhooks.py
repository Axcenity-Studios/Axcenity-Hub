"""Repository webhooks: each link's secret, verifying a delivery, and applying its event.

The OAuth App has no scopes, so the Hub can't create webhooks (`admin:repo_hook`): the owner
adds one in the repository's settings, with the payload URL and secret the project page shows
after confirming they're an admin of the repository on GitHub.

**One secret per link.** `GITHUB_WEBHOOK_SECRET` (the environment) is the root; a link's
secret is HMAC-SHA256(root, its random `hook_id`), and its payload URL carries the `hook_id`.
Nothing secret is stored, no owner sees the root, and one repository's secret can't sign
another's deliveries.

**Verification before anything is parsed:** the raw body's HMAC-SHA256 with the link's
secret must equal `X-Hub-Signature-256` (`sha256=<hex>`), compared in constant time. A
delivery is accepted once per link: `X-GitHub-Delivery` and the body's SHA-256 are each
unique per link (WebhookDelivery), since GitHub doesn't sign the delivery header.
"""

import hashlib
import hmac
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse

from . import github
from .models import RepositoryLink, WebhookDelivery

SIGNATURE_PREFIX = "sha256="


def webhooks_on() -> bool:
    """Whether this server accepts repository webhooks (the root secret is set)."""
    return bool(settings.GITHUB_WEBHOOK_SECRET)


def secret_for(hook_id: uuid.UUID | str) -> str:
    """The webhook secret for one link, derived from the root secret and its hook id."""
    if not webhooks_on():
        raise RuntimeError("GITHUB_WEBHOOK_SECRET isn't set")
    message = f"axcenity-hub:repository-webhook:{hook_id}".encode()
    return hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode(), message, hashlib.sha256).hexdigest()


def payload_path(hook_id: uuid.UUID | str) -> str:
    """The webhook's path on the Hub (the page shows it on the site's own origin)."""
    return reverse("projects:webhook", kwargs={"hook_id": hook_id})


def signature(secret: str, body: bytes) -> str:
    """GitHub's X-Hub-Signature-256 value for `body` signed with `secret`."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return SIGNATURE_PREFIX + digest


# ---------- Receiving a delivery ----------

EVENT_RE = re.compile(r"^[a-z_]{1,64}$")
DELIVERY_RE = re.compile(r"^[0-9A-Fa-f-]{1,64}$")
# Repository events that leave the repository in place (anything but "deleted").
DETAIL_FIELDS = (
    "full_name", "html_url", "description", "default_branch", "private", "archived", "pushed_at"
)  # fmt: skip


@dataclass(frozen=True)
class Outcome:
    """The HTTP status the webhook answers with, and a short plain-text reason."""

    status: int
    text: str


ACCEPTED = Outcome(200, "ok")
IGNORED = Outcome(202, "ignored")
UNSIGNED = Outcome(403, "signature missing or invalid")
REPLAYED = Outcome(409, "delivery already received")
MALFORMED = Outcome(400, "malformed delivery")


HEX_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class Refused(Exception):
    """A delivery that must change nothing (raised inside its transaction to roll it back)."""

    def __init__(self, outcome: Outcome):
        super().__init__(outcome.text)
        self.outcome = outcome


def verify(secret: str, body: bytes, header: str) -> bool:
    """Whether `header` (X-Hub-Signature-256) is `body`'s signature with `secret`.

    Only `sha256=` and 64 lower-case hex digits are considered; the comparison is constant
    time (hmac.compare_digest), so it leaks nothing about how much of a forgery matched.
    """
    if not isinstance(header, str) or not header.startswith(SIGNATURE_PREFIX):
        return False
    if not HEX_DIGEST_RE.match(header.removeprefix(SIGNATURE_PREFIX)):
        return False
    return hmac.compare_digest(signature(secret, body).encode(), header.encode())


def receive(link: RepositoryLink, *, body: bytes, headers, now: datetime) -> Outcome:
    """Verify one delivery for `link`, refuse replays, and apply its event.

    `headers` is the request's headers (case-insensitive). The signature is checked before
    any header or the body is read. A refused delivery changes nothing.
    """
    if not verify(secret_for(link.hook_id), body, headers.get("X-Hub-Signature-256", "")):
        return UNSIGNED
    event = headers.get("X-GitHub-Event", "")
    delivery_id = headers.get("X-GitHub-Delivery", "")
    if not EVENT_RE.match(event) or not DELIVERY_RE.match(delivery_id):
        return MALFORMED
    try:
        payload = json.loads(body)
    except ValueError:
        return MALFORMED
    if not isinstance(payload, dict):
        return MALFORMED
    try:
        with transaction.atomic():
            try:
                with transaction.atomic():
                    WebhookDelivery.objects.create(
                        link=link,
                        delivery_id=delivery_id,
                        body_sha256=hashlib.sha256(body).hexdigest(),
                        event=event,
                        received_at=now,
                    )
            except IntegrityError:  # this link has had this delivery id or this body
                raise Refused(REPLAYED) from None
            outcome = _apply(link, event, payload)
            if outcome is MALFORMED:
                raise Refused(MALFORMED)
            link.webhook_at = now
            link.first_webhook_at = link.first_webhook_at or now
            link.save()
    except Refused as refused:
        link.refresh_from_db()
        return refused.outcome
    return outcome


def _apply(link: RepositoryLink, event: str, payload: dict) -> Outcome:
    if event == "ping":
        return ACCEPTED
    if event not in ("repository", "push"):
        return IGNORED
    repository = payload.get("repository")
    if not isinstance(repository, dict) or repository.get("id") != link.github_id:
        return IGNORED  # about another repository: never applied to this link
    if event == "repository" and payload.get("action") == "deleted":
        link.deleted_on_github = True
        return ACCEPTED
    details = github.parse_details(repository)
    if details is None:
        return MALFORMED
    for field in DETAIL_FIELDS:
        if field == "pushed_at" and details[field] is None:
            continue
        setattr(link, field, details[field])
    return ACCEPTED
