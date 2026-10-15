"""Catalog extraction services.

The initial extraction reuses internal links already stored on a
successful :class:`website_analysis.WebsiteAnalysis` report. This module
performs **no HTTP requests**: it only reads stored data, so it is safe
to run anywhere and trivially testable.
"""

import hashlib
import logging
from urllib.parse import urlsplit, urlunsplit

from .models import CatalogItem

logger = logging.getLogger(__name__)

MAX_LINKS_PER_RUN = 100
MAX_TITLE_LENGTH = 300

# Maps the heuristic link categories stored by the website_analysis app
# to catalog item types. Anything unrecognized stays "unknown": the
# extractor must not force a product/service label onto a guess.
CATEGORY_TO_ITEM_TYPE = {
    "likely_product": CatalogItem.ITEM_PRODUCT,
    "likely_service": CatalogItem.ITEM_SERVICE,
    "likely_article": CatalogItem.ITEM_ARTICLE,
}


def normalize_url(raw_url):
    """Normalize a URL for deduplication.

    Lowercases the scheme and host, drops the fragment, removes default
    ports, and strips a single trailing slash (except for the root path).
    Raises ``ValueError`` for unusable input.
    """
    url = (raw_url or "").strip()
    if not url:
        raise ValueError("empty URL")
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("unsupported scheme")
    hostname = parts.hostname
    if not hostname:
        raise ValueError("missing hostname")
    netloc = hostname.lower()
    if parts.port and not (
        (scheme == "http" and parts.port == 80)
        or (scheme == "https" and parts.port == 443)
    ):
        netloc = f"{netloc}:{parts.port}"
    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def url_key_for(normalized_url):
    """Return the stable deduplication key for a normalized URL."""
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


def suggest_item_type(stored_category):
    """Suggest a catalog item type from a stored link category.

    Pure function with simple, testable rules. Returns
    :attr:`CatalogItem.ITEM_UNKNOWN` for anything that cannot be
    determined, rather than forcing a product/service/article label.
    """
    return CATEGORY_TO_ITEM_TYPE.get(stored_category, CatalogItem.ITEM_UNKNOWN)


def _analysis_site_host(analysis):
    """Return the analysis site's hostname, or "" if it cannot be determined."""
    for candidate in (analysis.final_url, analysis.submitted_url):
        try:
            host = urlsplit(candidate or "").hostname
        except ValueError:
            continue
        if host:
            return host.lower()
    return ""


def extract_from_analysis(analysis, business, limit=MAX_LINKS_PER_RUN):
    """Create catalog items from a website-analysis report's stored links.

    - Only valid HTTP/HTTPS links on the analysis site's own hostname are
      considered; external or unusable URLs are skipped. Stored data is
      never trusted blindly.
    - Idempotent: existing items (matched by ``(business, url_key)``)
      are left untouched, so re-running never creates duplicates and
      never overwrites staff edits.
    - Bounded: at most ``limit`` links are processed per run.
    - Makes no network requests.

    Returns ``(created_count, skipped_count)``.
    """
    site_host = _analysis_site_host(analysis)
    created_count = 0
    skipped_count = 0
    for link in (analysis.links or [])[:limit]:
        raw_url = (link.get("url") or "").strip()
        try:
            normalized = normalize_url(raw_url)
        except ValueError:
            skipped_count += 1
            continue
        if not site_host or urlsplit(normalized).hostname.lower() != site_host:
            skipped_count += 1
            continue
        key = url_key_for(normalized)
        title = (link.get("text") or "").strip()[:MAX_TITLE_LENGTH] or normalized
        _item, was_created = CatalogItem.objects.get_or_create(
            business=business,
            url_key=key,
            defaults={
                "item_type": suggest_item_type(link.get("category")),
                "title": title,
                "source_url": normalized,
                "description": "",
                "review_status": CatalogItem.REVIEW_PENDING,
                "extraction_source": f"website_analysis:{analysis.pk}",
            },
        )
        if was_created:
            created_count += 1
        else:
            skipped_count += 1
    return created_count, skipped_count
