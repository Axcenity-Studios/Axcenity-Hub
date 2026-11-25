"""The project pages' forms."""

from django import forms

from .models import Project, Role
from .strings import ROLES, STEPS

WORDS = STEPS["repository"]


class ProjectForm(forms.ModelForm):
    """A project's name and description (the model checks the name's rules)."""

    class Meta:
        model = Project
        fields = ["name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class DescriptionForm(forms.ModelForm):
    """The description alone: what a Maintainer may change (renaming is an Owner's)."""

    class Meta:
        model = Project
        fields = ["description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


ROLE_CHOICES = [(role.value, ROLES[role.value]) for role in Role]


class InviteForm(forms.Form):
    """Who to invite, by their Hub username, and in which role."""

    username = forms.CharField(
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false"}),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial=Role.VIEWER.value, label="Role")


class RoleForm(forms.Form):
    """A member's new role."""

    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Role")


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
