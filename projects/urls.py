"""Project URLs (namespace "projects")."""

from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("hooks/github/<uuid:hook_id>/", views.GitHubWebhookView.as_view(), name="webhook"),
    path("<slug:slug>/", views.ProjectDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", views.ProjectUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", views.ProjectDeleteView.as_view(), name="delete"),
    path(
        "<slug:slug>/repository/link/",
        views.LinkRepositoryView.as_view(),
        name="link_repository",
    ),
    path(
        "<slug:slug>/repository/unlink/",
        views.UnlinkRepositoryView.as_view(),
        name="unlink_repository",
    ),
    path(
        "<slug:slug>/repository/refresh/",
        views.RefreshRepositoryView.as_view(),
        name="refresh_repository",
    ),
]
