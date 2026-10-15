"""Views for the ``core`` app."""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db import DatabaseError, connection
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


@staff_member_required
def system_status(request):
    """Render a simple system-status page for staff users only.

    Shows only safe, coarse-grained information:

    - overall application status
    - whether the configured database is reachable
    - whether Django is running in debug mode

    The database is probed with Django's connection API and failures
    are handled gracefully: no exception messages, environment
    variables, secret values, filesystem paths, or stack traces are
    ever exposed. Returns HTTP 503 when the database is unreachable.
    """
    try:
        connection.ensure_connection()
        database_ok = True
    except DatabaseError:
        database_ok = False

    context = {
        "app_status": "ok" if database_ok else "degraded",
        "database_ok": database_ok,
        "debug_mode": settings.DEBUG,
    }
    status_code = 200 if database_ok else 503
    return render(request, "core/system_status.html", context, status=status_code)
