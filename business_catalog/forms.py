"""Forms for the ``business_catalog`` app."""

from django import forms

from .models import CatalogItem


class CatalogItemEditForm(forms.ModelForm):
    """Edit a catalog item's reviewable fields.

    Identity fields (business, source URL, deduplication key, extraction
    source) are intentionally not editable: they define what the item is.
    """

    class Meta:
        model = CatalogItem
        fields = ["title", "item_type", "description", "review_status"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class CatalogFilterForm(forms.Form):
    """Filter the catalog list by item type and review status."""

    item_type = forms.ChoiceField(
        choices=[("", "All types")] + CatalogItem.ITEM_TYPE_CHOICES,
        required=False,
    )
    review_status = forms.ChoiceField(
        choices=[("", "All statuses")] + CatalogItem.REVIEW_STATUS_CHOICES,
        required=False,
    )
