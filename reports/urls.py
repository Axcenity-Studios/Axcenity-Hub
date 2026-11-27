"""Report URLs (namespace "reports"). Bug reports are addressed by pk under bugs/; reported
content by its kind and pk. The bug URLs come first: bugs/<pk>/ would otherwise read as a
report of content of kind "bugs"."""

from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("bugs/", views.BugListView.as_view(), name="bug_list"),
    path("bugs/new/", views.BugCreateView.as_view(), name="bug_create"),
    path("bugs/<int:pk>/", views.BugDetailView.as_view(), name="bug_detail"),
    path("bugs/<int:pk>/status/", views.BugStatusView.as_view(), name="bug_status"),
    path("bugs/<int:pk>/assign/", views.BugAssignView.as_view(), name="bug_assign"),
    path("bugs/<int:pk>/comment/", views.BugCommentView.as_view(), name="bug_comment"),
    path("<slug:kind>/<int:pk>/", views.ReportCreateView.as_view(), name="create"),
]
