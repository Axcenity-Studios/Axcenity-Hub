"""The project pages' forms."""

from django import forms

from .models import Project
from .strings import STEPS

WORDS = STEPS["repository"]


class ProjectForm(forms.ModelForm):
    """A project's name and description (the model checks the name's rules)."""

    class Meta:
        model = Project
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class LinkRepositoryForm(forms.Form):
    """The repository to link, as owner/name or its GitHub address."""

    repository = forms.CharField(
        max_length=200,
        label=WORDS["field"],
        help_text=WORDS["help"],
        widget=forms.TextInput(
            attrs={
                "placeholder": WORDS["placeholder"],
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
    )
