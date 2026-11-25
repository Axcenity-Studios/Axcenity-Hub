"""Reporting a post or comment: a page with the form (verified members only).

The content is found before anything else runs: an unknown kind, a missing or hidden item,
or the member's own content is a 404 for everyone, so the URL reveals nothing.
"""

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.views.generic import FormView

from accounts.access import EmailNotVerified, VerifiedEmailRequiredMixin, verify_email_url

from . import services, strings
from .forms import ReportForm
from .targets import TARGETS


class ReportCreateView(VerifiedEmailRequiredMixin, FormView):
    form_class = ReportForm
    template_name = "reports/form.html"

    def dispatch(self, request, *args, **kwargs):
        self.target = TARGETS.get(kwargs["kind"])
        if self.target is None:
            raise Http404
        try:
            self.content = self.target.find(request.user, kwargs["pk"])
        except self.target.queryset().model.DoesNotExist:
            raise Http404 from None
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        label = self.target.label
        context = super().get_context_data(**kwargs)
        context.update(
            text=strings,
            heading=strings.TITLE.format(label=label),
            lede=strings.LEDE.format(label=label),
            content_title=self.target.title(self.content),
            back=strings.BACK.format(label=label),
            back_url=self.content.get_absolute_url(),
            already=(
                strings.ALREADY.format(label=label)
                if services.has_reported(self.request.user, self.content)
                else ""
            ),
        )
        return context

    def form_valid(self, form):
        label = self.target.label
        try:
            services.report_content(self.request.user, self.content, **form.cleaned_data)
        except EmailNotVerified:
            return HttpResponseRedirect(verify_email_url())
        except services.AlreadyReported:
            messages.info(self.request, strings.ALREADY.format(label=label))
        else:
            messages.success(self.request, strings.THANKS.format(label=label))
        return HttpResponseRedirect(self.content.get_absolute_url())
