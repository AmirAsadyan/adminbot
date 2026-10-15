"""Automated tests for the ``core`` app (Task 01: foundation only)."""

from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_returns_200_and_uses_template(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")
        self.assertContains(response, "AdminBot")


class HealthCheckTests(TestCase):
    def test_health_check_returns_ok_json(self):
        response = self.client.get(reverse("core:health-check"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_check_does_not_expose_internals(self):
        response = self.client.get(reverse("core:health-check"))
        body = response.content.decode().lower()
        self.assertNotIn("secret", body)
        self.assertNotIn("debug", body)
        self.assertNotIn("database", body)
