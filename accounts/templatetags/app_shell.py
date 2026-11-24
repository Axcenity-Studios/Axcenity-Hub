"""The app shell's rail (templates/app/shell.html)."""

from django import template
from django.urls import reverse

from accounts import strings

register = template.Library()


def rail_key(view_name: str) -> str:
    """The rail item a view belongs to: allauth's two-factor pages all go under Two-factor."""
    if view_name in strings.RAIL_PAGES:
        return strings.RAIL_PAGES[view_name]
    namespace = view_name.split(":", 1)[0] if ":" in view_name else ""
    if namespace in strings.RAIL_NAMESPACES:
        return strings.RAIL_NAMESPACES[namespace]
    return "two_factor" if view_name.startswith("mfa_") else ""


@register.simple_tag(takes_context=True)
def app_rail(context) -> list[dict]:
    """The rail's sections (Hub, then Account): each a heading and its items, each item with
    its URL and whether it's the current page."""
    request = context.get("request")
    match = getattr(request, "resolver_match", None)
    current = rail_key(match.view_name) if match else ""
    return [
        {
            "heading": heading,
            "items": [
                {
                    "key": key,
                    "label": label,
                    "href": reverse(name),
                    "icon": icon,
                    "current": key == current,
                }
                for key, label, name, icon in items
            ],
        }
        for heading, items in [
            (strings.RAIL_HUB_HEADING, strings.RAIL_HUB),
            (strings.RAIL_HEADING, strings.RAIL_ACCOUNT),
        ]
    ]


@register.simple_tag
def account_copy():
    """The account pages' copy (accounts/strings.py), for templates: {% account_copy as copy %}."""
    return strings
