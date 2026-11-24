"""Marketing URLs (namespace "marketing")."""

from django.urls import path

from . import views

app_name = "marketing"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("toolbox/", views.ToolboxView.as_view(), name="toolbox"),
    path("theme/", views.ThemeView.as_view(), name="theme"),
]
