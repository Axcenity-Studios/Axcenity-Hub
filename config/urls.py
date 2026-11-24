"""Root URLs. Each app has its own namespace."""

from django.contrib import admin
from django.urls import include, path

from accounts.urls import allauth_overrides
from config import errors

# Every error status renders the Hub's own page (config/errors.py).
handler400 = "config.errors.bad_request"
handler403 = "config.errors.permission_denied"
handler404 = "config.errors.page_not_found"
handler500 = "config.errors.server_error"
handler429 = "config.errors.too_many_requests"  # allauth's rate limits

urlpatterns = [
    path("admin/", admin.site.urls),
    # The Hub's account pages first, then allauth's (sign-in, sign-up, reset, two-factor).
    path("accounts/", include("accounts.urls")),
    path("accounts/", include(allauth_overrides)),
    path("accounts/", include("allauth.urls")),
    path("docs/", include("documentation.urls")),
    path("projects/", include("projects.urls")),
    # A development server's preview of each error page (a 404 when DEBUG is off).
    path(
        "errors/",
        include(([path("<slug:kind>/", errors.preview, name="preview")], "errors")),
    ),
    path("", include("marketing.urls")),
]
