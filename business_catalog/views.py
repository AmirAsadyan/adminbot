"""Views for the ``business_catalog`` app (staff users only)."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from business_profile.models import BusinessProfile
from website_analysis.models import WebsiteAnalysis

from .forms import CatalogFilterForm, CatalogItemEditForm
from .models import CatalogItem
from .services import extract_from_analysis


@staff_member_required
def item_list(request):
    """List catalog items with filters, and run the initial extraction."""
    if request.method == "POST" and request.POST.get("action") == "extract":
        return _run_extraction(request)

    items = CatalogItem.objects.select_related("business").all()
    filter_form = CatalogFilterForm(request.GET)
    if filter_form.is_valid():
        item_type = filter_form.cleaned_data["item_type"]
        review_status = filter_form.cleaned_data["review_status"]
        if item_type:
            items = items.filter(item_type=item_type)
        if review_status:
            items = items.filter(review_status=review_status)

    return render(
        request,
        "business_catalog/list.html",
        {
            "items": items[:200],
            "filter_form": filter_form,
            "total_count": CatalogItem.objects.count(),
        },
    )


def _run_extraction(request):
    """Run the initial extraction from the latest successful analysis."""
    business = BusinessProfile.get_profile()
    if business is None:
        messages.error(
            request,
            "Create the business profile first before extracting the catalog.",
        )
        return redirect("business_catalog:list")

    analysis = (
        WebsiteAnalysis.objects.filter(status=WebsiteAnalysis.STATUS_SUCCEEDED)
        .order_by("-created_at")
        .first()
    )
    if analysis is None:
        messages.error(
            request,
            "No successful website analysis found. Run a website analysis first.",
        )
        return redirect("business_catalog:list")

    created_count, skipped_count = extract_from_analysis(analysis, business)
    messages.success(
        request,
        f"Extraction finished: {created_count} new item(s), "
        f"{skipped_count} skipped (already in catalog or unusable).",
    )
    return redirect("business_catalog:list")


@staff_member_required
def item_detail(request, pk):
    """Show a catalog item and allow editing its reviewable fields."""
    item = get_object_or_404(CatalogItem, pk=pk)
    if request.method == "POST":
        form = CatalogItemEditForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Catalog item updated successfully.")
            return redirect("business_catalog:detail", pk=item.pk)
    else:
        form = CatalogItemEditForm(instance=item)
    return render(
        request, "business_catalog/detail.html", {"item": item, "form": form}
    )
