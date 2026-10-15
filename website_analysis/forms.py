"""Forms for the ``website_analysis`` app."""

from django import forms


class WebsiteAnalysisForm(forms.Form):
    """Submit a website URL for analysis.

    Django's own URL validation runs first; the SSRF-safe validation in
    :mod:`website_analysis.services` always runs again server-side and
    is the authoritative gate before any network request.
    """

    url = forms.URLField(
        max_length=2000,
        label="Website URL",
        assume_scheme="https",
        widget=forms.URLInput(
            attrs={"placeholder": "https://example.com", "size": 60}
        ),
    )
