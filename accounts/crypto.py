"""Encryption at rest for secrets the Hub must keep, such as members' GitHub tokens.

Fernet (AES-128-CBC with an HMAC-SHA256 tag) with keys from the environment only
(`settings.GITHUB_TOKEN_KEYS`, read on every call so tests and rotation see the current
value). The first key encrypts; every key decrypts, so a new key goes first and an old one
stays listed until every row is re-encrypted. Nothing here logs a value or puts one in an
exception message.
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings


class KeyMissing(RuntimeError):
    """No encryption key is configured (GITHUB_TOKEN_KEYS is empty)."""


class Unreadable(ValueError):
    """A stored value can't be decrypted with any configured key (or isn't ciphertext)."""


def is_configured() -> bool:
    """Whether at least one key is set."""
    return bool(settings.GITHUB_TOKEN_KEYS)


def _cipher() -> MultiFernet:
    keys = list(settings.GITHUB_TOKEN_KEYS)
    if not keys:
        raise KeyMissing("GITHUB_TOKEN_KEYS is not set")
    try:
        return MultiFernet([Fernet(key) for key in keys])
    except (ValueError, TypeError):
        # Fernet's own message never contains the key, but say nothing about it either way.
        raise KeyMissing("GITHUB_TOKEN_KEYS holds a key that isn't a Fernet key") from None


def encrypt(plain: str) -> str:
    """Encrypt `plain` with the first configured key; returns ASCII ciphertext."""
    return _cipher().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(stored: str) -> str:
    """Decrypt a value `encrypt` produced, with whichever configured key made it."""
    try:
        return _cipher().decrypt(stored.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError):
        raise Unreadable("the stored value can't be decrypted with the configured keys") from None
