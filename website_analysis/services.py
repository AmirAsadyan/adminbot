"""Website fetching, SSRF protection, and HTML parsing services.

Security model
--------------
Website fetching is SSRF-sensitive, so this module is conservative:

- Only ``http`` and ``https`` URLs are accepted; embedded usernames or
  passwords are rejected.
- Every hostname is resolved and **all** resolved addresses must be
  globally routable (stdlib :mod:`ipaddress` ``is_global`` check, which
  rejects loopback, private, link-local, multicast, reserved, and
  unspecified addresses).
- Redirects are followed manually (never blindly): each redirect target
  is re-validated exactly like the initial URL, with a cap of
  ``MAX_REDIRECTS`` hops.
- Short connect/read timeouts, a response-size cap, HTML-only responses,
  a descriptive user agent, no cookies, no credentials, and ambient proxy
  configuration is ignored (``trust_env=False``).

Documented limitation — DNS rebinding (TOCTOU): hostnames are resolved
for validation, but the HTTP client resolves again when it connects, so
a malicious DNS server could in theory return different addresses
between the check and the request. Fully preventing this requires
socket-level IP pinning, which is out of scope for this increment; the
strict per-hop IP validation above still blocks the common attack cases.
Do not treat this module as complete SSRF protection.
"""

import ipaddress
import logging
import socket
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MiB
MAX_LINKS = 100
MAX_TITLE_LENGTH = 300
MAX_DESCRIPTION_LENGTH = 2000
MAX_HEADINGS = 20
MAX_HEADING_LENGTH = 200
MAX_ANCHOR_TEXT_LENGTH = 200
USER_AGENT = "AdminBot-WebsiteAnalyzer/1.0 (https://github.com/AmirAsadyan/adminbot)"


class AnalysisError(Exception):
    """A safe, user-presentable website-analysis failure.

    Carries a stable ``category`` string (suitable for storage) instead
    of stack traces or internal details.
    """

    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def _resolve_and_validate_host(hostname):
    """Resolve a hostname and require every address to be globally routable."""
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise AnalysisError("dns_error", "Could not resolve the website address.")
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise AnalysisError("dns_error", "Could not resolve the website address.")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise AnalysisError(
                "disallowed_destination", "The website destination is not allowed."
            )
        if not ip.is_global:
            raise AnalysisError(
                "disallowed_destination", "The website destination is not allowed."
            )


def validate_url_for_fetch(raw_url):
    """Validate a candidate URL and return its normalized absolute form.

    Raises :class:`AnalysisError` for anything that must not be fetched.
    """
    url = (raw_url or "").strip()
    if not url:
        raise AnalysisError("invalid_url", "Enter a website URL.")
    if len(url) > 2000:
        raise AnalysisError("invalid_url", "The URL is too long.")
    try:
        parts = urlsplit(url)
    except ValueError:
        raise AnalysisError("invalid_url", "The URL is not valid.")
    if parts.scheme.lower() not in ("http", "https"):
        raise AnalysisError("invalid_url", "Only HTTP and HTTPS URLs are allowed.")
    if parts.username or parts.password:
        raise AnalysisError(
            "invalid_url", "URLs with embedded credentials are not allowed."
        )
    hostname = parts.hostname
    if not hostname:
        raise AnalysisError("invalid_url", "The URL must include a hostname.")
    _resolve_and_validate_host(hostname)
    # Normalize: lowercase scheme/host, drop the fragment.
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, "")
    )


@dataclass
class FetchResult:
    """Parsed website data (never includes the raw HTML body)."""

    final_url: str
    http_status: int
    title: str = ""
    meta_description: str = ""
    canonical_url: str = ""
    language: str = ""
    headings: list = field(default_factory=list)
    links: list = field(default_factory=list)  # [{"url", "text", "category"}]


def classify_link(path, anchor_text):
    """Heuristically classify an internal link from its path and anchor text.

    These are guesses, not confirmed semantic labels, and may be wrong.
    """
    haystack = f"{path} {anchor_text}".lower()
    if any(k in haystack for k in ("product", "shop", "store", "/item/", "pricing", "buy")):
        return "likely_product"
    if any(k in haystack for k in ("service", "solution")):
        return "likely_service"
    if any(k in haystack for k in ("/blog", "blog", "article", "news", "/post")):
        return "likely_article"
    if any(k in haystack for k in ("about", "contact", "team", "company")):
        return "likely_about"
    return "other"


