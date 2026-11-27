"""Showcase pages, in the app shell.

Anyone may browse the list and open a showcase. Publishing needs a verified member; editing
and deleting are its author's alone. For anyone else (another member, an admin who isn't the
author, a signed-out visitor) the edit and delete URLs are a 404, never a 403, found before
anything else runs, so they reveal nothing.

The list and the Like button work in place through HTMX (the list's part, the like's part),
and as plain pages without JavaScript. Publishing and editing are full pages: they carry a
file.
"""

from django.contrib import messages
from django.db.models import Prefetch
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, TemplateView

from accounts.access import EmailNotVerified, VerifiedEmailRequiredMixin, verify_email_url
from accounts.limits import LimitReached
from config.listing import ListingMixin
from forums.views import HtmxAwareMixin, count_words, mark_invalid, person
from reports.moderation import is_published
from reports.services import has_reported

from . import services, strings
from .forms import ShowcaseForm
from .listing import SHOWCASES
from .models import Like, Showcase, Tag

TAGS_BY_NAME = Prefetch("tags", queryset=Tag.objects.order_by("name"))


def like_context(request, showcase: Showcase, **extra) -> dict:
    """The like's part of the page: the count, whether the visitor likes it, and whether
    they may (signed in, not the author, the showcase published)."""
    user = request.user
    count = Like.objects.filter(showcase=showcase).count()
    return {
        "text": strings,
        "showcase": showcase,
        "like_count": count,
        "like_words": count_words(count, strings.LIKE_COUNT, strings.LIKE_COUNT_PLURAL),
        "liked": services.has_liked(user, showcase),
        "can_like": user.is_authenticated
        and not showcase.is_author(user)
        and is_published(showcase),
        "is_author": showcase.is_author(user),
        **extra,
    }


def showcase_context(request, showcase: Showcase) -> dict:
    """What a showcase's page needs: the showcase, its author and tags, whether the visitor
    published it (only then are Edit and Delete shown), its likes, and whether they may
    report it."""
    user = request.user
    is_author = showcase.is_author(user)
    can_report = user.is_authenticated and not is_author and is_published(showcase)
    return {
        **like_context(request, showcase),
        "author": person(showcase.author),
        "tags": list(showcase.tags.all()),
        "is_author": is_author,
        "can_report": can_report,
        "reported": can_report and has_reported(user, showcase),
    }


class AuthorShowcaseMixin:
    """The showcase named by the URL, if the caller published it; a 404 otherwise, for a
    signed-out visitor too, before any other check (sign-in, verification) can run."""

    def dispatch(self, request, *args, **kwargs):
        self.showcase = get_object_or_404(
            Showcase.objects.visible_to(request.user).authored_by(request.user),
            slug=kwargs["slug"],
        )
        return super().dispatch(request, *args, **kwargs)


class PublishedShowcaseMixin:
    """The showcase named by the URL, if anyone may interact with it (like it); a 404
    otherwise, before any other check runs."""

    def dispatch(self, request, *args, **kwargs):
        self.showcase = get_object_or_404(Showcase.objects.published(), slug=kwargs["slug"])
        return super().dispatch(request, *args, **kwargs)


