"""The showcase form: its words, its image and its tags."""

from django import forms

from . import images, strings
from .models import Showcase, Tag

ACCEPT = "image/png,image/jpeg,image/webp"


def _trimmed(**kwargs) -> forms.CharField:
    return forms.CharField(strip=True, **kwargs)


class ShowcaseForm(forms.Form):
    """A showcase's title, description, image, image description and tags.

    The image is checked and remade here (showcases.images), so the cleaned `image` is an
    `images.Processed` (or None when editing without a new one), and an image that won't
    decode is a form error, never a failed save. The cleaned `tags` is a list of names. The
    image is required when publishing, optional when editing. The services check the rest
    again (`full_clean`).
    """

    title = _trimmed(
        label=strings.TITLE_LABEL,
        help_text=strings.TITLE_HELP,
        max_length=Showcase.TITLE_MAX,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
        error_messages={"required": strings.TITLE_REQUIRED, "max_length": strings.TITLE_TOO_LONG},
    )
    image = forms.FileField(
        label=strings.IMAGE_LABEL,
        help_text=strings.IMAGE_HELP,
        widget=forms.FileInput(attrs={"accept": ACCEPT}),
        error_messages={"required": strings.IMAGE_REQUIRED},
    )
    image_alt = _trimmed(
        label=strings.ALT_LABEL,
        help_text=strings.ALT_HELP,
        max_length=Showcase.ALT_MAX,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
        error_messages={"max_length": strings.ALT_TOO_LONG},
    )
    description = _trimmed(
        label=strings.DESCRIPTION_LABEL,
        help_text=strings.DESCRIPTION_HELP,
        max_length=Showcase.DESCRIPTION_MAX,
        widget=forms.Textarea(attrs={"rows": 8}),
        error_messages={
            "required": strings.DESCRIPTION_REQUIRED,
            "max_length": strings.DESCRIPTION_TOO_LONG,
        },
    )
    tags = _trimmed(
        label=strings.TAGS_FIELD_LABEL,
        help_text=strings.TAGS_HELP,
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )

    def __init__(self, *args, editing: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        if editing:
            self.fields["image"].required = False
            self.fields["image"].help_text = strings.IMAGE_HELP_EDIT

    @classmethod
    def initial_for(cls, showcase: Showcase) -> dict:
        """The form's values for editing `showcase`."""
        return {
            "title": showcase.title,
            "description": showcase.description,
            "image_alt": showcase.image_alt,
            "tags": ", ".join(tag.name for tag in showcase.tags.all()),
        }

    def clean_image(self) -> images.Processed | None:
        upload = self.cleaned_data.get("image")
        if not upload:
            return None
        images.check(upload)
        return images.process(upload)

    def clean_tags(self) -> list[str]:
        return Tag.parse(self.cleaned_data.get("tags", ""))
