"""Automated tests for the ``core`` app."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


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


class SystemStatusTests(TestCase):
    def setUp(self):
        self.url = reverse("core:system-status")
        self.staff_user = User.objects.create_user(
            username="staff", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="testpass123", is_staff=False
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_non_staff_user_is_redirected_to_login(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_staff_user_sees_status_page(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/system_status.html")
        self.assertContains(response, "Operational")
        self.assertContains(response, "Reachable")

    @mock.patch("core.views.connection")
    def test_database_error_returns_503_without_leaking_details(
        self, mock_connection
    ):
        mock_connection.ensure_connection.side_effect = DatabaseError(
            "connection refused by secret-host"
        )
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Degraded", status_code=503)
        self.assertContains(response, "Unavailable", status_code=503)
        body = response.content.decode().lower()
        self.assertNotIn("secret-host", body)
        self.assertNotIn("traceback", body)
