"""What members can report, and how a report finds its target.

Each kind of reportable content is a `Target`, addressed in report URLs by its `kind`
(`/reports/post/<pk>/`, `/reports/showcase/<pk>/`). The set is fixed: an unknown kind is a 404. A target is found only
among content anyone may interact with (`published()`): hidden or removed content, or a
comment on a hidden post, is a 404, as is the reporter's own content.
"""

from collections.abc import Callable
from dataclasses import dataclass

from django.db.models import Model, QuerySet

from forums.models import Comment, ForumPost
from showcases.models import Showcase


@dataclass(frozen=True)
class Target:
    kind: str  # its name in report URLs
    label: str  # what the pages call it: "post"
    queryset: Callable[[], QuerySet]
    title: Callable[[Model], str]  # how the report page names it

    def find(self, reporter, pk: int) -> Model:
        """The content `reporter` may report: published, and not their own. Raises the
        model's DoesNotExist (the view's 404) otherwise."""
        found = self.queryset()
        if getattr(reporter, "is_authenticated", False):
            found = found.exclude(author=reporter)
        return found.get(pk=pk)


TARGETS: dict[str, Target] = {
    target.kind: target
    for target in [
        Target(
            "post",
            "post",
            lambda: ForumPost.objects.published(),
            lambda post: post.title,
        ),
        Target(
            "comment",
            "comment",
            lambda: Comment.objects.published().select_related("post"),
            lambda comment: comment.body,
        ),
        Target(
            "showcase",
            "showcase",
            lambda: Showcase.objects.published(),
            lambda showcase: showcase.title,
        ),
    ]
}


def target_kind(obj: Model) -> str:
    """The report URL's kind for `obj`."""
    for target in TARGETS.values():
        if isinstance(obj, target.queryset().model):
            return target.kind
    raise LookupError(f"{type(obj).__name__} can't be reported")
