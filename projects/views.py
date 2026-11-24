"""Project pages, in the app shell, the public setup guide, and the repository webhook.

Every project page is its owner's only: anyone else gets a 404 (Phase 11 adds members).
Views are thin; the rules live in projects.services, projects.github and projects.webhooks.
"""

from datetime import UTC, datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from accounts.access import VerifiedEmailRequiredMixin, has_verified_email
from accounts.limits import LimitReached

from . import github, services, strings, webhooks
from .forms import LinkRepositoryForm, ProjectForm
from .models import Project, RepositoryLink
from .setup import Setup, State, setup_for


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


# Hosts GitHub can never deliver to: the setup step warns that a tunnel is needed.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


def project_setup(user, link: RepositoryLink | None) -> dict:
    """A project's setup progress for its card: the steps' states, done and total."""
    setup = setup_for(user, link)
    return {
        "steps": [step.state.value for step in setup.steps],
        "done": setup.done,
        "total": setup.total,
        "complete": setup.complete,
        "label": (
            strings.SETUP_COMPLETE
            if setup.complete
            else strings.SETUP_PROGRESS.format(done=setup.done, total=setup.total)
        ),
    }


def step_rows(request, setup: Setup, link: RepositoryLink | None) -> list[dict]:
    """Each setup step as the page shows it: its number, words, state and summary line."""
    account = github.member_link(request.user)
    rows = []
    for step in setup.steps:
        copy = strings.STEPS[step.key]
        summary = copy.get(step.state.value) or copy["current"]
        if step.state is State.DONE:
            if step.key == "account" and account is not None:
                summary = copy["done"].format(login=account.login or "GitHub")
            elif step.key == "repository" and link is not None:
                summary = copy["done"].format(full_name=link.full_name)
            elif step.key == "delivery" and link is not None and link.first_webhook_at:
                summary = copy["done"].format(
                    first=when(link.first_webhook_at), last=when(link.webhook_at)
                )
        rows.append(
            {
                "key": step.key,
                "number": step.number,
                "state": step.state.value,
                "state_label": strings.STEP_STATES[step.state.value],
                "title": copy["title"],
                "icon": copy["icon"],
                "summary": summary,
                "open": step.open,
                "words": copy,
            }
        )
    return rows


class ProjectListView(LoginRequiredMixin, ListView):
    """The member's own projects as cards with their setup progress, and how many more
    they may create."""

    template_name = "projects/list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return Project.objects.owned_by(self.request.user).select_related("repository")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        cards = []
        for project in context["projects"]:
            link = RepositoryLink.objects.filter(project=project).first()
            cards.append({"project": project, "link": link, "setup": project_setup(user, link)})
        count = len(cards)
        context.update(
            text=strings,
            cards=cards,
            count_text=strings.LIST_COUNT.format(count=count, limit=Project.LIMIT_PER_OWNER),
            at_limit=count >= Project.LIMIT_PER_OWNER,
            verified=has_verified_email(user),
            guide_steps=[
                (f"{n:02d}", strings.STEPS[key]["title"], strings.STEPS[key]["icon"])
                for n, key in enumerate(strings.STEPS, start=1)
            ],
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
    """A project: its repository setup checklist, and the linked repository.

    Details older than GITHUB_REPOSITORY_REFRESH are fetched again on view (with the member's
    permission resolved first); when GitHub can't answer, the stored details are shown with
    a notice saying why and from when. `?webhook=show` shows the webhook's payload URL and
    secret inside the checklist, after an admin check, on a page that's never cached.
    """

    template_name = "projects/detail.html"
    context_object_name = "project"
    secret_shown = False

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if self.secret_shown:
            add_never_cache_headers(response)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request, project = self.request, self.object
        link = RepositoryLink.objects.filter(project=project).first()
        notice = webhook_error = ""
        hook = None
        now = datetime.now(UTC)
        if link is not None and not link.deleted_on_github:
            stale = link.fetched_at is None or (
                now - link.fetched_at >= settings.GITHUB_REPOSITORY_REFRESH
            )
            if stale:
                try:
                    link = services.refresh_repository(request.user, project, now=now)
                except services.RepositoryError as error:
                    shown = when(link.fetched_at) if link.fetched_at else strings.NEVER
                    notice = strings.STALE_NOTICE.format(when=shown, reason=refusal(error))
        if link is not None and request.GET.get("webhook") == "show":
            try:
                hook = services.webhook_settings(request.user, project, now=now)
            except services.RepositoryError as error:
                webhook_error = refusal(error)
            else:
                self.secret_shown = True
                link.refresh_from_db()
        setup = setup_for(request.user, link)
        fields = []
        if hook is not None:
            values = {
                "payload_url": request.build_absolute_uri(hook.path),
                "secret": hook.secret,
            }
            fields = [
                {"label": label, "value": value.format(**values), "copy": copyable, "id": i}
                for i, (label, value, copyable) in enumerate(strings.WEBHOOK_FIELDS)
            ]
        host = request.get_host().rsplit(":", 1)[0] if hook is not None else ""
        moments = [m for m in (link.fetched_at, link.webhook_at) if m] if link else []
        context.update(
            text=strings,
            link=link,
            notice=notice,
            setup=setup,
            steps=step_rows(request, setup, link),
            link_form=LinkRepositoryForm(),
            hook=hook,
            webhook_fields=fields,
            webhook_error=webhook_error,
            webhook_new_url=f"{link.html_url}/settings/hooks/new" if link else "",
            updated_at=max(moments) if moments else None,
            local_warning=(
                strings.STEPS["webhook"]["local"].format(host=request.get_host())
                if host in LOCAL_HOSTS
                else ""
            ),
        )
        return context


class ProjectGuideView(TemplateView):
    """The setup guide: connecting a GitHub repository, step by step (public)."""

    template_name = "projects/guide.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            text=strings,
            steps=[
                {
                    "number": f"{n:02d}",
                    "title": strings.STEPS[key]["title"],
                    "icon": strings.STEPS[key]["icon"],
                    "paragraphs": strings.GUIDE_STEPS[key],
                }
                for n, key in enumerate(strings.STEPS, start=1)
            ],
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
