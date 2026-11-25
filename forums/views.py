"""Forum pages, in the app shell.

Anyone may read the list and a post. Writing a post needs a verified member; editing and
deleting one are its author's alone. For anyone else (another member, an admin who isn't the
author, a signed-out visitor) the edit and delete URLs are a 404, never a 403, found before
anything else runs, so they reveal nothing.

On a post's page, Edit and Delete work in place through HTMX: the view answers an HTMX
request (`request.htmx`, django-htmx) with the part of the page that changes, and any other
request with the whole page or a redirect, so every action works without JavaScript too.
Responses that differ by the `HX-Request` header say so in `Vary`.
"""

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views import View
from django.views.generic import DetailView, FormView, ListView
from django_htmx.http import HttpResponseClientRedirect

from accounts.access import EmailNotVerified, VerifiedEmailRequiredMixin, verify_email_url

from . import services, strings
from .forms import PostForm
from .models import ForumPost


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


def post_context(request, post: ForumPost, **extra) -> dict:
    """What the post's part of the page needs: the post, its author, and whether the
    visitor wrote it (only then are Edit and Delete shown)."""
    return {
        "text": strings,
        "post": post,
        "author": person(post.author),
        "is_author": post.is_author(request.user),
        **extra,
    }


def mark_invalid(form: PostForm) -> None:
    """Mark each field with an error for assistive technology, and focus the first: after
    an in-place swap, the member lands on what to fix."""
    first = True
    for name in form.errors:
        if name not in form.fields:
            continue
        attrs = form.fields[name].widget.attrs
        attrs["aria-invalid"] = "true"
        if first:
            attrs["autofocus"] = True
            first = False


class HtmxAwareMixin:
    """Answers an HTMX request that would be redirected (to sign in, to verify, to the
    list) with `HX-Redirect`, so the browser loads that page in full rather than swapping it
    into the post. Every answer varies on `HX-Request`."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.htmx and response.status_code in (301, 302, 303):
            response = HttpResponseClientRedirect(response["Location"])
        patch_vary_headers(response, ["HX-Request"])
        return response


class AuthorPostMixin:
    """The post named by the URL, if the caller wrote it; a 404 otherwise, for a signed-out
    visitor too, before any other check (sign-in, verification) can run."""

    def dispatch(self, request, *args, **kwargs):
        self.post_object = get_object_or_404(
            ForumPost.objects.authored_by(request.user), pk=kwargs["pk"]
        )
        return super().dispatch(request, *args, **kwargs)


class PostListView(ListView):
    """Every post, newest first, for anyone."""

    template_name = "forums/list.html"
    context_object_name = "posts"

    def get_queryset(self):
        return ForumPost.objects.select_related("author__profile")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            text=strings,
            rows=[{"post": post, "author": person(post.author)} for post in context["posts"]],
        )
        return context


class PostDetailView(HtmxAwareMixin, DetailView):
    """A post, for anyone. An HTMX request (Cancel while editing) gets the post's part of
    the page, with its heading focused."""

    queryset = ForumPost.objects.select_related("author__profile")
    template_name = "forums/detail.html"

    def get(self, request, *args, **kwargs):
        if request.htmx:
            post = self.get_object()
            return render(
                request, "forums/partials/post.html", post_context(request, post, swapped=True)
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(post_context(self.request, self.object))
        return context


class PostCreateView(HtmxAwareMixin, VerifiedEmailRequiredMixin, FormView):
    """Publish a post (verified members only)."""

    form_class = PostForm
    template_name = "forums/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            text=strings,
            title=strings.CREATE_TITLE,
            lede=strings.CREATE_LEDE,
            submit=strings.PUBLISH,
            cancel_url=reverse("forums:list"),
        )
        return context

    def form_valid(self, form):
        try:
            post = services.create_post(self.request.user, **form.cleaned_data)
        except EmailNotVerified:
            return HttpResponseRedirect(verify_email_url())
        messages.success(self.request, strings.CREATED)
        return HttpResponseRedirect(post.get_absolute_url())


class PostEditView(HtmxAwareMixin, AuthorPostMixin, VerifiedEmailRequiredMixin, View):
    """Edit a post (its verified author only). Through HTMX the post swaps into its form and
    back; otherwise a full page, then a redirect to the post."""

    def render_form(self, request, form: PostForm):
        post = self.post_object
        if request.htmx:
            return render(
                request,
                "forums/partials/post_form.html",
                post_context(request, post, form=form, swapped=True),
            )
        return render(
            request,
            "forums/form.html",
            {
                "text": strings,
                "form": form,
                "post": post,
                "title": strings.EDIT_TITLE,
                "lede": "",
                "submit": strings.SAVE,
                "cancel_url": post.get_absolute_url(),
            },
        )

    def get(self, request, pk):
        form = PostForm(initial={"title": self.post_object.title, "body": self.post_object.body})
        if request.htmx:
            form.fields["title"].widget.attrs["autofocus"] = True
        return self.render_form(request, form)

    def post(self, request, pk):
        post = self.post_object
        form = PostForm(request.POST)
        if not form.is_valid():
            mark_invalid(form)
            return self.render_form(request, form)
        try:
            services.edit_post(request.user, post, **form.cleaned_data)
        except EmailNotVerified:
            return HttpResponseRedirect(verify_email_url())
        if request.htmx:
            return render(
                request,
                "forums/partials/post.html",
                post_context(request, post, swapped=True, status=strings.SAVED),
            )
        messages.success(request, strings.SAVED)
        return HttpResponseRedirect(post.get_absolute_url())


class PostDeleteView(HtmxAwareMixin, AuthorPostMixin, View):
    """Delete a post (its author only) after confirming. Through HTMX the confirmation opens
    in place of the post and the post gives way to a notice; otherwise a confirmation page,
    then a redirect to the list."""

    def get(self, request, pk):
        context = post_context(request, self.post_object, swapped=bool(request.htmx))
        if request.htmx:
            return render(request, "forums/partials/confirm_delete.html", context)
        return render(request, "forums/confirm_delete.html", context)

    def post(self, request, pk):
        title = services.delete_post(request.user, self.post_object)
        if request.htmx:
            return render(
                request,
                "forums/partials/deleted.html",
                {
                    "text": strings,
                    "deleted_text": strings.DELETED_TEXT.format(title=title),
                    "status": strings.DELETED,
                },
            )
        messages.success(request, strings.DELETED)
        return HttpResponseRedirect(reverse("forums:list"))
