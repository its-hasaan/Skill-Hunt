"""
Jobicy connector — https://jobicy.com/api/v2/remote-jobs

Free, no-key remote-jobs API. Supports filters via query params:
  count     max results (API caps ~50 per call)
  geo       e.g. 'anywhere', 'india', 'asia', 'usa'
  industry  e.g. 'dev', 'data-science'
  tag       free-text keyword

We loop over the configured `geos` so we can pull the 'anywhere' bucket plus
India-specific listings.
"""

from __future__ import annotations

from typing import Iterator, List

from .base import BaseConnector, NormalizedJob
from .utils import html_to_text, to_iso, detect_country_code, coerce_number

API_URL = "https://jobicy.com/api/v2/remote-jobs"

_CONTRACT_MAP = {
    "full-time": ("full_time", "permanent"),
    "part-time": ("part_time", "permanent"),
    "contract": ("contract", "temporary"),
    "freelance": ("contract", "temporary"),
    "internship": ("part_time", "temporary"),
}


class JobicyConnector(BaseConnector):
    name = "jobicy"
    requires_key = False

    def _geos(self) -> List[str]:
        geos = self.config.get("geos")
        return geos if geos else ["anywhere"]

    def fetch(self) -> Iterator[NormalizedJob]:
        count = int(self.config.get("count", 50))
        total = 0
        seen: set[str] = set()

        for geo in self._geos():
            params = {"count": count}
            if geo and geo != "anywhere":
                params["geo"] = geo
            payload = self._get_json(API_URL, params=params)
            self._sleep()
            if not payload:
                continue
            jobs = payload.get("jobs") if isinstance(payload, dict) else None
            if not jobs:
                continue

            for item in jobs:
                title = item.get("jobTitle") or ""
                industry = item.get("jobIndustry") or []
                role = self._match_role(title, industry)
                if not role:
                    continue

                ext_id = str(item.get("id") or item.get("jobSlug") or "").strip()
                if not ext_id or ext_id in seen:
                    continue
                seen.add(ext_id)

                geo_str = item.get("jobGeo") or ""
                job_types = item.get("jobType") or []
                ctype, ctime = ("", "")
                for jt in job_types:
                    key = str(jt).lower().replace(" ", "-")
                    if key in _CONTRACT_MAP:
                        ctype, ctime = _CONTRACT_MAP[key]
                        break

                yield NormalizedJob(
                    source=self.name,
                    external_id=ext_id,
                    search_role=role,
                    country_code=detect_country_code(geo_str),
                    title=title,
                    company_name=item.get("companyName") or "",
                    description=html_to_text(item.get("jobDescription") or item.get("jobExcerpt")),
                    redirect_url=item.get("url") or "",
                    location_display=geo_str or "Remote",
                    location_areas=[a for a in [geo_str] if a],
                    category_tag="it-jobs",
                    category_label="IT Jobs",
                    salary_min=coerce_number(item.get("salaryMin")),
                    salary_max=coerce_number(item.get("salaryMax")),
                    salary_currency=item.get("salaryCurrency") or "USD",
                    contract_type=ctype,
                    contract_time=ctime,
                    job_posted_at=to_iso(item.get("pubDate")),
                    raw={k: item.get(k) for k in ("id", "url", "jobGeo", "jobType", "pubDate", "jobIndustry")},
                )
                total += 1

        self.log.info("jobicy: yielded %d matching jobs", total)