class ShowcaseListView(ListingMixin, TemplateView):
    """The showcases the visitor may see, 24 a page, as cards: searched, filtered (by tag
    and when published) and ordered by the query string (showcases.listing), newest first
    without one. An HTMX request gets the list's part."""

    template_name = "showcases/list.html"
    partial_template_name = "showcases/partials/showcase_list.html"
    listing = SHOWCASES
    list_id = "showcase-list"

    def get_listing_queryset(self):
        return (
            Showcase.objects.visible_to(self.request.user)
            .with_likes()
            .select_related("author__profile")
            .prefetch_related(TAGS_BY_NAME)
        )

    def get_list_url(self) -> str:
        return reverse("showcases:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        count = context["count"]
        tag = context["selection"].chosen.get("tag", "")
        context.update(
            text=strings,
            count_words=count_words(count, strings.SHOWCASES_COUNT, strings.SHOWCASES_COUNT_PLURAL),
            tagged=strings.TAGGED.format(tag=tag) if tag else "",
            empty=not count and not context["selection"].narrowed,
            rows=[
                {
                    "showcase": showcase,
                    "author": person(showcase.author),
                    "tags": list(showcase.tags.all()),
                    "likes": count_words(
                        showcase.like_count, strings.LIKE_COUNT, strings.LIKE_COUNT_PLURAL
                    ),
                }
                for showcase in context["page"]
            ],
        )
        return context


class ShowcaseDetailView(DetailView):
    """A showcase, for anyone (hidden ones for staff only)."""

    template_name = "showcases/detail.html"
    context_object_name = "showcase"

    def get_queryset(self):
        return (
            Showcase.objects.visible_to(self.request.user)
            .select_related("author__profile")
            .prefetch_related(TAGS_BY_NAME)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(showcase_context(self.request, self.object))
        return context


class ShowcaseFormMixin:
    """The publish and edit pages: the form and the words around it."""

    template_name = "showcases/form.html"

    def form_page(self, form: ShowcaseForm, **extra):
        mark_invalid(form)
        return render(self.request, self.template_name, {"text": strings, "form": form, **extra})


class ShowcaseCreateView(HtmxAwareMixin, VerifiedEmailRequiredMixin, ShowcaseFormMixin, View):
    """Publish a showcase (verified members, one a day). The page says so before the member
    chooses a file when they've reached the limit; the service decides."""

    def page(self, form: ShowcaseForm):
        return self.form_page(
            form,
            title=strings.CREATE_TITLE,
            lede=strings.CREATE_LEDE,
            submit=strings.PUBLISH,
            cancel_url=reverse("showcases:list"),
            limit=services.limit_message(self.request.user),
        )

    def get(self, request):
        return self.page(ShowcaseForm())

    def post(self, request):
        form = ShowcaseForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.page(form)
        try:
            showcase = services.create_showcase(request.user, **form.cleaned_data)
        except EmailNotVerified:
            return HttpResponseRedirect(verify_email_url())
        except LimitReached as error:
            form.add_error(None, str(error))
            return self.page(form)
        messages.success(request, strings.CREATED)
        return HttpResponseRedirect(showcase.get_absolute_url())


class ShowcaseEditView(
    HtmxAwareMixin, AuthorShowcaseMixin, VerifiedEmailRequiredMixin, ShowcaseFormMixin, View
):
    """Edit a showcase (its verified author only); a new image is optional. Its address
    stays the same."""

    def page(self, form: ShowcaseForm):
        return self.form_page(
            form,
            showcase=self.showcase,
            title=strings.EDIT_TITLE,
            lede="",
            submit=strings.SAVE,
            cancel_url=self.showcase.get_absolute_url(),
            limit="",
        )

    def get(self, request, slug):
        return self.page(
            ShowcaseForm(initial=ShowcaseForm.initial_for(self.showcase), editing=True)
        )

    def post(self, request, slug):
        form = ShowcaseForm(request.POST, request.FILES, editing=True)
        if not form.is_valid():
            return self.page(form)
        try:
            services.edit_showcase(request.user, self.showcase, **form.cleaned_data)
        except EmailNotVerified:
            return HttpResponseRedirect(verify_email_url())
        messages.success(request, strings.SAVED)
        return HttpResponseRedirect(self.showcase.get_absolute_url())


class ShowcaseDeleteView(HtmxAwareMixin, AuthorShowcaseMixin, View):
    """Delete a showcase (its author only) after confirming, then back to the list."""

    def get(self, request, slug):
        return render(
            request,
            "showcases/confirm_delete.html",
            {"text": strings, "showcase": self.showcase},
        )

    def post(self, request, slug):
        services.delete_showcase(request.user, self.showcase)
        messages.success(request, strings.DELETED)
        return HttpResponseRedirect(reverse("showcases:list"))


class LikeView(HtmxAwareMixin, PublishedShowcaseMixin, VerifiedEmailRequiredMixin, View):
    """Like a showcase (`action=like`) or take the like back (`action=unlike`). Through HTMX
    the like's part swaps in place; otherwise a redirect back to it."""

    http_method_names = ["post"]

    def post(self, request, slug):
        showcase = self.showcase
        action = request.POST.get("action", "")
        status, error = "", ""
        try:
            if action == "unlike":
                services.unlike(request.user, showcase)
                status = strings.UNLIKED
            elif action == "like":
                services.like(request.user, showcase)
                status = strings.LIKED
        except EmailNotVerified:
            return HttpResponseRedirect(verify_email_url())
        except services.LikeRefused as refused:
            error = str(refused)
        if request.htmx:
            context = like_context(
                request, showcase, swapped=True, like_status=status, like_error=error
            )
            return render(request, "showcases/partials/like.html", context)
        if error:
            messages.error(request, error)
        elif status:
            messages.success(request, status)
        return HttpResponseRedirect(f"{showcase.get_absolute_url()}#like")
