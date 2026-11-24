"""Accounts URLs (namespace "accounts"). allauth's own pages are mounted beside these at
/accounts/ under its un-namespaced names (account_login, account_signup, ...)."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify_email"),
]

# Replaces allauth's own email page (same URL and name), mounted ahead of allauth's
# URLs in config/urls.py: status and resend only (see accounts.views.EmailView).
allauth_overrides = [
    path("email/", views.EmailView.as_view(), name="account_email"),
]
