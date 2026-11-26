"""Forum pages, in the app shell.

Anyone may read the list and a post. Writing a post needs a verified member; editing and
deleting one are its author's alone. For anyone else (another member, an admin who isn't the
author, a signed-out visitor) the edit and delete URLs are a 404, never a 403, found before
anything else runs, so they reveal nothing.

A post's page also holds its rating and its comments. Rating, commenting and deleting your
own comment work in place too; reporting is a page of its own (reports.views).

On a post's page, Edit and Delete work in place through HTMX: the view answers an HTMX
request (`request.htmx`, django-htmx) with the part of the page that changes, and any other
request with the whole page or a redirect, so every action works without JavaScript too.
Responses that differ by the `HX-Request` header say so in `Vary`.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views import View
from django.views.generic import DetailView, FormView, TemplateView
from django_htmx.http import HttpResponseClientRedirect

from accounts.access import EmailNotVerified, VerifiedEmailRequiredMixin, verify_email_url
from accounts.limits import LimitReached
from config.listing import ListingMixin
from reports.moderation import Visibility, is_published
from reports.services import has_reported, reported_ids

from . import services, strings
from .forms import CommentForm, PostForm
from .listing import POSTS
from .models import Comment, ForumPost, Rating


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


def count_words(count: int, one: str, many: str) -> str:
    return (one if count == 1 else many).format(count=count)


def rating_context(request, post: ForumPost) -> dict:
    """The post's rating as its part of the page shows it: the average (one decimal) and
    count, the visitor's own rating, and whether they may rate (signed in, not the author,
    the post visible)."""
    user = request.user
    stats = Rating.objects.filter(post=post).aggregate(count=Count("pk"), average=Avg("score"))
    mine = None
    if user.is_authenticated:
        mine = Rating.objects.filter(post=post, user=user).values_list("score", flat=True).first()
    count = stats["count"]
    return {
        "count": count,
        "average": (
            strings.RATING_AVERAGE.format(average=f"{stats['average']:.1f}") if count else ""
        ),
        "count_words": count_words(count, strings.RATING_COUNT, strings.RATING_COUNT_PLURAL),
        "mine": mine,
        "can_rate": user.is_authenticated and not post.is_author(user) and is_published(post),
        "stars": [
            {
                "score": score,
                "label": strings.RATE_STAR.format(score=score),
                "on": bool(mine) and score <= mine,
                "pressed": mine == score,
            }
            for score in range(Rating.LOWEST, Rating.HIGHEST + 1)
        ],
    }


def post_context(request, post: ForumPost, **extra) -> dict:
    """What the post's part of the page needs: the post, its author, whether the visitor
    wrote it (only then are Edit and Delete shown), its rating, and whether they may report
    it."""
    user = request.user
    is_author = post.is_author(user)
    can_report = user.is_authenticated and not is_author and is_published(post)
    return {
        "text": strings,
        "post": post,
        "author": person(post.author),
        "is_author": is_author,
        "rating": rating_context(request, post),
        "can_report": can_report,
        "reported": can_report and has_reported(user, post),
        **extra,
    }


def comment_row(request, comment: Comment, reported: set[int], *, post_open: bool, **extra) -> dict:
    """One comment as `forums/partials/comment.html` shows it. `post_open`: whether its post
    is published (so the comment may be reported if it is too)."""
    user = request.user
    is_author = comment.is_author(user)
    comment_open = post_open and comment.state == Visibility.VISIBLE
    return {
        "comment": comment,
        "author": person(comment.author),
        "is_author": is_author,
        "can_report": user.is_authenticated and not is_author and comment_open,
        "reported": comment.pk in reported,
        **extra,
    }


def comments_context(request, post: ForumPost, *, form=None, focus=None, **extra) -> dict:
    """What the comments' part of the page needs: the comments the visitor may see, oldest
    first, and the form (a fresh one unless `form` is given). `focus` is the pk of a
    comment to focus after a swap."""
    comments = list(
        Comment.objects.visible_to(request.user).filter(post=post).select_related("author__profile")
    )
    reported = reported_ids(request.user, Comment, [c.pk for c in comments])
    post_open = is_published(post)
    return {
        "text": strings,
        "post": post,
        "comments": [
            comment_row(request, c, reported, post_open=post_open, focus=c.pk == focus)
            for c in comments
        ],
        "comment_count": count_words(
            len(comments), strings.COMMENTS_COUNT, strings.COMMENTS_COUNT_PLURAL
        ),
        "comment_form": form or CommentForm(),
        "comments_open": post_open,
        **extra,
    }


def mark_invalid(form) -> None:
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
            ForumPost.objects.visible_to(request.user).authored_by(request.user), pk=kwargs["pk"]
        )
        return super().dispatch(request, *args, **kwargs)


class PostListView(ListingMixin, TemplateView):
    """The posts the visitor may see, 20 a page: searched, filtered and ordered by the query
    string (forums.listing), newest first without one. An HTMX request gets the list's part."""

    template_name = "forums/list.html"
    partial_template_name = "forums/partials/post_list.html"
    listing = POSTS
    list_id = "post-list"

    def get_listing_queryset(self):
        user = self.request.user
        return ForumPost.objects.visible_to(user).with_stats(user).select_related("author__profile")

    def get_list_url(self) -> str:
        return reverse("forums:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        count = context["count"]
        context.update(
            text=strings,
            count_words=count_words(count, strings.POSTS_COUNT, strings.POSTS_COUNT_PLURAL),
            # No posts at all (nothing to search yet), or none that match.
            empty=not count and not context["selection"].narrowed,
            rows=[
                {
                    "post": post,
                    "author": person(post.author),
                    "comments": count_words(
                        post.comment_count, strings.COMMENTS_COUNT, strings.COMMENTS_COUNT_PLURAL
                    ),
                    "rating": f"{post.rating_average:.1f}" if post.rating_count else "",
                    "rating_words": strings.RATING_AVERAGE.format(
                        average=f"{post.rating_average:.1f}"
                    )
                    if post.rating_count
                    else "",
                }
                for post in context["page"]
            ],
        )
        return context


class PostDetailView(HtmxAwareMixin, DetailView):
    """A post, for anyone. An HTMX request (Cancel while editing) gets the post's part of
    the page, with its heading focused."""

    template_name = "forums/detail.html"

    def get_queryset(self):
        return ForumPost.objects.visible_to(self.request.user).select_related("author__profile")

    def get(self, request, *args, **kwargs):
        if request.htmx:
            post = self.get_object()
            return render(
                request, "forums/partials/post.html", post_context(request, post, swapped=True)
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(comments_context(self.request, self.object))
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
        except LimitReached as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
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


class PostedPostMixin:
    """The post named by the URL, if anyone may interact with it (comment on it, rate it);
    a 404 otherwise, before any other check runs."""

    def dispatch(self, request, *args, **kwargs):
        self.post_object = get_object_or_404(
            ForumPost.objects.published().select_related("author__profile"), pk=kwargs["pk"]
        )
        return super().dispatch(request, *args, **kwargs)


class CommentCreateView(HtmxAwareMixin, PostedPostMixin, VerifiedEmailRequiredMixin, View):
    """Comment on a post (verified members). Through HTMX the comments swap in place with
    the new one focused, or the form with what to fix; otherwise a redirect to the comment,
    or the post's page with the form's errors."""

    http_method_names = ["post"]

    def post(self, request, pk):
        post = self.post_object
        form = CommentForm(request.POST)
        comment = None
        if form.is_valid():
            try:
                comment = services.add_comment(request.user, post, **form.cleaned_data)
            except EmailNotVerified:
                return HttpResponseRedirect(verify_email_url())
            except LimitReached as error:
                form.add_error(None, str(error))
            except ValidationError as error:
                form.add_error("body", error.messages)
        if comment is None:
            mark_invalid(form)
            form.fields["body"].widget.attrs["autofocus"] = True
            if request.htmx:
                return render(
                    request,
                    "forums/partials/comments.html",
                    comments_context(request, post, form=form, swapped=True),
                )
            context = {**comments_context(request, post, form=form), **post_context(request, post)}
            context["object"] = post
            return render(request, "forums/detail.html", context)
        if request.htmx:
            return render(
                request,
                "forums/partials/comments.html",
                comments_context(
                    request, post, focus=comment.pk, swapped=True, status=strings.COMMENTED
                ),
            )
        messages.success(request, strings.COMMENTED)
        return HttpResponseRedirect(comment.get_absolute_url())


class CommentView(HtmxAwareMixin, View):
    """A comment: through HTMX its part of the page (Keep it, after Delete), focused;
    otherwise a redirect to it on its post's page."""

    def get(self, request, pk):
        comment = get_object_or_404(
            Comment.objects.visible_to(request.user).select_related("post", "author__profile"),
            pk=pk,
        )
        if not request.htmx:
            return HttpResponseRedirect(comment.get_absolute_url())
        reported = reported_ids(request.user, Comment, [comment.pk])
        row = comment_row(
            request, comment, reported, post_open=is_published(comment.post), focus=True
        )
        return render(request, "forums/partials/comment.html", {"text": strings, **row})


class AuthorCommentMixin:
    """The comment named by the URL, if the caller wrote it; a 404 otherwise, for a
    signed-out visitor too, before any other check can run."""

    def dispatch(self, request, *args, **kwargs):
        self.comment = get_object_or_404(
            Comment.objects.visible_to(request.user)
            .authored_by(request.user)
            .select_related("post"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)


class CommentDeleteView(HtmxAwareMixin, AuthorCommentMixin, View):
    """Delete a comment (its author only) after confirming: in place through HTMX, or a
    confirmation page and a redirect to the post."""

    def get(self, request, pk):
        context = {"text": strings, "comment": self.comment, "swapped": bool(request.htmx)}
        if request.htmx:
            return render(request, "forums/partials/comment_confirm_delete.html", context)
        return render(request, "forums/comment_confirm_delete.html", context)

    def post(self, request, pk):
        post = self.comment.post
        services.delete_comment(request.user, self.comment)
        if request.htmx:
            return render(
                request,
                "forums/partials/comments.html",
                comments_context(
                    request, post, swapped=True, focus_heading=True, status=strings.COMMENT_DELETED
                ),
            )
        messages.success(request, strings.COMMENT_DELETED)
        return HttpResponseRedirect(f"{post.get_absolute_url()}#comments")


SCORES = {str(score) for score in range(Rating.LOWEST, Rating.HIGHEST + 1)}


class RateView(HtmxAwareMixin, PostedPostMixin, VerifiedEmailRequiredMixin, View):
    """Rate a post 1 to 5, or clear your rating (`score=clear`). Through HTMX the rating
    swaps in place; otherwise a redirect back to it."""

    http_method_names = ["post"]

    def post(self, request, pk):
        post = self.post_object
        raw = request.POST.get("score", "")
        status, error, focus = "", "", None
        try:
            if raw == "clear":
                services.clear_rating(request.user, post)
                status, focus = strings.RATING_CLEARED, Rating.LOWEST
            else:
                # Only "1" to "5": not "٣" (a digit to isdigit) or " 3".
                score = int(raw) if raw in SCORES else -1
                services.rate_post(request.user, post, score)
                status, focus = strings.RATED, score
        except EmailNotVerified:
            return HttpResponseRedirect(verify_email_url())
        except services.RatingRefused as refused:
            error = str(refused)
        except ValidationError:
            error = strings.RATING_OUT_OF_RANGE
        if request.htmx:
            context = post_context(request, post, rating_status=status, rating_error=error)
            context["focus_star"] = focus
            return render(request, "forums/partials/rating.html", context)
        if error:
            messages.error(request, error)
        else:
            messages.success(request, status)
        return HttpResponseRedirect(f"{post.get_absolute_url()}#rating")
