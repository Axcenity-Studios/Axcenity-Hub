"""Template tags for the Home's drawn media (templates/marketing/media/)."""

from django import template

from marketing import drawings

register = template.Library()


@register.simple_tag
def terrain_drawing() -> drawings.TerrainDrawing:
    """The terrain wireframe stand-in's geometry."""
    return drawings.terrain_wireframe()


@register.filter
def luau_lines(source: str) -> list[list[tuple[str, str]]]:
    """Luau source as lines of (kind, text) tokens."""
    return drawings.luau_lines(source)
