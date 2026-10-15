"""Tests for the ``website_analysis`` app.

All network/DNS boundaries are mocked: no test contacts the public
internet or performs real DNS resolution.
"""

import socket
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from business_profile.models import BusinessProfile

from .models import WebsiteAnalysis
from .services import AnalysisError, classify_link, validate_url_for_fetch

User = get_user_model()

HTML_FIXTURE = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>Acme Corp - Quality Products</title>
  <meta name="description" content="We sell quality products online.">
  <link rel="canonical" href="https://example.com/">
</head>
<body>
  <h1>Welcome to Acme</h1>
  <h2>Our Services</h2>
  <h3>Featured</h3>
  <a href="/products/widget">Buy our widget</a>
  <a href="/services/consulting">Consulting services</a>
  <a href="/blog/hello-world">Hello world post</a>
  <a href="/about-us">About our team</a>
  <a href="/random-page">Random</a>
  <a href="https://other.com/page">External site</a>
  <a href="mailto:info@example.com">Email us</a>
</body>
</html>
"""


def _addrinfo(*ips):
    """Build a fake getaddrinfo() result for the given IP strings."""
    results = []
    for ip in ips:
        if ":" in ip:
            results.append(
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, 0, 0, 0))
            )
        else:
            results.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)))
    return results


def make_response(
    url="https://example.com/",
    status=200,
    content_type="text/html; charset=utf-8",
    body=b"",
    content_length=None,
    is_redirect=False,
    location=None,
):
    response = mock.Mock()
    response.status_code = status
    response.is_redirect = is_redirect
    headers = {"Content-Type": content_type}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    if is_redirect:
        headers["Location"] = location
    response.headers = headers
    response.encoding = "utf-8"
    response.iter_content = lambda chunk_size=65536: [body] if body else []
    response.close = lambda: None
    response.url = url
    return response


class AnalysisTestBase(TestCase):
    """Base class with DNS and HTTP fully mocked (no real network)."""

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff", password="testpass123", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username="regular", password="testpass123", is_staff=False
        )
        getaddrinfo_patcher = mock.patch(
            "website_analysis.services.socket.getaddrinfo"
        )
        self.mock_getaddrinfo = getaddrinfo_patcher.start()
        self.addCleanup(getaddrinfo_patcher.stop)
        # Default: hostname resolves to a single public IP.
        self.mock_getaddrinfo.return_value = _addrinfo("93.184.216.34")

        session_patcher = mock.patch("website_analysis.services.requests.Session")
        self.mock_session_cls = session_patcher.start()
        self.addCleanup(session_patcher.stop)
        self.mock_session = mock.Mock()
        self.mock_session_cls.return_value = self.mock_session


class UrlValidationTests(AnalysisTestBase):
    def test_http_and_https_urls_are_accepted(self):
        self.assertEqual(
            validate_url_for_fetch("http://example.com"), "http://example.com/"
        )
        self.assertEqual(
            validate_url_for_fetch("https://example.com/page?q=1"),
            "https://example.com/page?q=1",
        )

    def test_invalid_schemes_are_rejected(self):
        for bad_url in (
            "ftp://example.com/file",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/html,<h1>x</h1>",
        ):
            with self.subTest(url=bad_url):
                with self.assertRaises(AnalysisError) as ctx:
                    validate_url_for_fetch(bad_url)
                self.assertEqual(ctx.exception.category, "invalid_url")

    def test_embedded_credentials_are_rejected(self):
        with self.assertRaises(AnalysisError) as ctx:
            validate_url_for_fetch("https://user:pass@example.com/")
        self.assertEqual(ctx.exception.category, "invalid_url")

    def test_loopback_and_private_destinations_are_rejected(self):
        for ip in (
            "127.0.0.1",
            "10.0.0.5",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "::1",
        ):
            with self.subTest(ip=ip):
                self.mock_getaddrinfo.return_value = _addrinfo(ip)
                with self.assertRaises(AnalysisError) as ctx:
                    validate_url_for_fetch("https://example.com/")
                self.assertEqual(ctx.exception.category, "disallowed_destination")

    def test_mixed_public_and_private_addresses_are_rejected(self):
        self.mock_getaddrinfo.return_value = _addrinfo("93.184.216.34", "10.0.0.1")
        with self.assertRaises(AnalysisError) as ctx:
            validate_url_for_fetch("https://example.com/")
        self.assertEqual(ctx.exception.category, "disallowed_destination")

    def test_unresolvable_hostname_is_rejected(self):
        self.mock_getaddrinfo.side_effect = socket.gaierror("nope")
        with self.assertRaises(AnalysisError) as ctx:
            validate_url_for_fetch("https://example.com/")
        self.assertEqual(ctx.exception.category, "dns_error")


class FetchBehaviorTests(AnalysisTestBase):
    def test_redirect_to_disallowed_destination_is_rejected(self):
        redirect = make_response(
            is_redirect=True, location="http://169.254.169.254/admin", status=302
        )
        self.mock_session.get.return_value = redirect
        self.mock_getaddrinfo.side_effect = [
            _addrinfo("93.184.216.34"),  # initial URL: public
            _addrinfo("169.254.169.254"),  # redirect target: link-local
        ]
        from .services import fetch_and_parse

        with self.assertRaises(AnalysisError) as ctx:
            fetch_and_parse("https://example.com/")
        self.assertEqual(ctx.exception.category, "disallowed_destination")

    def test_too_many_redirects_are_rejected(self):
        redirect = make_response(
            is_redirect=True, location="https://example.com/loop", status=302
        )
        self.mock_session.get.return_value = redirect
        from .services import fetch_and_parse

        with self.assertRaises(AnalysisError) as ctx:
            fetch_and_parse("https://example.com/")
        self.assertEqual(ctx.exception.category, "too_many_redirects")

    def test_oversized_response_is_rejected(self):
        response = make_response(content_length=100 * 1024 * 1024)
        self.mock_session.get.return_value = response
        from .services import fetch_and_parse

        with self.assertRaises(AnalysisError) as ctx:
            fetch_and_parse("https://example.com/")
        self.assertEqual(ctx.exception.category, "response_too_large")

    def test_non_html_response_is_rejected(self):
        response = make_response(content_type="application/pdf")
        self.mock_session.get.return_value = response
        from .services import fetch_and_parse

        with self.assertRaises(AnalysisError) as ctx:
            fetch_and_parse("https://example.com/")
        self.assertEqual(ctx.exception.category, "unsupported_content_type")

    def test_timeout_produces_safe_failure_record(self):
        self.mock_session.get.side_effect = requests.Timeout()
        analysis = WebsiteAnalysis.objects.create(
            submitted_url="https://example.com/"
        )
        from .services import run_analysis

        run_analysis(analysis)
        analysis.refresh_from_db()
        self.assertEqual(analysis.status, WebsiteAnalysis.STATUS_FAILED)
        self.assertEqual(analysis.error_category, "timeout")
        self.assertIsNotNone(analysis.completed_at)

    def test_network_error_produces_safe_failure_record(self):
        self.mock_session.get.side_effect = requests.ConnectionError("dns boom")
        analysis = WebsiteAnalysis.objects.create(
            submitted_url="https://example.com/"
        )
        from .services import run_analysis

        run_analysis(analysis)
        analysis.refresh_from_db()
        self.assertEqual(analysis.status, WebsiteAnalysis.STATUS_FAILED)
        self.assertEqual(analysis.error_category, "network_error")

    def test_metadata_and_headings_are_extracted(self):
        response = make_response(body=HTML_FIXTURE.encode("utf-8"))
        self.mock_session.get.return_value = response
        from .services import fetch_and_parse

        result = fetch_and_parse("https://example.com/")
        self.assertEqual(result.final_url, "https://example.com/")
        self.assertEqual(result.http_status, 200)
        self.assertEqual(result.title, "Acme Corp - Quality Products")
        self.assertEqual(result.meta_description, "We sell quality products online.")
        self.assertEqual(result.canonical_url, "https://example.com/")
        self.assertEqual(result.language, "en")
        self.assertEqual(
            result.headings, ["Welcome to Acme", "Our Services", "Featured"]
        )

    def test_same_site_links_are_classified_heuristically(self):
        response = make_response(body=HTML_FIXTURE.encode("utf-8"))
        self.mock_session.get.return_value = response
        from .services import fetch_and_parse

        result = fetch_and_parse("https://example.com/")
        by_url = {link["url"]: link["category"] for link in result.links}
        self.assertEqual(
            by_url["https://example.com/products/widget"], "likely_product"
        )
        self.assertEqual(
            by_url["https://example.com/services/consulting"], "likely_service"
        )
        self.assertEqual(
            by_url["https://example.com/blog/hello-world"], "likely_article"
        )
        self.assertEqual(by_url["https://example.com/about-us"], "likely_about")
        self.assertEqual(by_url["https://example.com/random-page"], "other")

    def test_external_links_are_not_treated_as_internal(self):
        response = make_response(body=HTML_FIXTURE.encode("utf-8"))
        self.mock_session.get.return_value = response
        from .services import fetch_and_parse

        result = fetch_and_parse("https://example.com/")
        urls = [link["url"] for link in result.links]
        self.assertNotIn("https://other.com/page", urls)
        self.assertEqual(len(urls), 5)

    def test_classify_link_unit(self):
        self.assertEqual(classify_link("/products/x", ""), "likely_product")
        self.assertEqual(classify_link("/services/y", ""), "likely_service")
        self.assertEqual(classify_link("/blog/z", ""), "likely_article")
        self.assertEqual(classify_link("/about", ""), "likely_about")
        self.assertEqual(classify_link("/something-else", "hello"), "other")


class WebsiteAnalysisViewTests(AnalysisTestBase):
    def setUp(self):
        super().setUp()
        self.url = reverse("website_analysis:analyze")

    def _mock_successful_fetch(self):
        self.mock_session.get.return_value = make_response(
            body=HTML_FIXTURE.encode("utf-8")
        )

    def test_staff_can_submit_valid_url(self):
        self._mock_successful_fetch()
        self.client.force_login(self.staff_user)
        response = self.client.post(self.url, {"url": "https://example.com"})
        analysis = WebsiteAnalysis.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], reverse("website_analysis:detail", args=[analysis.pk])
        )
        self.assertEqual(analysis.status, WebsiteAnalysis.STATUS_SUCCEEDED)
        self.assertEqual(analysis.title, "Acme Corp - Quality Products")
        self.assertEqual(len(analysis.links), 5)

    def test_anonymous_user_cannot_initiate_analysis(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])
        response = self.client.post(self.url, {"url": "https://example.com"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WebsiteAnalysis.objects.count(), 0)

    def test_non_staff_user_cannot_initiate_analysis(self):
        self.client.force_login(self.regular_user)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        response = self.client.post(self.url, {"url": "https://example.com"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WebsiteAnalysis.objects.count(), 0)

    def test_invalid_form_url_is_rejected_without_record(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(self.url, {"url": "not a url"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WebsiteAnalysis.objects.count(), 0)

    def test_failed_analysis_shows_safe_error_message(self):
        self.mock_session.get.side_effect = requests.Timeout()
        self.client.force_login(self.staff_user)
        response = self.client.post(self.url, {"url": "https://example.com"})
        analysis = WebsiteAnalysis.objects.get()
        self.assertEqual(response.status_code, 302)
        follow_up = self.client.get(
            reverse("website_analysis:detail", args=[analysis.pk])
        )
        self.assertEqual(follow_up.status_code, 200)
        self.assertContains(follow_up, "timeout")

    def test_business_website_is_shown_when_configured(self):
        BusinessProfile.objects.create(
            business_name="Acme",
            website_url="https://acme.example",
            content_language="en",
            timezone="UTC",
        )
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertContains(response, "https://acme.example")

    def test_detail_page_shows_metadata_and_classified_links(self):
        analysis = WebsiteAnalysis.objects.create(
            submitted_url="https://example.com/",
            final_url="https://example.com/",
            status=WebsiteAnalysis.STATUS_SUCCEEDED,
            http_status=200,
            title="Acme Corp",
            meta_description="We sell things.",
            detected_language="en",
            headings=["Welcome"],
            links=[
                {
                    "url": "https://example.com/products/x",
                    "text": "Buy",
                    "category": "likely_product",
                }
            ],
        )
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("website_analysis:detail", args=[analysis.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acme Corp")
        self.assertContains(response, "likely_product")
        self.assertContains(response, "heuristic")

    def test_detail_page_requires_staff(self):
        analysis = WebsiteAnalysis.objects.create(
            submitted_url="https://example.com/"
        )
        url = reverse("website_analysis:detail", args=[analysis.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.regular_user)
        self.assertEqual(self.client.get(url).status_code, 302)
