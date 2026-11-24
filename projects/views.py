"""Project pages, in the app shell, and the repository webhook.

Every project page is its owner's only: anyone else gets a 404 (Phase 11 adds members).
Views are thin; the rules live in projects.services, projects.github and projects.webhooks.
"""

from datetime import UTC, datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DeleteView, DetailView, FormView, ListView, UpdateView

from accounts.access import VerifiedEmailRequiredMixin, has_verified_email
from accounts.limits import LimitReached

from . import github, services, strings, webhooks
from .forms import LinkRepositoryForm, ProjectForm
from .models import Project, RepositoryLink


def when(moment: datetime) -> str:
    """A moment as the pages show it: "24 Nov 2026, 12:05 UTC"."""
    return timezone.localtime(moment).strftime("%d %b %Y, %H:%M %Z")


def refusal(error: services.RepositoryError) -> str:
    """A refused repository action's message, with when to retry after a rate limit."""
    text = str(error)
    if error.retry_at:
        text = f"{text} {strings.RETRY_AFTER.format(when=when(error.retry_at))}"
    return text


class OwnedProjectMixin(LoginRequiredMixin):
    """The project named by the URL's slug, if the signed-in member owns it; a 404 otherwise."""

    def get_queryset(self):
        return Project.objects.owned_by(self.request.user)

    def get_project(self) -> Project:
        return get_object_or_404(self.get_queryset(), slug=self.kwargs["slug"])


class ProjectListView(LoginRequiredMixin, ListView):
    """The member's own projects, and how many more they may create."""

    template_name = "projects/list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return Project.objects.owned_by(self.request.user).select_related("repository")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        count = len(context["projects"])
        context.update(
            text=strings,
            count_text=strings.LIST_COUNT.format(count=count, limit=Project.LIMIT_PER_OWNER),
            at_limit=count >= Project.LIMIT_PER_OWNER,
            verified=has_verified_email(self.request.user),
        )
        return context


class ProjectCreateView(VerifiedEmailRequiredMixin, FormView):
    """Create a project (verified members only, at most Project.LIMIT_PER_OWNER each)."""

    form_class = ProjectForm
    template_name = "projects/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        at_limit = Project.objects.owned_by(self.request.user).count()
        context.update(
            text=strings,
            title=strings.CREATE_TITLE,
            lede=strings.CREATE_LEDE,
            submit=strings.CREATE,
            cancel_url=reverse("projects:list"),
            at_limit=at_limit >= Project.LIMIT_PER_OWNER,
        )
        return context

    def form_valid(self, form):
        try:
            project = services.create_project(
                self.request.user,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
            )
        except LimitReached as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        except ValidationError as error:
            form.add_error(None, error)  # a name error lands on the name field
            return self.form_invalid(form)
        messages.success(self.request, strings.CREATED)
        return HttpResponseRedirect(project.get_absolute_url())


class ProjectDetailView(OwnedProjectMixin, DetailView):
    """A project, its linked repository, and the repository's actions.

    Details older than GITHUB_REPOSITORY_REFRESH are fetched again on view (with the member's
    permission resolved first); when GitHub can't answer, the stored details are shown with
    a notice saying why and from when.
    """

    template_name = "projects/detail.html"
    context_object_name = "project"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        link = RepositoryLink.objects.filter(project=project).first()
        notice = ""
        if link is not None and not link.deleted_on_github:
            now = datetime.now(UTC)
            stale = link.fetched_at is None or (
                now - link.fetched_at >= settings.GITHUB_REPOSITORY_REFRESH
            )
            if stale:
                try:
                    link = services.refresh_repository(self.request.user, project, now=now)
                except services.RepositoryError as error:
                    shown = when(link.fetched_at) if link.fetched_at else strings.NEVER
                    notice = strings.STALE_NOTICE.format(when=shown, reason=refusal(error))
        context.update(
            text=strings,
            link=link,
            notice=notice,
            link_form=LinkRepositoryForm(),
            has_github=github.member_link(self.request.user) is not None,
            webhooks_on=webhooks.webhooks_on(),
        )
        return context


