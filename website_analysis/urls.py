"""URL routes for the ``website_analysis`` app."""

from django.urls import path

from . import views

app_name = "website_analysis"

urlpatterns = [
    path("", views.analyze, name="analyze"),
    path("<int:pk>/", views.detail, name="detail"),
]
