"""Views for the ``website_analysis`` app (staff users only)."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from business_profile.models import BusinessProfile

from .forms import WebsiteAnalysisForm
from .models import WebsiteAnalysis
from .services import run_analysis

# Safe, user-presentable messages per failure category. The raw
# exception text is never shown to users.
ERROR_MESSAGES = {
    "invalid_url": "The submitted URL is not valid.",
    "disallowed_destination": "The website destination is not allowed.",
    "dns_error": "Could not resolve the website address.",
    "too_many_redirects": "The website redirected too many times.",
    "timeout": "The website took too long to respond.",
    "network_error": "Could not reach the website.",
    "http_error": "The website returned an error response.",
    "response_too_large": "The page is too large to analyze.",
    "unsupported_content_type": "The URL did not return an HTML page.",
    "parse_error": "Could not parse the page.",
    "internal_error": "An unexpected error occurred while analyzing the website.",
}


@staff_member_required
def analyze(request):
    """Submit a website URL and list recent analysis reports."""
    business_website = ""
    profile = BusinessProfile.get_profile()
    if profile and profile.website_url:
        business_website = profile.website_url

    if request.method == "POST":
        form = WebsiteAnalysisForm(request.POST)
        if form.is_valid():
            analysis = WebsiteAnalysis.objects.create(
                submitted_url=form.cleaned_data["url"],
                status=WebsiteAnalysis.STATUS_PENDING,
            )
            # Bounded synchronous analysis (timeouts and size caps are
            # enforced in services); no background workers in this task.
            run_analysis(analysis)
            if analysis.status == WebsiteAnalysis.STATUS_SUCCEEDED:
                messages.success(request, "Website analysis completed successfully.")
            else:
                messages.error(
                    request,
                    ERROR_MESSAGES.get(
                        analysis.error_category, "Website analysis failed."
                    ),
                )
            return redirect("website_analysis:detail", pk=analysis.pk)
    else:
        form = WebsiteAnalysisForm(initial={"url": business_website})

    recent_analyses = WebsiteAnalysis.objects.all()[:20]
    return render(
        request,
        "website_analysis/analyze.html",
        {
            "form": form,
            "business_website": business_website,
            "recent_analyses": recent_analyses,
        },
    )


@staff_member_required
def detail(request, pk):
    """Show a single analysis report with its extracted data."""
    analysis = get_object_or_404(WebsiteAnalysis, pk=pk)
    return render(request, "website_analysis/detail.html", {"analysis": analysis})
