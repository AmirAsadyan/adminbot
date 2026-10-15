"""Views for the ``setup_wizard`` app.

Task 02 scope: placeholder foundation only. The actual web-based setup
wizard will be implemented in a later task. This view intentionally
renders static information and performs no configuration changes:
it never writes files, executes commands, or creates user accounts.
"""

from django.shortcuts import render


def placeholder(request):
    """Render a static placeholder page for the future setup wizard."""
    return render(request, "setup_wizard/placeholder.html")
