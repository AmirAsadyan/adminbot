"""URL routes for the ``setup_wizard`` app (Task 02: placeholder only)."""

from django.urls import path

from . import views

app_name = "setup_wizard"

urlpatterns = [
    path("", views.placeholder, name="placeholder"),
]
