"""Documentation URLs (namespace "documentation"): the engine docs, served from the snapshot."""

from django.urls import path

from . import views

app_name = "documentation"

urlpatterns = [
    path("", views.DocsIndexView.as_view(), name="index"),
    path("<path:path>/", views.DocsPageView.as_view(), name="page"),
]
