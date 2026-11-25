"""Forum URLs (namespace "forums"). Posts and comments are addressed by their pk."""

from django.urls import path

from . import views

app_name = "forums"

urlpatterns = [
    path("", views.PostListView.as_view(), name="list"),
    path("new/", views.PostCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PostDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.PostEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.PostDeleteView.as_view(), name="delete"),
    path("<int:pk>/comments/", views.CommentCreateView.as_view(), name="comment_create"),
    path("<int:pk>/rate/", views.RateView.as_view(), name="rate"),
    path("comments/<int:pk>/", views.CommentView.as_view(), name="comment"),
    path("comments/<int:pk>/delete/", views.CommentDeleteView.as_view(), name="comment_delete"),
]
