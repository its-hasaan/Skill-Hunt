"""
We Work Remotely connector — RSS feeds.

WeWorkRemotely publishes public RSS feeds (RSS is an explicit "please consume
me programmatically" contract). We read the main feed plus optional
category feeds. No API key.

  main:     https://weworkremotely.com/remote-jobs.rss
  category: https://weworkremotely.com/categories/<slug>.rss

Item title format is "Company Name: Job Title".
"""

from __future__ import annotations

from typing import Iterator, List

from .base import BaseConnector, NormalizedJob
from .utils import html_to_text, to_iso, detect_country_code

MAIN_FEED = "https://weworkremotely.com/remote-jobs.rss"
CATEGORY_FEED = "https://weworkremotely.com/categories/{slug}.rss"

_CONTRACT_MAP = {
    "full-time": ("full_time", "permanent"),
    "full time": ("full_time", "permanent"),
    "part-time": ("part_time", "permanent"),
    "part time": ("part_time", "permanent"),
    "contract": ("contract", "temporary"),
    "freelance": ("contract", "temporary"),
}


class WeWorkRemotelyConnector(BaseConnector):
    name = "weworkremotely"
    requires_key = False

    def _feed_urls(self) -> List[str]:
        slugs = self.config.get("feeds") or []
        if not slugs:
            return [MAIN_FEED]
        return [CATEGORY_FEED.format(slug=s) for s in slugs]

    def fetch(self) -> Iterator[NormalizedJob]:
        try:
            import feedparser  # type: ignore
        except ImportError:
            self.log.error("weworkremotely: `feedparser` not installed — skipping. "
                           "Run: pip install feedparser")
            return

        seen: set[str] = set()
        total = 0
        for url in self._feed_urls():
            xml = self._get_text(url)
            self._sleep()
            if not xml:
                continue
            feed = feedparser.parse(xml)
            for entry in feed.entries:
                title_raw = entry.get("title", "")
                if ":" in title_raw:
                    company, _, position = title_raw.partition(":")
                    company, position = company.strip(), position.strip()
                else:
                    company, position = "", title_raw.strip()

                # Match on the TITLE only. The WWR category ("Front-End
                # Programming", ...) is too coarse — non-dev roles appear in
                # dev feeds and would be misclassified by the category string.
                role = self._match_role(position)
                if not role:
                    continue

                link = entry.get("link", "")
                ext_id = (entry.get("id") or link or f"{company}:{position}").strip()
                if ext_id in seen:
                    continue
                seen.add(ext_id)

                region = entry.get("region", "") or entry.get("state", "")
                ctype, ctime = _CONTRACT_MAP.get(str(entry.get("type", "")).lower(), ("", ""))

                yield NormalizedJob(
                    source=self.name,
                    external_id=ext_id,
                    search_role=role,
                    country_code=detect_country_code(region),
                    title=position,
                    company_name=company,
                    description=html_to_text(entry.get("summary") or entry.get("description")),
                    redirect_url=link,
                    location_display=region or "Remote",
                    location_areas=[a for a in [region] if a],
                    category_tag="it-jobs",
                    category_label=entry.get("category", "IT Jobs") or "IT Jobs",
                    contract_type=ctype,
                    contract_time=ctime,
                    salary_currency="USD",
                    job_posted_at=to_iso(entry.get("published") or entry.get("updated")),
                    raw={k: entry.get(k) for k in ("title", "link", "published", "region", "type", "category")},
                )
                total += 1

        self.log.info("weworkremotely: yielded %d matching jobs", total)
