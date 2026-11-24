"""Documentation URLs (namespace "documentation"): the engine docs, served from the snapshot."""

from django.urls import path

from . import views

app_name = "documentation"

urlpatterns = [
    path("", views.DocsIndexView.as_view(), name="index"),
    # Before <path:path>/: no page may take this URL (Library.check refuses one that does).
    path("search/", views.DocsSearchView.as_view(), name="search"),
    path("<path:path>/", views.DocsPageView.as_view(), name="page"),
]
