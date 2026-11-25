"""The report form: why, and optional details (required for "Something else")."""

from django import forms

from . import strings
from .models import Report


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
