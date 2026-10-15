"""Forms for the ``business_profile`` app."""

from django import forms

from .models import BusinessProfile


class BusinessProfileForm(forms.ModelForm):
    """Create or edit the single business profile.

    The slogan text (``brand_slogan``) and the ``use_brand_slogan``
    toggle are independent fields: unchecking the toggle submits
    ``False`` without touching the saved slogan text.
    """

    class Meta:
        model = BusinessProfile
        fields = [
            "business_name",
            "industry",
            "description",
            "website_url",
            "content_language",
            "timezone",
            "brand_slogan",
            "use_brand_slogan",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
