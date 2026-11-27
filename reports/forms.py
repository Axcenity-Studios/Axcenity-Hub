"""The report form: why, and optional details (required for "Something else")."""

from django import forms

from . import strings
from .models import BugActivity, BugReport, Report


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        labels = {"reason": strings.REASON_LABEL, "details": strings.DETAILS_LABEL}
        help_texts = {"details": strings.DETAILS_HELP}
        widgets = {
            "reason": forms.RadioSelect,
            "details": forms.Textarea(attrs={"rows": 5}),
        }
        error_messages = {
            "reason": {
                "required": strings.REASON_REQUIRED,
                "invalid_choice": strings.REASON_REQUIRED,
            },
            "details": {"max_length": strings.DETAILS_TOO_LONG},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A radio list, with no empty "---------" choice.
        self.fields["reason"].choices = Report.Reason.choices

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("reason") == Report.Reason.OTHER and not cleaned.get("details"):
            self.add_error("details", strings.DETAILS_REQUIRED)
        return cleaned


# ---------- Bug reports and feedback ----------

ENGINE = "engine"  # the "About" choice for the Axcenity Engine itself


class BugReportForm(forms.ModelForm):
    """A bug report or feedback. `about` is the engine or one of the member's projects (by
    slug); anything else is refused. The model's `clean` holds the rules for each kind."""

    about = forms.ChoiceField(
        label=strings.BUG_FORM_PROJECT,
        help_text=strings.BUG_FORM_PROJECT_HELP,
        error_messages={
            "required": strings.BUG_FORM_PROJECT_INVALID,
            "invalid_choice": strings.BUG_FORM_PROJECT_INVALID,
        },
    )

    class Meta:
        model = BugReport
        fields = ["kind", "title", "description", "steps", "expected", "engine_version", "platform"]
        labels = {
            "kind": strings.BUG_FORM_KIND,
            "title": strings.BUG_FORM_TITLE,
            "description": strings.BUG_FORM_DESCRIPTION,
            "steps": strings.BUG_FORM_STEPS,
            "expected": strings.BUG_FORM_EXPECTED,
            "engine_version": strings.BUG_FORM_VERSION,
            "platform": strings.BUG_FORM_PLATFORM,
        }
        help_texts = {
            "title": strings.BUG_FORM_TITLE_HELP,
            "description": strings.BUG_FORM_DESCRIPTION_HELP,
            "steps": strings.BUG_FORM_STEPS_HELP,
            "expected": strings.BUG_FORM_EXPECTED_HELP,
            "engine_version": strings.BUG_FORM_VERSION_HELP,
            "platform": strings.BUG_FORM_PLATFORM_HELP,
        }
        widgets = {
            "kind": forms.RadioSelect,
            "description": forms.Textarea(attrs={"rows": 5}),
            "steps": forms.Textarea(attrs={"rows": 5}),
            "expected": forms.Textarea(attrs={"rows": 3}),
            "engine_version": forms.TextInput(attrs={"placeholder": "0.4.0-alpha.2"}),
        }
        error_messages = {
            name: {"max_length": strings.BUG_TOO_LONG}
            for name in ("steps", "expected", "engine_version")
        } | {
            "title": {"max_length": strings.BUG_TOO_LONG, "required": strings.BUG_TITLE_REQUIRED},
            "description": {
                "max_length": strings.BUG_TOO_LONG,
                "required": strings.BUG_DESCRIPTION_REQUIRED,
            },
            "kind": {
                "invalid_choice": strings.BUG_KIND_INVALID,
                "required": strings.BUG_KIND_INVALID,
            },
            "platform": {"invalid_choice": strings.BUG_PLATFORM_REQUIRED},
        }

    field_order = ["about", "kind", "title", "description", "steps", "expected"]

    def __init__(self, *args, projects=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.projects = {project.slug: project for project in projects}
        self.fields["about"].choices = [(ENGINE, strings.ENGINE)] + [
            (slug, project.name) for slug, project in self.projects.items()
        ]
        self.fields["kind"].choices = BugReport.Kind.choices
        self.fields["platform"].choices = [("", strings.BUG_FORM_PLATFORM_EMPTY)] + list(
            BugReport.Platform.choices
        )

    def clean_about(self):
        about = self.cleaned_data["about"]
        return None if about == ENGINE else self.projects[about]

    def report_fields(self) -> dict:
        """The cleaned values as `bugs.submit` takes them."""
        data = {name: self.cleaned_data.get(name, "") for name in self.Meta.fields}
        return {"project": self.cleaned_data["about"], **data}


class BugStatusForm(forms.Form):
    """A status change. Any value is passed on: bugs.change_status decides."""

    status = forms.CharField(max_length=20, required=False)


class BugAssignForm(forms.Form):
    """An assignment: a member's id, or empty for nobody. bugs.assign decides who may be."""

    assignee = forms.CharField(max_length=20, required=False)


class BugCommentForm(forms.Form):
    body = forms.CharField(
        label=strings.BUG_COMMENT_LABEL,
        help_text=strings.BUG_COMMENT_HELP,
        max_length=BugActivity.COMMENT_MAX,
        widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={
            "required": strings.BUG_COMMENT_REQUIRED,
            "max_length": strings.BUG_TOO_LONG,
        },
    )
