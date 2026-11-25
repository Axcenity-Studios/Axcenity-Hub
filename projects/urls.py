"""Project URLs (namespace "projects")."""

from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("hooks/github/<uuid:hook_id>/", views.GitHubWebhookView.as_view(), name="webhook"),
    path(
        "invitations/<int:pk>/accept/",
        views.InvitationAcceptView.as_view(),
        name="accept_invitation",
    ),
    path(
        "invitations/<int:pk>/decline/",
        views.InvitationDeclineView.as_view(),
        name="decline_invitation",
    ),
    path("<slug:slug>/", views.ProjectDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", views.ProjectUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", views.ProjectDeleteView.as_view(), name="delete"),
    path("<slug:slug>/members/", views.MembersView.as_view(), name="members"),
    path("<slug:slug>/members/invite/", views.InviteView.as_view(), name="invite"),
    path("<slug:slug>/members/search/", views.MemberSearchView.as_view(), name="member_search"),
    path(
        "<slug:slug>/members/<int:pk>/role/",
        views.MemberRoleView.as_view(),
        name="change_role",
    ),
    path(
        "<slug:slug>/members/<int:pk>/remove/",
        views.MemberRemoveView.as_view(),
        name="remove_member",
    ),
    path(
        "<slug:slug>/invitations/<int:pk>/cancel/",
        views.InvitationCancelView.as_view(),
        name="cancel_invitation",
    ),
    path("<slug:slug>/leave/", views.LeaveView.as_view(), name="leave"),
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
