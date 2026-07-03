"""
Generic HTML scraper template — DISABLED by default.

This is a *polite, compliance-first* scraper you can point ONLY at sites whose
Terms of Service and robots.txt permit automated access. It exists so you can
add a small local board that has no API — not to defeat anti-bot systems.

What it does (robust, sustainable):
  - Reads and OBEYS robots.txt for every URL before fetching it.
  - Rate-limits between requests and identifies itself honestly (real UA).
  - Extracts fields with CSS selectors you provide in config.

What it deliberately does NOT do (and won't be added):
  - Rotate residential proxies / spoof browser fingerprints to evade bot
    detection.
  - Solve CAPTCHAs or bypass login walls.
  - Scrape sites that forbid it (LinkedIn, Indeed, Rozee.pk, ...). For those,
    use their official/partner APIs or a licensed aggregator (Jooble/Adzuna
    already resell a lot of that inventory legally). See SCRAPING_BOTS.md.

Config block (in sources_config.json under sources.<name>):
  {
    "enabled": false,
    "connector": "generic_scraper",
    "base_url": "https://example-jobboard.com",
    "list_url": "https://example-jobboard.com/jobs?q={role}&page={page}",
    "max_pages": 3,
    "country_code": "pk",
    "selectors": {
      "item": "div.job-card",
      "title": "h2.job-title",
      "company": ".company-name",
      "location": ".job-location",
      "link": "a.job-link",           # href is read from this element
      "description": ".job-desc"       # optional; else the item text is used
    }
  }
"""

from __future__ import annotations

import urllib.parse
import urllib.robotparser
from typing import Iterator, Optional, Dict

from .base import BaseConnector, NormalizedJob
from .utils import html_to_text, detect_country_code


class GenericScraperConnector(BaseConnector):
    name = "generic_scraper"
    requires_key = False

    def __init__(self, config, role_matcher, logger_=None):
        super().__init__(config, role_matcher, logger_)
        self.base_url = config.get("base_url", "")
        self.list_url = config.get("list_url", "")
        self.max_pages = int(config.get("max_pages", 3))
        self.country_code = config.get("country_code", "remote")
        self.selectors: Dict[str, str] = config.get("selectors", {})
        self.roles = config.get("roles", [])
        self._robots: Optional[urllib.robotparser.RobotFileParser] = None

    def is_available(self) -> bool:
        if not self.list_url or not self.selectors.get("item"):
            self.log.warning("generic_scraper: missing `list_url` or `selectors.item` — skipping.")
            return False
        try:
            import bs4  # noqa: F401
        except ImportError:
            self.log.error("generic_scraper: needs beautifulsoup4 — pip install beautifulsoup4 lxml")
            return False
        return True

    def _robots_ok(self, url: str) -> bool:
        """Fetch (once) and honor robots.txt. Fail CLOSED: if we cannot
        confirm the path is allowed, we do not fetch it."""
        if self._robots is None:
            self._robots = urllib.robotparser.RobotFileParser()
            robots_url = urllib.parse.urljoin(self.base_url or url, "/robots.txt")
            try:
                txt = self._get_text(robots_url)
                if txt is None:
                    self.log.warning("generic_scraper: no robots.txt at %s — refusing to scrape.", robots_url)
                    self._robots.disallow_all = True
                else:
                    self._robots.parse(txt.splitlines())
            except Exception as e:
                self.log.warning("generic_scraper: robots.txt error (%s) — refusing to scrape.", e)
                self._robots.disallow_all = True
        ua = self.session.headers.get("User-Agent", "*")
        allowed = self._robots.can_fetch(ua, url)
        if not allowed:
            self.log.info("generic_scraper: robots.txt disallows %s — skipping.", url)
        return allowed

    def fetch(self) -> Iterator[NormalizedJob]:
        from bs4 import BeautifulSoup  # type: ignore

        roles = self.roles or [""]
        total = 0
        for role_query in roles:
            for page in range(1, self.max_pages + 1):
                url = self.list_url.format(role=urllib.parse.quote(role_query), page=page)
                if not self._robots_ok(url):
                    break
                html = self._get_text(url)
                self._sleep()
                if not html:
                    break
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select(self.selectors["item"])
                if not items:
                    break

                for el in items:
                    def pick(key: str) -> str:
                        sel = self.selectors.get(key)
                        if not sel:
                            return ""
                        node = el.select_one(sel)
                        return node.get_text(" ", strip=True) if node else ""

                    title = pick("title")
                    role = self._match_role(title) or (role_query if role_query in self.role_matcher.active else None)
                    if not role:
                        continue

                    link = ""
                    link_sel = self.selectors.get("link")
                    if link_sel:
                        a = el.select_one(link_sel)
                        if a and a.has_attr("href"):
                            link = urllib.parse.urljoin(self.base_url or url, a["href"])
                    if not link:
                        continue

                    location = pick("location")
                    desc_sel = self.selectors.get("description")
                    desc_node = el.select_one(desc_sel) if desc_sel else None
                    description = html_to_text(str(desc_node)) if desc_node else el.get_text(" ", strip=True)

                    yield NormalizedJob(
                        source=self.config.get("source_name", self.name),
                        external_id=link,  # URL is the stable id for scraped pages
                        search_role=role,
                        country_code=self.country_code or detect_country_code(location),
                        title=title,
                        company_name=pick("company"),
                        description=description,
                        redirect_url=link,
                        location_display=location or self.country_code,
                        location_areas=[a for a in [location] if a],
                        category_tag="it-jobs",
                        category_label="IT Jobs",
                        raw={"url": link, "scraped_from": url},
                    )
                    total += 1

        self.log.info("generic_scraper: yielded %d jobs", total)
