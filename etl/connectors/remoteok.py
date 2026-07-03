"""
RemoteOK connector — https://remoteok.com/api

Public JSON feed of remote tech jobs. No API key. The first array element is
a legal/attribution notice and is skipped. RemoteOK's terms require linking
back to the job URL on RemoteOK and crediting them as the source — our
`redirect_url` is exactly that RemoteOK job URL, so we comply.

RemoteOK rejects the default python-requests User-Agent, so `build_session`
sets a real one.
"""

from __future__ import annotations

from typing import Iterator

from .base import BaseConnector, NormalizedJob
from .utils import html_to_text, to_iso, detect_country_code

API_URL = "https://remoteok.com/api"


class RemoteOKConnector(BaseConnector):
    name = "remoteok"
    requires_key = False

    def fetch(self) -> Iterator[NormalizedJob]:
        max_jobs = int(self.config.get("max_jobs", 500))
        data = self._get_json(API_URL)
        self._sleep()
        if not isinstance(data, list):
            self.log.warning("remoteok: unexpected payload type %s", type(data))
            return

        count = 0
        for item in data:
            if not isinstance(item, dict) or item.get("legal"):
                continue  # skip the leading legal notice
            ext_id = str(item.get("id") or item.get("slug") or "").strip()
            if not ext_id:
                continue

            title = item.get("position") or item.get("title") or ""
            # Title ONLY — RemoteOK auto-tags are noise (non-tech posts carry
            # tags like 'infosec'/'dev'), so they cannot be trusted for roles.
            role = self._match_role(title)
            if not role:
                continue  # not one of our tracked roles

            location = item.get("location") or ""
            salary_min = item.get("salary_min") or None
            salary_max = item.get("salary_max") or None

            yield NormalizedJob(
                source=self.name,
                external_id=ext_id,
                search_role=role,
                country_code=detect_country_code(location),
                title=title,
                company_name=item.get("company") or "",
                description=html_to_text(item.get("description")),
                redirect_url=item.get("url") or f"https://remoteok.com/remote-jobs/{ext_id}",
                location_display=location or "Remote",
                location_areas=[a for a in [location] if a],
                category_tag="it-jobs",
                category_label="IT Jobs",
                salary_min=float(salary_min) if salary_min else None,
                salary_max=float(salary_max) if salary_max else None,
                salary_currency="USD",
                contract_type="full_time",
                job_posted_at=to_iso(item.get("date") or item.get("epoch")),
                raw=item,
            )
            count += 1
            if count >= max_jobs:
                break

        self.log.info("remoteok: yielded %d matching jobs", count)
