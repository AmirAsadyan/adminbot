"""Tests for the ``setup_wizard`` placeholder (Task 02)."""

from django.test import TestCase
from django.urls import reverse


class SetupWizardPlaceholderTests(TestCase):
    def test_placeholder_page_returns_200(self):
        response = self.client.get(reverse("setup_wizard:placeholder"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "setup_wizard/placeholder.html")
        self.assertContains(response, "not implemented yet")

    def test_placeholder_is_read_only(self):
        # The placeholder must never change configuration: GET and POST
        # both render the same static page without side effects.
        get_response = self.client.get(reverse("setup_wizard:placeholder"))
        post_response = self.client.post(
            reverse("setup_wizard:placeholder"), {"key": "value"}
        )
        self.assertEqual(post_response.status_code, 200)
        self.assertEqual(get_response.content, post_response.content)
