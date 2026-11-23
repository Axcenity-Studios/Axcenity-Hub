"""Template tags for the Home's drawn media (templates/marketing/media/)."""

from django import template

from marketing import content, drawings

register = template.Library()


@register.simple_tag
def terrain_drawing() -> drawings.TerrainDrawing:
    """The terrain loop's fallback drawing: its wireframe geometry."""
    return drawings.terrain_wireframe()


@register.filter
def luau_lines(source: str) -> list[list[tuple[str, str]]]:
    """Luau source as lines of (kind, text) tokens."""
    return drawings.luau_lines(source)


@register.filter
def display_sizes(media: content.Media, slot: str) -> str:
    """The `sizes` attribute for a media item in one slot ("inline", "stage", "hero")."""
    return media.display[slot].sizes
