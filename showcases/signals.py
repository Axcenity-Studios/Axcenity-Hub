"""Signal receivers for showcases."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Showcase


@receiver(post_delete, sender=Showcase)
def delete_images(sender, instance: Showcase, **kwargs) -> None:
    """A deleted showcase (or its author's account) takes its image files with it."""
    for field in (instance.image, instance.card):
        if field:
            field.storage.delete(field.name)
