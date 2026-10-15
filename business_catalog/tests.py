"""Tests for the ``business_catalog`` app.

Extraction works purely on stored analysis data: no test performs
HTTP requests or DNS resolution.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from business_profile.models import BusinessProfile
from website_analysis.models import WebsiteAnalysis

from .models import CatalogItem
from .services import (
    extract_from_analysis,
    normalize_url,
    suggest_item_type,
    url_key_for,
)

User = get_user_model()


def make_business(name="Acme Corp"):
    return BusinessProfile.objects.create(
        business_name=name, content_language="en", timezone="UTC"
    )


def make_analysis(status=WebsiteAnalysis.STATUS_SUCCEEDED, links=None):
    if links is None:
        links = [
            {
                "url": "https://example.com/products/widget",
                "text": "Our widget",
                "category": "likely_product",
            },
            {
                "url": "https://example.com/services/consulting",
                "text": "Consulting",
                "category": "likely_service",
            },
            {
                "url": "https://example.com/blog/hello",
                "text": "Hello post",
                "category": "likely_article",
            },
            {
                "url": "https://example.com/about",
                "text": "About us",
                "category": "likely_about",
            },
            {
                "url": "https://example.com/random",
                "text": "Random page",
                "category": "other",
            },
        ]
    return WebsiteAnalysis.objects.create(
        submitted_url="https://example.com/",
        final_url="https://example.com/",
        status=status,
        http_status=200,
        links=links,
    )


class CatalogAccessTests(TestCase):
    def setUp(self):
        self.list_url = reverse("business_catalog:list")
        self.staff_user = User.objects.create_user(
            username="staff", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="testpass123", is_staff=False
        )
        self.business = make_business()
        self.item = CatalogItem.objects.create(
            business=self.business,
            item_type=CatalogItem.ITEM_PRODUCT,
            title="Widget",
            source_url="https://example.com/products/widget",
            url_key=url_key_for(normalize_url("https://example.com/products/widget")),
        )
        self.detail_url = reverse("business_catalog:detail", args=[self.item.pk])

    def test_anonymous_cannot_view_list_or_detail(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 302)

    def test_anonymous_cannot_trigger_extraction_or_edit(self):
        response = self.client.post(self.list_url, {"action": "extract"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CatalogItem.objects.count(), 1)
        response = self.client.post(
            self.detail_url, {"title": "Hacked", "item_type": "product"}
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, "Widget")

    def test_non_staff_cannot_view_or_modify(self):
        self.client.force_login(self.regular_user)
        self.assertEqual(self.client.get(self.list_url).status_code, 302)
        self.assertEqual(self.client.get(self.detail_url).status_code, 302)
        response = self.client.post(self.list_url, {"action": "extract"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CatalogItem.objects.count(), 1)

    def test_staff_can_view_list_and_detail(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Widget")
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://example.com/products/widget")


class CatalogListFilterTests(TestCase):
    def setUp(self):
        self.url = reverse("business_catalog:list")
        self.staff_user = User.objects.create_user(
            username="staff", password="testpass123", is_staff=True
        )
        self.client.force_login(self.staff_user)
        self.business = make_business()
        CatalogItem.objects.create(
            business=self.business,
            item_type=CatalogItem.ITEM_PRODUCT,
            title="Widget",
            source_url="https://example.com/products/widget",
            url_key=url_key_for(normalize_url("https://example.com/products/widget")),
            review_status=CatalogItem.REVIEW_APPROVED,
        )
        CatalogItem.objects.create(
            business=self.business,
            item_type=CatalogItem.ITEM_SERVICE,
            title="Consulting",
            source_url="https://example.com/services/consulting",
            url_key=url_key_for(
                normalize_url("https://example.com/services/consulting")
            ),
            review_status=CatalogItem.REVIEW_PENDING,
        )

    def test_filter_by_item_type(self):
        response = self.client.get(self.url, {"item_type": "product"})
        self.assertContains(response, "Widget")
        self.assertNotContains(response, "Consulting")

    def test_filter_by_review_status(self):
        response = self.client.get(self.url, {"review_status": "approved"})
        self.assertContains(response, "Widget")
        self.assertNotContains(response, "Consulting")

    def test_no_filter_shows_all(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Widget")
        self.assertContains(response, "Consulting")


class ExtractionViewTests(TestCase):
    def setUp(self):
        self.url = reverse("business_catalog:list")
        self.staff_user = User.objects.create_user(
            username="staff", password="testpass123", is_staff=True
        )
        self.client.force_login(self.staff_user)

    def test_extraction_without_business_profile_shows_error(self):
        make_analysis()
        response = self.client.post(self.url, {"action": "extract"})
        self.assertEqual(response.status_code, 302)
        follow_up = self.client.get(self.url)
        self.assertContains(follow_up, "business profile")
        self.assertEqual(CatalogItem.objects.count(), 0)

    def test_extraction_without_successful_analysis_shows_error(self):
        make_business()
        make_analysis(status=WebsiteAnalysis.STATUS_FAILED)
        response = self.client.post(self.url, {"action": "extract"})
        self.assertEqual(response.status_code, 302)
        follow_up = self.client.get(self.url)
        self.assertContains(follow_up, "No successful website analysis")
        self.assertEqual(CatalogItem.objects.count(), 0)

    def test_extraction_creates_items_from_latest_analysis(self):
        from datetime import timedelta

        from django.utils import timezone

        business = make_business()
        older = make_analysis()
        WebsiteAnalysis.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        latest = make_analysis(
            links=[
                {
                    "url": "https://example.com/products/new",
                    "text": "New product",
                    "category": "likely_product",
                }
            ]
        )
        response = self.client.post(self.url, {"action": "extract"})
        self.assertEqual(response.status_code, 302)
        items = CatalogItem.objects.filter(business=business)
        self.assertEqual(items.count(), 1)
        item = items.get()
        self.assertEqual(item.title, "New product")
        self.assertEqual(item.item_type, CatalogItem.ITEM_PRODUCT)
        self.assertEqual(item.review_status, CatalogItem.REVIEW_PENDING)
        self.assertEqual(item.extraction_source, f"website_analysis:{latest.pk}")
        follow_up = self.client.get(self.url)
        self.assertContains(follow_up, "1 new item")

    def test_extraction_skips_external_and_invalid_urls(self):
        business = make_business()
        make_analysis(
            links=[
                {"url": "https://other.com/page", "text": "Ext", "category": "other"},
                {"url": "javascript:alert(1)", "text": "JS", "category": "other"},
                {"url": "ftp://example.com/f", "text": "FTP", "category": "other"},
                {"url": "not a url", "text": "Bad", "category": "other"},
                {
                    "url": "https://example.com/ok",
                    "text": "OK",
                    "category": "other",
                },
            ]
        )
        self.client.post(self.url, {"action": "extract"})
        items = CatalogItem.objects.filter(business=business)
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.get().source_url, "https://example.com/ok")

    def test_rerun_does_not_create_duplicates(self):
        business = make_business()
        analysis = make_analysis()
        self.client.post(self.url, {"action": "extract"})
        self.assertEqual(CatalogItem.objects.filter(business=business).count(), 5)
        self.client.post(self.url, {"action": "extract"})
        self.assertEqual(CatalogItem.objects.filter(business=business).count(), 5)


class CatalogEditTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff", password="testpass123", is_staff=True
        )
        self.client.force_login(self.staff_user)
        self.business = make_business()
        self.item = CatalogItem.objects.create(
            business=self.business,
            item_type=CatalogItem.ITEM_UNKNOWN,
            title="Untitled",
            source_url="https://example.com/mystery",
            url_key=url_key_for(normalize_url("https://example.com/mystery")),
            review_status=CatalogItem.REVIEW_PENDING,
        )
        self.url = reverse("business_catalog:detail", args=[self.item.pk])

    def test_edit_title_type_description_and_status(self):
        response = self.client.post(
            self.url,
            {
                "title": "Consulting Service",
                "item_type": "service",
                "description": "We consult.",
                "review_status": "approved",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, "Consulting Service")
        self.assertEqual(self.item.item_type, CatalogItem.ITEM_SERVICE)
        self.assertEqual(self.item.description, "We consult.")
        self.assertEqual(self.item.review_status, CatalogItem.REVIEW_APPROVED)
        # Identity fields are untouched.
        self.assertEqual(self.item.source_url, "https://example.com/mystery")

    def test_edit_validation_errors_keep_existing_data(self):
        response = self.client.post(
            self.url,
            {"title": "", "item_type": "service", "review_status": "approved"},
        )
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, "Untitled")
        self.assertEqual(self.item.review_status, CatalogItem.REVIEW_PENDING)

    def test_reject_status_change(self):
        self.client.post(
            self.url,
            {
                "title": "Untitled",
                "item_type": "unknown",
                "review_status": "rejected",
            },
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.review_status, CatalogItem.REVIEW_REJECTED)


class CatalogServiceTests(TestCase):
    def test_normalize_url_dedup_variants(self):
        variants = [
            "https://example.com/page",
            "HTTPS://EXAMPLE.COM/page/",
            "https://example.com/page#section",
            "https://example.com:443/page",
        ]
        keys = {url_key_for(normalize_url(v)) for v in variants}
        self.assertEqual(len(keys), 1)

    def test_normalize_url_rejects_bad_input(self):
        for bad in ("", "not a url", "ftp://example.com/x", "https://"):
            with self.subTest(url=bad):
                with self.assertRaises(ValueError):
                    normalize_url(bad)

    def test_suggest_item_type_mapping(self):
        self.assertEqual(
            suggest_item_type("likely_product"), CatalogItem.ITEM_PRODUCT
        )
        self.assertEqual(
            suggest_item_type("likely_service"), CatalogItem.ITEM_SERVICE
        )
        self.assertEqual(
            suggest_item_type("likely_article"), CatalogItem.ITEM_ARTICLE
        )
        # Unknown or unrecognized categories stay unknown: never forced.
        self.assertEqual(
            suggest_item_type("likely_about"), CatalogItem.ITEM_UNKNOWN
        )
        self.assertEqual(suggest_item_type("other"), CatalogItem.ITEM_UNKNOWN)
        self.assertEqual(suggest_item_type(""), CatalogItem.ITEM_UNKNOWN)
        self.assertEqual(suggest_item_type(None), CatalogItem.ITEM_UNKNOWN)

    def test_database_unique_constraint_is_enforced(self):
        business = make_business()
        key = url_key_for(normalize_url("https://example.com/dup"))
        CatalogItem.objects.create(
            business=business,
            item_type=CatalogItem.ITEM_PRODUCT,
            title="First",
            source_url="https://example.com/dup",
            url_key=key,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CatalogItem.objects.create(
                    business=business,
                    item_type=CatalogItem.ITEM_PRODUCT,
                    title="Second",
                    source_url="https://example.com/dup",
                    url_key=key,
                )

    def test_unique_constraint_is_per_business(self):
        # The deduplication constraint is defined on (business, url_key),
        # so the same URL may legitimately appear under different
        # businesses in a multi-business future.
        constraint_names = [c.name for c in CatalogItem._meta.constraints]
        self.assertIn("unique_catalog_url_per_business", constraint_names)
        constraint = next(
            c
            for c in CatalogItem._meta.constraints
            if c.name == "unique_catalog_url_per_business"
        )
        self.assertEqual(set(constraint.fields), {"business", "url_key"})

    def test_extract_from_analysis_is_bounded(self):
        business = make_business()
        links = [
            {
                "url": f"https://example.com/page-{i}",
                "text": f"Page {i}",
                "category": "other",
            }
            for i in range(10)
        ]
        analysis = make_analysis(links=links)
        created, skipped = extract_from_analysis(analysis, business, limit=3)
        self.assertEqual(created, 3)
        self.assertEqual(skipped, 0)
        self.assertEqual(CatalogItem.objects.filter(business=business).count(), 3)
