"""Template tags for the site's shells (templates/base.html)."""

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def versioned_static(path: str) -> str:
    """The static URL for `path` with `?v=<when it last changed>`.

    A stylesheet or script keeps one URL, so a browser could go on using a
    cached copy after it changes. The version makes every change a new URL.
    A file the finders can't see gets its plain static URL.
    """
    url = static(path)
    found = finders.find(path)
    if not found:
        return url
    return f"{url}?v={int(os.path.getmtime(found))}"
