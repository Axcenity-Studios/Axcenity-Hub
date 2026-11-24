"""URLs for the contribution-gate tests: the site's URLs plus one stand-in
contribution view (nothing in the Hub posts, creates or reports yet; Phases 10-14 will).
"""

from django.http import HttpResponse
from django.urls import path
from django.views import View

from accounts.access import VerifiedEmailRequiredMixin
from config import urls as site_urls

# What the stand-in view did, so a test can see that a refused request changed nothing.
CONTRIBUTIONS: list[int] = []


class ContributeView(VerifiedEmailRequiredMixin, View):
    """Stands in for any create, post or report view."""

    def get(self, request):
        return HttpResponse("the create form")

    def post(self, request):
        CONTRIBUTIONS.append(request.user.pk)
        return HttpResponse("created")


# The site's real URLs, plus the stand-in.
urlpatterns = [
    path("contribute/", ContributeView.as_view(), name="contribute"),
    *site_urls.urlpatterns,
]