def _parse_html(html, base_url, http_status):
    soup = BeautifulSoup(html, "html.parser")
    base_host = (urlsplit(base_url).hostname or "").lower()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()[:MAX_TITLE_LENGTH]

    meta_description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        content = meta.get("content", "")
        if isinstance(content, str):
            meta_description = content.strip()[:MAX_DESCRIPTION_LENGTH]

    canonical_url = ""
    canonical = soup.find("link", rel="canonical")
    if canonical:
        href = (canonical.get("href") or "").strip()
        if href:
            absolute = urljoin(base_url, href).split("#")[0]
            cparts = urlsplit(absolute)
            if cparts.scheme in ("http", "https") and cparts.hostname:
                canonical_url = absolute

    language = ""
    html_tag = soup.find("html")
    if html_tag:
        lang = html_tag.get("lang", "")
        if isinstance(lang, str):
            language = lang.strip()[:20]

    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.get_text(separator=" ", strip=True)
        if text:
            headings.append(text[:MAX_HEADING_LENGTH])
        if len(headings) >= MAX_HEADINGS:
            break

    links = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith("#"):
            continue
        if href.lower().startswith(("javascript:", "mailto:", "tel:", "data:")):
            continue
        absolute = urljoin(base_url, href).split("#")[0]
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            continue
        # Strict same-hostname rule: external links are never internal.
        if parts.hostname.lower() != base_host:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        text = anchor.get_text(separator=" ", strip=True)[:MAX_ANCHOR_TEXT_LENGTH]
        links.append(
            {
                "url": absolute,
                "text": text,
                "category": classify_link(parts.path or "", text),
            }
        )
        if len(links) >= MAX_LINKS:
            break

    return FetchResult(
        final_url=base_url,
        http_status=http_status,
        title=title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        language=language,
        headings=headings,
        links=links,
    )


def fetch_and_parse(normalized_url):
    """Fetch a pre-validated URL (following validated redirects) and parse it.

    Raises :class:`AnalysisError` with a safe category on any failure.
    """
    session = requests.Session()
    # Ignore ambient proxy configuration: destinations are validated
    # by this module, and env proxies could bypass that validation.
    session.trust_env = False
    current_url = normalized_url
    response = None
    try:
        redirects_followed = 0
        while True:
            try:
                response = session.get(
                    current_url,
                    allow_redirects=False,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                    stream=True,
                )
            except requests.Timeout:
                raise AnalysisError(
                    "timeout", "The website took too long to respond."
                )
            except requests.RequestException:
                raise AnalysisError("network_error", "Could not reach the website.")

            if response.is_redirect:
                if redirects_followed >= MAX_REDIRECTS:
                    raise AnalysisError(
                        "too_many_redirects", "The website redirected too many times."
                    )
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise AnalysisError(
                        "invalid_url", "The website returned an invalid redirect."
                    )
                # Re-validate every redirect destination like the initial URL.
                current_url = validate_url_for_fetch(urljoin(current_url, location))
                redirects_followed += 1
                continue
            break

        http_status = response.status_code
        if not 200 <= http_status < 300:
            raise AnalysisError(
                "http_error", f"The website returned HTTP {http_status}."
            )

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower():
            raise AnalysisError(
                "unsupported_content_type",
                "The URL did not return an HTML page.",
            )

        declared_length = response.headers.get("Content-Length")
        if declared_length is not None:
            try:
                if int(declared_length) > MAX_RESPONSE_BYTES:
                    raise AnalysisError(
                        "response_too_large",
                        "The page is too large to analyze.",
                    )
            except (TypeError, ValueError):
                pass

        chunks = []
        total_bytes = 0
        try:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if total_bytes > MAX_RESPONSE_BYTES:
                    raise AnalysisError(
                        "response_too_large",
                        "The page is too large to analyze.",
                    )
                chunks.append(chunk)
        except requests.RequestException:
            raise AnalysisError(
                "network_error", "The connection was interrupted."
            )
        raw = b"".join(chunks)

        encoding = response.encoding or "utf-8"
        try:
            html = raw.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            html = raw.decode("utf-8", errors="replace")

        try:
            return _parse_html(html, current_url, http_status)
        except AnalysisError:
            raise
        except Exception:
            logger.exception("Website HTML parsing failed")
            raise AnalysisError("parse_error", "Could not parse the page.")
    finally:
        if response is not None:
            response.close()
        session.close()


def run_analysis(analysis):
    """Run the website analysis synchronously and update the record.

    Never raises: failures are recorded on the analysis with a safe
    error category, and unexpected exceptions are logged, never exposed.
    """
    from django.utils import timezone

    from .models import WebsiteAnalysis

    try:
        normalized = validate_url_for_fetch(analysis.submitted_url)
    except AnalysisError as exc:
        _mark_failed(analysis, exc.category)
        return analysis
    try:
        result = fetch_and_parse(normalized)
    except AnalysisError as exc:
        _mark_failed(analysis, exc.category)
        return analysis
    except Exception:
        logger.exception("Unexpected website analysis failure")
        _mark_failed(analysis, "internal_error")
        return analysis

    analysis.final_url = result.final_url
    analysis.http_status = result.http_status
    analysis.title = result.title
    analysis.meta_description = result.meta_description
    analysis.detected_language = result.language
    analysis.headings = result.headings
    analysis.links = result.links
    analysis.status = WebsiteAnalysis.STATUS_SUCCEEDED
    analysis.error_category = ""
    analysis.completed_at = timezone.now()
    analysis.save()
    return analysis


def _mark_failed(analysis, category):
    from django.utils import timezone

    analysis.status = type(analysis).STATUS_FAILED
    analysis.error_category = category
    analysis.completed_at = timezone.now()
    analysis.save()
