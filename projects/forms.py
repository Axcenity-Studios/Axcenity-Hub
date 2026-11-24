"""The project pages' forms."""

from django import forms

from .models import Project


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
        label="GitHub repository",
        help_text="owner/name, or the repository's github.com address. You must be an admin of it.",
        widget=forms.TextInput(
            attrs={"placeholder": "owner/name", "autocomplete": "off", "spellcheck": "false"}
        ),
    )
