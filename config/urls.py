"""Root URL configuration for the AdminBot project."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("setup/", include("setup_wizard.urls")),
    path("business-profile/", include("business_profile.urls")),
    path("website-analysis/", include("website_analysis.urls")),
    path("", include("core.urls")),
]
