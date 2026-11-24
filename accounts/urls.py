"""Accounts URLs (namespace "accounts"). allauth's own pages are mounted beside these at
/accounts/ under its un-namespaced names (account_login, account_signup, ...)."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify_email"),
]

# Replace allauth's own pages (same URLs and names), mounted ahead of allauth's URLs in
# config/urls.py: the email page (status and resend only, accounts.views.EmailView), the
# connections page, and the GitHub start, which only ever links (never signs in).
allauth_overrides = [
    path("email/", views.EmailView.as_view(), name="account_email"),
    path("3rdparty/", views.ConnectionsView.as_view(), name="socialaccount_connections"),
    path("github/login/", views.GitHubConnectView.as_view(), name="github_login"),
]