class ProjectUpdateView(VerifiedEmailRequiredMixin, OwnedProjectMixin, UpdateView):
    """Rename a project or change its description (its address follows the name)."""

    form_class = ProjectForm
    template_name = "projects/form.html"
    context_object_name = "project"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            text=strings,
            title=strings.EDIT_TITLE,
            lede="",
            submit=strings.SAVE,
            cancel_url=self.object.get_absolute_url(),
            at_limit=False,
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, strings.SAVED)
        return super().form_valid(form)


class ProjectDeleteView(OwnedProjectMixin, DeleteView):
    """Delete a project after confirming (its repository link goes with it)."""

    template_name = "projects/confirm_delete.html"
    context_object_name = "project"
    success_url = reverse_lazy("projects:list")

    def get_context_data(self, **kwargs):
        return super().get_context_data(text=strings, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, strings.DELETED)
        return super().form_valid(form)


class LinkRepositoryView(VerifiedEmailRequiredMixin, OwnedProjectMixin, View):
    """Link a GitHub repository to the project (POST; the member must be its admin)."""

    def post(self, request, slug):
        project = self.get_project()
        form = LinkRepositoryForm(request.POST)
        if not form.is_valid():
            messages.error(request, strings.REPOSITORY_NAME_INVALID)
        else:
            try:
                services.link_repository(request.user, project, form.cleaned_data["repository"])
            except services.RepositoryError as error:
                messages.error(request, refusal(error))
            else:
                messages.success(request, strings.REPOSITORY_LINKED)
        return HttpResponseRedirect(project.get_absolute_url())


class UnlinkRepositoryView(OwnedProjectMixin, View):
    """Unlink the project's repository (POST). GitHub isn't asked: it's the Hub's own record."""

    def post(self, request, slug):
        project = self.get_project()
        services.unlink_repository(request.user, project)
        messages.success(request, strings.REPOSITORY_UNLINKED)
        return HttpResponseRedirect(project.get_absolute_url())


class RefreshRepositoryView(OwnedProjectMixin, View):
    """Fetch the repository's details from GitHub now (POST; needs read permission)."""

    def post(self, request, slug):
        project = self.get_project()
        try:
            services.refresh_repository(request.user, project)
        except services.RepositoryError as error:
            messages.error(request, refusal(error))
        else:
            messages.success(request, strings.REPOSITORY_REFRESHED)
        return HttpResponseRedirect(project.get_absolute_url())


@method_decorator(never_cache, name="dispatch")
class WebhookSettingsView(OwnedProjectMixin, View):
    """The webhook's payload URL and secret, for an admin of the repository on GitHub.

    Never cached: the page carries the link's secret.
    """

    def get(self, request, slug):
        project = self.get_project()
        try:
            hook = services.webhook_settings(request.user, project)
        except services.RepositoryError as error:
            messages.error(request, refusal(error))
            return HttpResponseRedirect(project.get_absolute_url())
        return render(
            request,
            "projects/webhook.html",
            {
                "copy": strings,
                "project": project,
                "payload_url": request.build_absolute_uri(hook.path),
                "secret": hook.secret,
            },
        )


@method_decorator(csrf_exempt, name="dispatch")
class GitHubWebhookView(View):
    """GitHub's deliveries for one linked repository (POST only).

    The Hub's only CSRF-exempt view: GitHub can't send a CSRF token, so each delivery is
    authenticated by its signature instead (projects.webhooks). Unknown hooks, and every
    hook while webhooks are off, are a 404.
    """

    http_method_names = ["post"]

    def post(self, request, hook_id):
        if not webhooks.webhooks_on():
            raise Http404
        link = RepositoryLink.objects.filter(hook_id=hook_id).first()
        if link is None:
            raise Http404
        try:
            body = request.body
        except RequestDataTooBig:
            return HttpResponse("payload too large", status=413, content_type="text/plain")
        outcome = webhooks.receive(link, body=body, headers=request.headers, now=datetime.now(UTC))
        return HttpResponse(outcome.text, status=outcome.status, content_type="text/plain")
