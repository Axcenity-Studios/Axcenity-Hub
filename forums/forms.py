"""The forum's form: a post's title and body."""

from django import forms

from . import strings
from .models import ForumPost


class PostForm(forms.ModelForm):
    """A post's title and body (leading and trailing spaces dropped; blank is refused)."""

    class Meta:
        model = ForumPost
        fields = ["title", "body"]
        labels = {"title": strings.TITLE_LABEL, "body": strings.BODY_LABEL}
        help_texts = {"title": strings.TITLE_HELP, "body": strings.BODY_HELP}
        widgets = {
            "title": forms.TextInput(attrs={"autocomplete": "off"}),
            "body": forms.Textarea(attrs={"rows": 10}),
        }
        error_messages = {
            "title": {"required": strings.TITLE_REQUIRED, "max_length": strings.TITLE_TOO_LONG},
            "body": {"required": strings.BODY_REQUIRED, "max_length": strings.BODY_TOO_LONG},
        }
