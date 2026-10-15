"""Stored website-analysis records."""

from django.db import models


class WebsiteAnalysis(models.Model):
    """A single website-analysis attempt and its extracted data.

    Only bounded, extracted metadata is stored — never full HTML pages
    or arbitrary response bodies. ``links`` and ``headings`` use
    :class:`~django.db.models.JSONField`, which works on both SQLite
    and PostgreSQL.
    """

    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    ]

    submitted_url = models.URLField(max_length=2000)
    final_url = models.URLField(max_length=2000, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    http_status = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=300, blank=True, default="")
    meta_description = models.TextField(blank=True, default="")
    detected_language = models.CharField(max_length=20, blank=True, default="")
    headings = models.JSONField(default=list, blank=True)
    links = models.JSONField(
        default=list,
        blank=True,
        help_text="Bounded list of classified same-site links.",
    )
    error_category = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Safe failure category; never a stack trace.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.submitted_url} ({self.status})"
