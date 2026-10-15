"""URL routes for the ``business_catalog`` app."""

from django.urls import path

from . import views

app_name = "business_catalog"

urlpatterns = [
    path("", views.item_list, name="list"),
    path("<int:pk>/", views.item_detail, name="detail"),
]
