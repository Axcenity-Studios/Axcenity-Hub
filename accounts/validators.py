"""Username rules (settings.ACCOUNT_USERNAME_VALIDATORS)."""

from django.core.validators import MaxLengthValidator, RegexValidator

USERNAME_MAX = 30

USERNAME_VALIDATORS = [
    RegexValidator(
        r"\A[A-Za-z0-9_-]+\Z",
        "Use only letters, digits, hyphens (-) and underscores (_).",
        code="invalid_username",
    ),
    MaxLengthValidator(USERNAME_MAX),
]
