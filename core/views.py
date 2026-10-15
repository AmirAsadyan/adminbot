"""Views for the ``core`` app (Task 01: foundation only)."""

from django.http import JsonResponse
from django.shortcuts import render


def home(request):
    """Render the minimal landing page."""
    return render(request, "core/home.html")


def health_check(request):
    """Return a simple success response.

    Deliberately static: it must never expose secrets, configuration
    values, or Django debug information.
    """
    return JsonResponse({"status": "ok"})
