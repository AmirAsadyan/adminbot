"""URL routes for the ``business_profile`` app."""

from django.urls import path

from . import views

app_name = "business_profile"

urlpatterns = [
    path("", views.edit_profile, name="edit"),
]
