"""Project pages, in the app shell, and the repository webhook.

Each project view names the Action it needs; the members whose role allows it (models.
PERMISSIONS) see the page, and everyone else gets a 404. Views are thin; the rules live in
projects.services, projects.teams, projects.github and projects.webhooks.
"""

from datetime import UTC, datetime
from urllib.parse import urlsplit

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
    UpdateView,
)

from accounts.access import EmailNotVerified, VerifiedEmailRequiredMixin, has_verified_email
from accounts.limits import LimitReached

from . import github, services, strings, teams, webhooks
from .forms import DescriptionForm, InviteForm, LinkRepositoryForm, ProjectForm, RoleForm
from .models import (
    Action,
    Project,
    ProjectInvitation,
    ProjectMembership,
    RepositoryLink,
    Role,
    allows,
)
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


class ProjectAccessMixin(LoginRequiredMixin):
    """The project named by the URL's slug, if the signed-in member's role allows `action`;
    a 404 otherwise (whether the project exists or not)."""

    action = Action.VIEW

    def get_queryset(self):
        return Project.objects.allowing(self.request.user, self.action)

    def get_project(self) -> Project:
        return get_object_or_404(self.get_queryset(), slug=self.kwargs["slug"])


# Hosts GitHub can never deliver to: the setup step warns that a tunnel is needed.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def payload_url(request, path: str) -> str:
    """`path` as GitHub must reach it: on HUB_PUBLIC_URL when set, else this page's address."""
    if settings.HUB_PUBLIC_URL:
        return settings.HUB_PUBLIC_URL + path
    return request.build_absolute_uri(path)


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


def first_repository(user, project: Project) -> bool:
    """Whether this is the member's first repository: none of their other projects has one.
    The setup's help opens by itself on the current step until then."""
    return not (
        RepositoryLink.objects.filter(project__in=Project.objects.owned_by(user))
        .exclude(project=project)
        .exists()
    )


def step_rows(
    request, setup: Setup, link: RepositoryLink | None, *, first_time: bool = False
) -> list[dict]:
    """Each setup step as the page shows it: its number, words, state and summary line, and
    its help (open on the current step of a member's first repository)."""
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
                "help": strings.HELP_STEPS[step.key],
                "help_open": first_time and step.state in (State.CURRENT, State.ATTENTION),
            }
        )
    return rows


