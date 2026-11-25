"""Report URLs (namespace "reports"). Content is addressed by its kind and pk."""

from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("<slug:kind>/<int:pk>/", views.ReportCreateView.as_view(), name="create"),
]
