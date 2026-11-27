"""Showcase URLs (namespace "showcases"). Showcases are addressed by their slug."""

from django.urls import path

from . import views

app_name = "showcases"

urlpatterns = [
    path("", views.ShowcaseListView.as_view(), name="list"),
    path("new/", views.ShowcaseCreateView.as_view(), name="create"),
    path("<slug:slug>/", views.ShowcaseDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", views.ShowcaseEditView.as_view(), name="edit"),
    path("<slug:slug>/delete/", views.ShowcaseDeleteView.as_view(), name="delete"),
    path("<slug:slug>/like/", views.LikeView.as_view(), name="like"),
]
