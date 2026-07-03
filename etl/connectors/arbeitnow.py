"""
Arbeitnow connector — https://www.arbeitnow.com/api/job-board-api

Free, no-key job-board API (paginated). Arbeitnow is EU/Germany-centric with a
mix of on-site and remote roles. On-site EU roles are not relevant to the
Pakistan/India remote focus, so we keep only `remote == true` postings and
bucket them under 'remote'.
"""

from __future__ import annotations

from typing import Iterator

from .base import BaseConnector, NormalizedJob
from .utils import html_to_text, to_iso, detect_country_code

API_URL = "https://www.arbeitnow.com/api/job-board-api"

_CONTRACT_KEYWORDS = {
    "full": ("full_time", "permanent"),
    "part": ("part_time", "permanent"),
    "contract": ("contract", "temporary"),
    "freelance": ("contract", "temporary"),
    "intern": ("part_time", "temporary"),
}


def _map_contract(job_types) -> tuple[str, str]:
    for jt in (job_types or []):
        low = str(jt).lower()
        for kw, val in _CONTRACT_KEYWORDS.items():
            if kw in low:
                return val
    return ("", "")


class ArbeitnowConnector(BaseConnector):
    name = "arbeitnow"
    requires_key = False

    def fetch(self) -> Iterator[NormalizedJob]:
        max_pages = int(self.config.get("max_pages", 10))
        remote_only = bool(self.config.get("remote_only", True))
        total = 0

        for page in range(1, max_pages + 1):
            payload = self._get_json(API_URL, params={"page": page})
            self._sleep()
            if not payload:
                break
            jobs = payload.get("data") if isinstance(payload, dict) else None
            if not jobs:
                break

            for item in jobs:
                if remote_only and not item.get("remote"):
                    continue
                title = item.get("title") or ""
                tags = item.get("tags") or []
                role = self._match_role(title, tags)
                if not role:
                    continue

                ext_id = str(item.get("slug") or "").strip()
                if not ext_id:
                    continue

                location = item.get("location") or ""
                ctype, ctime = _map_contract(item.get("job_types"))

                yield NormalizedJob(
                    source=self.name,
                    external_id=ext_id,
                    search_role=role,
                    country_code=detect_country_code(location) if not item.get("remote") else "remote",
                    title=title,
                    company_name=item.get("company_name") or "",
                    description=html_to_text(item.get("description")),
                    redirect_url=item.get("url") or "",
                    location_display=location or "Remote",
                    location_areas=[a for a in [location] if a],
                    category_tag="it-jobs",
                    category_label="IT Jobs",
                    contract_type=ctype,
                    contract_time=ctime,
                    salary_currency="EUR",
                    job_posted_at=to_iso(item.get("created_at")),
                    raw={k: item.get(k) for k in ("slug", "url", "remote", "location", "created_at", "job_types")},
                )
                total += 1

            # If the API returns a `meta.last_page`, stop when we hit it.
            meta = payload.get("meta") if isinstance(payload, dict) else None
            if meta and meta.get("current_page") and meta.get("last_page"):
                if meta["current_page"] >= meta["last_page"]:
                    break

        self.log.info("arbeitnow: yielded %d matching jobs", total)
