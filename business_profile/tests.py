"""Tests for the ``business_profile`` app."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BusinessProfile

User = get_user_model()


class BusinessProfileAccessTests(TestCase):
    def setUp(self):
        self.url = reverse("business_profile:edit")
        self.staff_user = User.objects.create_user(
            username="staff", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="testpass123", is_staff=False
        )

    def test_anonymous_user_cannot_access_profile_page(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_anonymous_user_cannot_modify_profile(self):
        response = self.client.post(self.url, {"business_name": "Acme"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BusinessProfile.objects.count(), 0)

    def test_non_staff_user_cannot_access_or_modify_profile(self):
        self.client.force_login(self.regular_user)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        response = self.client.post(self.url, {"business_name": "Acme"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BusinessProfile.objects.count(), 0)

    def test_staff_user_can_open_profile_page(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "business_profile/edit.html")


class BusinessProfileFormTests(TestCase):
    def setUp(self):
        self.url = reverse("business_profile:edit")
        self.staff_user = User.objects.create_user(
            username="staff", password="testpass123", is_staff=True
        )
        self.client.force_login(self.staff_user)

    def valid_data(self, **overrides):
        data = {
            "business_name": "Acme Corp",
            "industry": "Retail",
            "description": "We sell things.",
            "website_url": "https://example.com",
            "content_language": "en",
            "timezone": "UTC",
            "brand_slogan": "Quality first",
            "use_brand_slogan": "on",
        }
        data.update(overrides)
        return data

    def test_staff_can_create_profile(self):
        response = self.client.post(self.url, self.valid_data())
        self.assertEqual(response.status_code, 302)
        profile = BusinessProfile.get_profile()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.business_name, "Acme Corp")
        self.assertTrue(profile.use_brand_slogan)
        follow_up = self.client.get(self.url)
        self.assertContains(follow_up, "saved successfully")

    def test_staff_can_update_existing_profile(self):
        BusinessProfile.objects.create(
            business_name="Old name", content_language="en", timezone="UTC"
        )
        response = self.client.post(
            self.url, self.valid_data(business_name="New name")
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BusinessProfile.objects.count(), 1)
        self.assertEqual(BusinessProfile.get_profile().business_name, "New name")

    def test_business_name_is_required(self):
        response = self.client.post(self.url, self.valid_data(business_name=""))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "business_name", ["This field is required."]
        )
        # The stored profile (none yet) is left untouched.
        self.assertEqual(BusinessProfile.objects.count(), 0)

    def test_invalid_website_url_is_rejected(self):
        response = self.client.post(
            self.url, self.valid_data(website_url="not-a-url")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "website_url", ["Enter a valid URL."]
        )
        self.assertEqual(BusinessProfile.objects.count(), 0)

    def test_invalid_timezone_is_rejected(self):
        response = self.client.post(
            self.url, self.valid_data(timezone="Mars/Olympus")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "timezone",
            ["Enter a valid IANA timezone identifier, e.g. Asia/Tehran."],
        )
        self.assertEqual(BusinessProfile.objects.count(), 0)

    def test_disabling_slogan_toggle_preserves_slogan_text(self):
        BusinessProfile.objects.create(
            business_name="Acme Corp",
            brand_slogan="Quality first",
            use_brand_slogan=True,
            content_language="en",
            timezone="UTC",
        )
        # An unchecked checkbox is omitted from the POST data entirely.
        data = self.valid_data(brand_slogan="Quality first")
        del data["use_brand_slogan"]
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        profile = BusinessProfile.get_profile()
        self.assertFalse(profile.use_brand_slogan)
        self.assertEqual(profile.brand_slogan, "Quality first")

    def test_clearing_slogan_does_not_affect_other_fields(self):
        BusinessProfile.objects.create(
            business_name="Acme Corp",
            industry="Retail",
            brand_slogan="Quality first",
            use_brand_slogan=True,
            content_language="en",
            timezone="UTC",
        )
        data = self.valid_data(brand_slogan="", industry="Retail")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        profile = BusinessProfile.get_profile()
        self.assertEqual(profile.brand_slogan, "")
        self.assertEqual(profile.industry, "Retail")
        self.assertEqual(profile.business_name, "Acme Corp")

    def test_only_one_profile_can_exist_per_installation(self):
        BusinessProfile.objects.create(
            business_name="First", content_language="en", timezone="UTC"
        )
        BusinessProfile.objects.create(
            business_name="Second", content_language="en", timezone="UTC"
        )
        self.assertEqual(BusinessProfile.objects.count(), 1)
        self.assertEqual(BusinessProfile.get_profile().business_name, "Second")

    def test_get_profile_returns_none_when_missing(self):
        self.assertIsNone(BusinessProfile.get_profile())