class ProjectListView(LoginRequiredMixin, ListView):
    """The member's own projects as cards with their setup progress, and how many more
    they may create."""

    template_name = "projects/list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return Project.objects.visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        roles = dict(ProjectMembership.objects.filter(user=user).values_list("project_id", "role"))
        cards = []
        for project in context["projects"]:
            link = RepositoryLink.objects.filter(project=project).first()
            role = roles[project.pk]
            owner = allows(role, Action.MANAGE_REPOSITORY)
            cards.append(
                {
                    "project": project,
                    "link": link,
                    "role": role,
                    "role_label": strings.ROLES[role],
                    # The setup is the Owners' (their GitHub account links the repository).
                    "setup": project_setup(user, link) if owner else None,
                }
            )
        owned = services.owned_count(user)
        invitations = [
            {
                "invitation": invitation,
                "text": strings.INVITATION_ROW.format(
                    inviter=invitation.invited_by.username
                    if invitation.invited_by
                    else strings.SOMEONE,
                    role=strings.ROLES[invitation.role],
                ),
            }
            for invitation in ProjectInvitation.objects.filter(invitee=user).select_related(
                "project", "invited_by"
            )
        ]
        context.update(
            text=strings,
            cards=cards,
            invitations=invitations,
            count_text=strings.LIST_COUNT.format(count=owned, limit=Project.LIMIT_PER_OWNER),
            at_limit=owned >= Project.LIMIT_PER_OWNER,
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
        at_limit = services.owned_count(self.request.user)
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


class ProjectDetailView(ProjectAccessMixin, DetailView):
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
        role = project.role_of(request.user)
        can = {action.value: allows(role, action) for action in Action}
        link = RepositoryLink.objects.filter(project=project).first()
        notice = webhook_error = ""
        hook = None
        now = datetime.now(UTC)
        # A stale repository is refreshed for members who may refresh it (with their own
        # GitHub permission); Viewers see the stored details.
        if can["refresh"] and link is not None and not link.deleted_on_github:
            stale = link.fetched_at is None or (
                now - link.fetched_at >= settings.GITHUB_REPOSITORY_REFRESH
            )
            if stale:
                try:
                    link = services.refresh_repository(request.user, project, now=now)
                except services.RepositoryError as error:
                    shown = when(link.fetched_at) if link.fetched_at else strings.NEVER
                    notice = strings.STALE_NOTICE.format(when=shown, reason=refusal(error))
        if can["manage_repository"] and link is not None and request.GET.get("webhook") == "show":
            try:
                hook = services.webhook_settings(request.user, project, now=now)
            except services.RepositoryError as error:
                webhook_error = refusal(error)
            else:
                self.secret_shown = True
                link.refresh_from_db()
        setup = setup_for(request.user, link)
        first_time = first_repository(request.user, project)
        fields = []
        if hook is not None:
            values = {
                "payload_url": payload_url(request, hook.path),
                "secret": hook.secret,
            }
            fields = [
                {"label": label, "value": value.format(**values), "copy": copyable, "id": i}
                for i, (label, value, copyable) in enumerate(strings.WEBHOOK_FIELDS)
            ]
        # The payload URL's host: the public address when one is set, else this page's.
        public = urlsplit(payload_url(request, "/"))
        host = (public.hostname or "") if hook is not None else ""
        moments = [m for m in (link.fetched_at, link.webhook_at) if m] if link else []
        context.update(
            text=strings,
            role=role,
            role_label=strings.ROLES[role],
            can=can,
            team_count=project.memberships.count(),
            link=link,
            notice=notice,
            setup=setup,
            steps=step_rows(request, setup, link, first_time=first_time),
            first_time=first_time,
            link_form=LinkRepositoryForm(),
            hook=hook,
            webhook_fields=fields,
            webhook_error=webhook_error,
            webhook_new_url=f"{link.html_url}/settings/hooks/new" if link else "",
            updated_at=max(moments) if moments else None,
            local_warning=(
                strings.STEPS["webhook"]["local"].format(host=public.netloc)
                if host in LOCAL_HOSTS
                else ""
            ),
            # Only a development server's own developer can act on this hint.
            show_operator_hint=settings.DEBUG,
        )
        return context


class ProjectUpdateView(VerifiedEmailRequiredMixin, ProjectAccessMixin, UpdateView):
    """Change a project's description, and for an Owner its name (the address follows)."""

    action = Action.EDIT
    template_name = "projects/form.html"
    context_object_name = "project"

    def get_form_class(self):
        # Renaming is an Owner's: a Maintainer's form has no name, so a posted one is ignored.
        if allows(self.object.role_of(self.request.user), Action.RENAME):
            return ProjectForm
        return DescriptionForm

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


class ProjectDeleteView(ProjectAccessMixin, DeleteView):
    """Delete a project after confirming (its team and repository link go with it)."""

    action = Action.DELETE

    template_name = "projects/confirm_delete.html"
    context_object_name = "project"
    success_url = reverse_lazy("projects:list")

    def get_context_data(self, **kwargs):
        return super().get_context_data(text=strings, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, strings.DELETED)
        return super().form_valid(form)


class LinkRepositoryView(VerifiedEmailRequiredMixin, ProjectAccessMixin, View):
    """Link a GitHub repository to the project (POST; the member must be its admin)."""

    action = Action.MANAGE_REPOSITORY

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


class UnlinkRepositoryView(ProjectAccessMixin, View):
    """Unlink the project's repository (POST). GitHub isn't asked: it's the Hub's own record."""

    action = Action.MANAGE_REPOSITORY

    def post(self, request, slug):
        project = self.get_project()
        services.unlink_repository(request.user, project)
        messages.success(request, strings.REPOSITORY_UNLINKED)
        return HttpResponseRedirect(project.get_absolute_url())


class RefreshRepositoryView(ProjectAccessMixin, View):
    """Fetch the repository's details from GitHub now (POST; needs read permission)."""

    action = Action.REFRESH

    def post(self, request, slug):
        project = self.get_project()
        try:
            services.refresh_repository(request.user, project)
        except services.RepositoryError as error:
            messages.error(request, refusal(error))
        else:
            messages.success(request, strings.REPOSITORY_REFRESHED)
        return HttpResponseRedirect(project.get_absolute_url())


def person(user) -> dict:
    """A member as `partials/avatar.html` shows them: name, photo or initial."""
    profile = getattr(user, "profile", None)
    if profile is None:
        return {"name": user.username, "initial": user.username[:1].upper(), "photo": ""}
    return {
        "name": profile.name,
        "initial": profile.initial,
        "photo": profile.avatar.url if profile.avatar else "",
    }


class MembersView(ProjectAccessMixin, DetailView):
    """The project's team and, for its Owners, the pending invitations and the controls."""

    template_name = "projects/members.html"
    context_object_name = "project"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project, user = self.object, self.request.user
        role = project.role_of(user)
        manage = allows(role, Action.MANAGE_MEMBERS)
        members = project.memberships.select_related("user", "user__profile")
        context.update(
            text=strings,
            role=role,
            manage=manage,
            members=[
                {
                    "membership": m,
                    "person": person(m.user),
                    "role_label": strings.ROLES[m.role],
                    "me": m.user_id == user.pk,
                    "form": RoleForm(initial={"role": m.role}, auto_id=f"member-{m.pk}-%s"),
                }
                for m in members
            ],
            # The only Owner can't leave or step down: the page says so instead.
            last_owner=role == Role.OWNER
            and not project.memberships.filter(role=Role.OWNER).exclude(user=user).exists(),
            roles=[(strings.ROLES[key], note) for key, note in strings.ROLE_NOTES.items()],
            invitations=[
                {
                    "invitation": invitation,
                    "person": person(invitation.invitee),
                    "text": strings.PENDING_ROW.format(
                        role=strings.ROLES[invitation.role],
                        inviter=invitation.invited_by.username
                        if invitation.invited_by
                        else strings.SOMEONE,
                    ),
                }
                for invitation in (
                    project.invitations.select_related("invitee__profile", "invited_by")
                    if manage
                    else []
                )
            ],
            invite_form=InviteForm(),
        )
        return context


class TeamActionView(ProjectAccessMixin, View):
    """A team change (POST): run it, show its refusal if any, and return to the team page.

    Anything the member can't see (a project, membership or invitation) is a 404."""

    action = Action.MANAGE_MEMBERS
    success = ""

    def change(self, request, project: Project) -> None:
        raise NotImplementedError

    def done_url(self, project: Project) -> str:
        return reverse("projects:members", args=[project.slug])

    def post(self, request, slug, **kwargs):
        project = self.get_project()
        try:
            self.change(request, project)
        except (
            Project.DoesNotExist,
            ProjectMembership.DoesNotExist,
            ProjectInvitation.DoesNotExist,
        ):
            raise Http404 from None
        except (teams.TeamError, LimitReached, EmailNotVerified) as error:
            messages.error(request, str(error))
            return HttpResponseRedirect(reverse("projects:members", args=[project.slug]))
        if self.success:
            messages.success(request, self.success)
        return HttpResponseRedirect(self.done_url(project))


class InviteView(VerifiedEmailRequiredMixin, TeamActionView):
    """Invite a member by username, in a role (an Owner's action)."""

    success = strings.INVITED

    def change(self, request, project):
        form = InviteForm(request.POST)
        if not form.is_valid():
            raise teams.TeamError(strings.INVITE_INVALID)
        teams.invite(
            request.user, project, form.cleaned_data["username"], form.cleaned_data["role"]
        )


class MemberRoleView(TeamActionView):
    """Change a member's role (an Owner's action)."""

    success = strings.ROLE_CHANGED

    def change(self, request, project):
        form = RoleForm(request.POST)
        if not form.is_valid():
            raise teams.TeamError(strings.ROLE_INVALID)
        teams.change_role(request.user, project, self.kwargs["pk"], form.cleaned_data["role"])

    def done_url(self, project):
        # An Owner who stepped down may no longer see the team's controls, but still the team.
        return reverse("projects:members", args=[project.slug])


class MemberRemoveView(TeamActionView):
    """Take a member out of the team (an Owner's action)."""

    success = strings.MEMBER_REMOVED

    def change(self, request, project):
        teams.remove(request.user, project, self.kwargs["pk"])

    def done_url(self, project):
        if project.role_of(self.request.user) is None:  # removed themselves
            return reverse("projects:list")
        return super().done_url(project)


class InvitationCancelView(TeamActionView):
    """Withdraw a pending invitation (an Owner's action)."""

    success = strings.INVITATION_CANCELLED

    def change(self, request, project):
        teams.cancel(request.user, project, self.kwargs["pk"])


class LeaveView(TeamActionView):
    """Leave the project (any member)."""

    action = Action.VIEW
    success = strings.LEFT

    def change(self, request, project):
        teams.leave(request.user, project)

    def done_url(self, project):
        return reverse("projects:list")


class InvitationAnswerView(LoginRequiredMixin, View):
    """Accept or decline an invitation (POST; the invitee only, everyone else a 404)."""

    def answer(self, user, pk: int) -> str:
        raise NotImplementedError

    def post(self, request, pk):
        try:
            url = self.answer(request.user, pk)
        except ProjectInvitation.DoesNotExist:
            raise Http404 from None
        except (teams.TeamError, LimitReached) as error:
            messages.error(request, str(error))
            return HttpResponseRedirect(reverse("projects:list"))
        return HttpResponseRedirect(url)


class InvitationAcceptView(InvitationAnswerView):
    def answer(self, user, pk):
        membership = teams.accept(user, pk)
        messages.success(self.request, strings.JOINED)
        return membership.project.get_absolute_url()


class InvitationDeclineView(InvitationAnswerView):
    def answer(self, user, pk):
        teams.decline(user, pk)
        messages.success(self.request, strings.DECLINED)
        return reverse("projects:list")


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
