"""Reporting a post, comment or showcase (verified members only), and bug reports and
feedback: the list, sending one, its page and handling it.

Content and reports are found before anything else runs: an unknown kind, a missing or
hidden item, the member's own content, or a report the caller can't see is a 404 for
everyone, so the URL reveals nothing.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import FormView, TemplateView

from accounts.access import EmailNotVerified, VerifiedEmailRequiredMixin, verify_email_url
from accounts.limits import LimitReached
from config.listing import ListingMixin
from forums.views import count_words, mark_invalid, person

from . import bugs, services, strings
from .forms import BugAssignForm, BugCommentForm, BugReportForm, BugStatusForm, ReportForm
from .listing import for_member
from .models import BugActivity, BugReport
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


# ---------- Bug reports and feedback ----------
#
# A report is found before anything else runs (sign-in, verification): a report the caller
# can't see, or can't handle for the handling actions, is a 404 for everyone, signed out
# included, as for one that doesn't exist (reports.bugs).


def bug_row(report: BugReport, user) -> dict:
    """One report as the list shows it."""
    return {
        "report": report,
        "submitter": person(report.submitter) if report.submitter else None,
        "assignee": person(report.assignee) if report.assignee else None,
        "yours": report.submitter_id == user.pk,
    }


def activity_row(entry: BugActivity) -> dict:
    """One timeline entry: who, when, and what they did or said."""
    if entry.kind == BugActivity.Kind.STATUS:
        what = strings.BUG_ACTIVITY_STATUS.format(
            old=entry.get_old_status_display(), new=entry.get_new_status_display()
        )
    elif entry.kind == BugActivity.Kind.ASSIGNED:
        what = (
            strings.BUG_ACTIVITY_ASSIGNED.format(name=person(entry.assignee)["name"])
            if entry.assignee
            else strings.BUG_ACTIVITY_UNASSIGNED
        )
    else:
        what = ""
    return {
        "entry": entry,
        "actor": person(entry.actor) if entry.actor else None,
        "what": what,
    }


class BugLookupMixin:
    """The report named by the URL, if the caller may see it (`scope = "visible"`) or handle
    it (`"managed"`); a 404 otherwise, before any other check runs."""

    scope = "visible"

    def dispatch(self, request, *args, **kwargs):
        reports = BugReport.objects
        found = (
            reports.managed_by(request.user)
            if self.scope == "managed"
            else reports.visible_to(request.user)
        )
        self.report = get_object_or_404(
            found.select_related("project", "submitter__profile", "assignee__profile"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)


class BugListView(LoginRequiredMixin, ListingMixin, TemplateView):
    """The reports the member may see, 20 a page, searched, filtered and ordered by the query
    string (reports.listing), newest first. An HTMX request gets the list's part."""

    template_name = "reports/bug_list.html"
    partial_template_name = "reports/partials/bug_list.html"
    list_id = "bug-list"

    def visible(self):
        return BugReport.objects.visible_to(self.request.user)

    @cached_property
    def listing(self):
        return for_member(self.request.user, self.visible())

    def get_listing_queryset(self):
        return self.visible().select_related("project", "submitter__profile", "assignee__profile")

    def get_list_url(self) -> str:
        return reverse("reports:bug_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        count = context["count"]
        context.update(
            text=strings,
            count_words=count_words(count, strings.BUGS_COUNT, strings.BUGS_COUNT_PLURAL),
            empty=not count and not context["selection"].narrowed,
            rows=[bug_row(report, self.request.user) for report in context["page"]],
        )
        return context


class BugCreateView(VerifiedEmailRequiredMixin, View):
    """Send a bug report or feedback (verified members, 5 a day): about the engine or one of
    the member's projects (`?about=<slug>` chooses it)."""

    template_name = "reports/bug_form.html"

    def form(self, data=None):
        projects = list(bugs.reportable_projects(self.request.user))
        initial = {}
        about = self.request.GET.get("about", "")
        if about in {project.slug for project in projects}:
            initial["about"] = about
        return BugReportForm(data, projects=projects, initial=initial)

    def page(self, form):
        mark_invalid(form)
        return render(
            self.request,
            self.template_name,
            {
                "text": strings,
                "form": form,
                "limit": bugs.limit_message(self.request.user),
            },
        )

    def get(self, request):
        return self.page(self.form())

    def post(self, request):
        form = self.form(request.POST)
        if not form.is_valid():
            return self.page(form)
        try:
            report = bugs.submit(request.user, **form.report_fields())
        except EmailNotVerified:
            return HttpResponseRedirect(verify_email_url())
        except LimitReached as error:
            form.add_error(None, str(error))
            return self.page(form)
        except ValidationError as error:
            form.add_error(None, error)
            return self.page(form)
        except PermissionDenied:
            raise Http404 from None
        messages.success(request, strings.BUG_SENT)
        return HttpResponseRedirect(report.get_absolute_url())


def bug_context(request, report: BugReport, *, comment_form=None) -> dict:
    """What a report's page needs: the report, who sent and has it, its timeline, and, for
    those who handle it, the statuses it may move to and who it may be assigned."""
    user = request.user
    manage = bugs.can_manage(user, report)
    context = {
        "text": strings,
        "report": report,
        "submitter": person(report.submitter) if report.submitter else None,
        "assignee": person(report.assignee) if report.assignee else None,
        "is_submitter": report.submitter_id == user.pk,
        "can_manage": manage,
        "activity": [
            activity_row(entry)
            for entry in report.activity.select_related("actor__profile", "assignee__profile")
        ],
        "comment_form": comment_form or BugCommentForm(),
    }
    if manage:
        context["next_statuses"] = [
            {"value": status.value, "label": status.label} for status in report.next_statuses()
        ]
        context["assignable"] = [
            {
                "pk": member.pk,
                "name": person(member)["name"],
                "username": member.username,
                "current": member.pk == report.assignee_id,
            }
            for member in bugs.assignable(report).select_related("profile")
        ]
    return context


class BugDetailView(BugLookupMixin, View):
    """A report's page: its submitter, the project's Owners and Maintainers, and admins."""

    def get(self, request, pk):
        return render(request, "reports/bug_detail.html", bug_context(request, self.report))


class BugStatusView(BugLookupMixin, View):
    """POST: change a report's status (those who handle it; anyone else 404)."""

    scope = "managed"
    http_method_names = ["post"]

    def post(self, request, pk):
        form = BugStatusForm(request.POST)
        status = form.cleaned_data["status"] if form.is_valid() else ""
        try:
            report = bugs.change_status(request.user, self.report, status)
        except bugs.TransitionRefused as error:
            messages.error(request, str(error))
        except PermissionDenied:
            raise Http404 from None
        else:
            messages.success(
                request, strings.BUG_STATUS_CHANGED.format(status=report.get_status_display())
            )
        return HttpResponseRedirect(self.report.get_absolute_url())


class BugAssignView(BugLookupMixin, View):
    """POST: assign a report, or unassign it (those who handle it; anyone else 404)."""

    scope = "managed"
    http_method_names = ["post"]

    def post(self, request, pk):
        form = BugAssignForm(request.POST)
        value = form.cleaned_data["assignee"].strip() if form.is_valid() else "?"
        assignee = None
        if value:
            assignee = (
                get_user_model().objects.filter(pk=int(value)).first()
                if value.isascii() and value.isdigit()
                else None
            )
            if assignee is None:
                messages.error(request, strings.BUG_ASSIGNEE_REFUSED)
                return HttpResponseRedirect(self.report.get_absolute_url())
        try:
            report = bugs.assign(request.user, self.report, assignee)
        except bugs.AssigneeRefused as error:
            messages.error(request, str(error))
        except PermissionDenied:
            raise Http404 from None
        else:
            messages.success(
                request,
                strings.BUG_ASSIGNED.format(name=person(report.assignee)["name"])
                if report.assignee
                else strings.BUG_UNASSIGNED,
            )
        return HttpResponseRedirect(self.report.get_absolute_url())


class BugCommentView(BugLookupMixin, VerifiedEmailRequiredMixin, View):
    """POST: comment on a report (anyone who may see it, verified)."""

    http_method_names = ["post"]

    def post(self, request, pk):
        form = BugCommentForm(request.POST)
        if form.is_valid():
            try:
                entry = bugs.comment(request.user, self.report, form.cleaned_data["body"])
            except EmailNotVerified:
                return HttpResponseRedirect(verify_email_url())
            except ValidationError as error:
                form.add_error("body", error.messages)
            except PermissionDenied:
                raise Http404 from None
            else:
                messages.success(request, strings.BUG_COMMENTED)
                return HttpResponseRedirect(f"{self.report.get_absolute_url()}#activity-{entry.pk}")
        mark_invalid(form)
        context = bug_context(request, self.report, comment_form=form)
        return render(request, "reports/bug_detail.html", context)
