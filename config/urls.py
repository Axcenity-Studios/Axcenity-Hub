"""Root URLs. Each app has its own namespace."""

from django.contrib import admin
from django.urls import include, path

from accounts.urls import allauth_overrides

urlpatterns = [
    path("admin/", admin.site.urls),
    # The Hub's account pages first, then allauth's (sign-in, sign-up, reset, two-factor).
    path("accounts/", include("accounts.urls")),
    path("accounts/", include(allauth_overrides)),
    path("accounts/", include("allauth.urls")),
    path("docs/", include("documentation.urls")),
    path("projects/", include("projects.urls")),
    path("", include("marketing.urls")),
]
