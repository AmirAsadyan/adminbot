"""Business profile model for this installation.

Single-business design: this is a self-hosted, single-business
application, so exactly one profile may exist per installation.
The singleton is enforced by pinning the primary key to a constant
value on save, which is portable across SQLite and PostgreSQL
without extra database constraints or a tenant model.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import models


class BusinessProfile(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("fa", "Persian (Farsi)"),
        ("ar", "Arabic"),
        ("tr", "Turkish"),
        ("fr", "French"),
        ("de", "German"),
        ("es", "Spanish"),
    ]

    SINGLETON_PK = 1

    business_name = models.CharField(max_length=200)
    industry = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    website_url = models.URLField(max_length=500, blank=True, default="")
    content_language = models.CharField(
        max_length=10, choices=LANGUAGE_CHOICES, default="en"
    )
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="IANA timezone identifier, e.g. Asia/Tehran.",
    )
    brand_slogan = models.CharField(max_length=255, blank=True, default="")
    use_brand_slogan = models.BooleanField(
        default=True,
        help_text=(
            "When enabled, future content generation may use the saved slogan. "
            "Disabling it never deletes the saved slogan text."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValidationError(
                {"timezone": "Enter a valid IANA timezone identifier, e.g. Asia/Tehran."}
            )

    def save(self, *args, **kwargs):
        # Pin the primary key so only one profile row can ever exist.
        # When the singleton row already exists, turn the save into an
        # UPDATE (even when called via QuerySet.create(), which forces
        # an INSERT) instead of attempting a duplicate INSERT.
        self.pk = self.SINGLETON_PK
        manager = type(self)._default_manager
        if manager.filter(pk=self.pk).exists():
            kwargs.pop("force_insert", None)
            kwargs["force_update"] = True
            # A forced UPDATE on a fresh instance would otherwise write
            # NULL into auto_now_add columns, so keep the stored value.
            self.created_at = manager.values_list("created_at", flat=True).get(
                pk=self.pk
            )
        super().save(*args, **kwargs)

    @classmethod
    def get_profile(cls):
        """Return the single business profile, or None if not created yet."""
        return cls.objects.filter(pk=cls.SINGLETON_PK).first()

    def __str__(self):
        return self.business_name
