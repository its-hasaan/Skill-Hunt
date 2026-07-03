"""
The Muse connector — https://www.themuse.com/api/public/jobs

Public jobs API. Works without a key (rate-limited); an optional free key
raises the limit — set THEMUSE_API_KEY. The Muse skews US/global with some
India coverage and a "Flexible / Remote" bucket, so it diversifies beyond the
dedicated remote boards.

Params: page, category (repeatable), level, location (repeatable), api_key.
Results carry no salary, so salary stays null.
"""

from __future__ import annotations

import os
from typing import Iterator, List

from .base import BaseConnector, NormalizedJob
from .utils import html_to_text, to_iso, detect_country_code

API_URL = "https://www.themuse.com/api/public/jobs"


class TheMuseConnector(BaseConnector):
    name = "themuse"
    requires_key = False  # works keyless, key only raises the rate limit

    def __init__(self, config, role_matcher, logger_=None):
        super().__init__(config, role_matcher, logger_)
        self.api_key = os.getenv(config.get("env_key", "THEMUSE_API_KEY"), "")
        self.max_pages = int(config.get("max_pages", 20))
        # Muse categories that overlap our roles (reduces noise before matching).
        self.categories: List[str] = config.get("categories", [
            "Software Engineering", "Data Science", "Data and Analytics", "IT",
        ])
        self.locations: List[str] = config.get("locations", ["Flexible / Remote", "India"])

    def fetch(self) -> Iterator[NormalizedJob]:
        total = 0
        seen: set[str] = set()

        for page in range(0, self.max_pages):
            params: list[tuple[str, str]] = [("page", str(page))]
            for c in self.categories:
                params.append(("category", c))
            for loc in self.locations:
                params.append(("location", loc))
            if self.api_key:
                params.append(("api_key", self.api_key))

            payload = self._get_json(API_URL, params=params)
            self._sleep()
            if not payload:
                break
            results = payload.get("results") if isinstance(payload, dict) else None
            if not results:
                break

            for item in results:
                title = item.get("name") or ""
                role = self._match_role(title)
                if not role:
                    continue

                ext_id = str(item.get("id") or "").strip()
                if not ext_id or ext_id in seen:
                    continue
                seen.add(ext_id)

                locations = [l.get("name", "") for l in (item.get("locations") or []) if isinstance(l, dict)]
                company = ""
                if isinstance(item.get("company"), dict):
                    company = item["company"].get("name", "")
                refs = item.get("refs") or {}

                yield NormalizedJob(
                    source=self.name,
                    external_id=ext_id,
                    search_role=role,
                    country_code=detect_country_code(" ".join(locations)),
                    title=title,
                    company_name=company,
                    description=html_to_text(item.get("contents")),
                    redirect_url=refs.get("landing_page", "") if isinstance(refs, dict) else "",
                    location_display=", ".join(locations) or "Remote",
                    location_areas=locations,
                    category_tag="it-jobs",
                    category_label="IT Jobs",
                    salary_currency="USD",
                    job_posted_at=to_iso(item.get("publication_date")),
                    raw={k: item.get(k) for k in ("id", "refs", "locations", "publication_date", "categories")},
                )
                total += 1

            page_count = payload.get("page_count") if isinstance(payload, dict) else None
            if page_count is not None and page >= page_count - 1:
                break

        self.log.info("themuse: yielded %d matching jobs", total)
