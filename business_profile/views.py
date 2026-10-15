"""Views for the ``business_profile`` app."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render

from .forms import BusinessProfileForm
from .models import BusinessProfile


@staff_member_required
def edit_profile(request):
    """Create or edit the single business profile (staff users only).

    Uses the Post/Redirect/Get pattern: a valid POST saves the profile
    and redirects with a success message; an invalid POST re-renders the
    form with field-level errors and leaves the stored profile untouched.
    """
    profile = BusinessProfile.get_profile()
    if request.method == "POST":
        form = BusinessProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Business profile saved successfully.")
            return redirect("business_profile:edit")
    else:
        form = BusinessProfileForm(instance=profile)
    return render(
        request,
        "business_profile/edit.html",
        {"form": form, "profile": profile},
    )
