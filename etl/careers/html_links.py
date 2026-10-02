"""
Links on a career page: embedded hiring-system boards and job-detail pages.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urldefrag, urlparse

from ops.discover_companies import extract_tokens

_JOB_PATH = re.compile(r"/(?:jobs?|careers?|positions?|openings?|vacanc(?:y|ies)|opportunit(?:y|ies))/[^/?#]+",
                       re.IGNORECASE)


class _LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.urls.append(value.strip())


def extract_links(html: str, base_url: str) -> list[str]:
    collector = _LinkCollector()
    try:
        collector.feed(html or "")
    except Exception:  # noqa: BLE001 - malformed HTML: keep what was parsed
        pass
    links = []
    for raw in collector.urls:
        absolute, _ = urldefrag(urljoin(base_url, raw))
        if absolute.startswith(("http://", "https://")) and absolute not in links:
            links.append(absolute)
    return links


def ats_boards(html: str, base_url: str) -> dict[str, set[str]]:
    """Hiring-system boards linked or embedded on the page, by system."""
    return {ats: tokens for ats, tokens in extract_tokens(extract_links(html, base_url)).items() if tokens}


def _same_site(host: str, domain: str) -> bool:
    host = (host or "").lower()
    return host == domain or host.endswith("." + domain)


def job_links(links: list[str], domain: str, limit: int) -> list[str]:
    """Same-site links that look like job-detail pages, in page order."""
    found = []
    for link in links:
        parsed = urlparse(link)
        if _same_site(parsed.hostname, domain) and _JOB_PATH.search(parsed.path) and link not in found:
            found.append(link)
            if len(found) >= limit:
                break
    return found
