"""Business catalog models.

The catalog holds products, services, and articles discovered from the
business website (see the ``website_analysis`` app). This is a
single-business application: every item belongs to the installation's
single :class:`business_profile.BusinessProfile`.
"""

from django.db import models


class CatalogItem(models.Model):
    """A single catalog entry (product, service, or article).

    Deduplication: ``url_key`` is the SHA-256 hex digest of the
    normalized source URL, and the database enforces uniqueness of
    ``(business, url_key)``. A fixed-length hash keeps the unique index
    portable across SQLite and PostgreSQL regardless of URL length.
    """

    ITEM_PRODUCT = "product"
    ITEM_SERVICE = "service"
    ITEM_ARTICLE = "article"
    ITEM_UNKNOWN = "unknown"
    ITEM_TYPE_CHOICES = [
        (ITEM_PRODUCT, "Product"),
        (ITEM_SERVICE, "Service"),
        (ITEM_ARTICLE, "Article"),
        (ITEM_UNKNOWN, "Unknown"),
    ]

    REVIEW_PENDING = "pending"
    REVIEW_APPROVED = "approved"
    REVIEW_REJECTED = "rejected"
    REVIEW_STATUS_CHOICES = [
        (REVIEW_PENDING, "Pending review"),
        (REVIEW_APPROVED, "Approved"),
        (REVIEW_REJECTED, "Rejected"),
    ]

    business = models.ForeignKey(
        "business_profile.BusinessProfile",
        on_delete=models.CASCADE,
        related_name="catalog_items",
    )
    item_type = models.CharField(
        max_length=20, choices=ITEM_TYPE_CHOICES, default=ITEM_UNKNOWN
    )
    title = models.CharField(max_length=300)
    source_url = models.URLField(max_length=2000)
    url_key = models.CharField(
        max_length=64,
        help_text="SHA-256 of the normalized source URL; used for deduplication.",
    )
    description = models.TextField(blank=True, default="")
    review_status = models.CharField(
        max_length=20, choices=REVIEW_STATUS_CHOICES, default=REVIEW_PENDING
    )
    extraction_source = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "url_key"],
                name="unique_catalog_url_per_business",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_item_type_display()})"
