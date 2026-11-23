"""Template context shared by every page."""

from django.http import HttpRequest

from config.theme import THEME_LABELS, next_theme, theme_choice


def theme(request: HttpRequest) -> dict[str, str]:
    """The validated colour-scheme choice, for <html> and the nav's theme switch."""
    choice = theme_choice(request)
    following = next_theme(choice)
    return {
        "theme_choice": choice,
        "theme_label": THEME_LABELS[choice],
        "theme_next": following,
        "theme_next_label": THEME_LABELS[following],
    }
