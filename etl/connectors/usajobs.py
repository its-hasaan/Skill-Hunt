"""
USAJobs connector — https://data.usajobs.gov/api/search

Official US federal government jobs API (an example of the "government labor
API" category). US-only, so it does not directly serve the Pakistan/India
focus — it is included as a solid, fully-compliant government source and is
DISABLED by default in sources_config.json. Enable it if you want US federal
coverage.

Auth (all free, self-service at https://developer.usajobs.gov/):
  Host: data.usajobs.gov
  User-Agent: <your registered email>   -> USAJOBS_USER_AGENT
  Authorization-Key: <your api key>      -> USAJOBS_API_KEY
"""

from __future__ import annotations

import os
from typing import Iterator, List

import requests

from .base import BaseConnector, NormalizedJob, build_session
from .utils import html_to_text, to_iso, coerce_number

API_URL = "https://data.usajobs.gov/api/search"


class USAJobsConnector(BaseConnector):
    name = "usajobs"
    requires_key = True

    def __init__(self, config, role_matcher, logger_=None):
        self.api_key = os.getenv(config.get("env_key", "USAJOBS_API_KEY"), "")
        self.user_agent = os.getenv(config.get("env_ua", "USAJOBS_USER_AGENT"), "")
        super().__init__(config, role_matcher, logger_)
        self.roles: List[str] = config.get("roles", [])
        self.results_per_page = int(config.get("results_per_page", 50))
        self.max_pages = int(config.get("max_pages", 3))

    def _build_session(self) -> requests.Session:
        return build_session(extra_headers={
            "Host": "data.usajobs.gov",
            "User-Agent": self.user_agent or "skillhunt@example.com",
            "Authorization-Key": self.api_key,
        })

    def is_available(self) -> bool:
        if not self.api_key or not self.user_agent:
            self.log.warning("usajobs: USAJOBS_API_KEY / USAJOBS_USER_AGENT not set — skipping. "
                             "Register free at https://developer.usajobs.gov/")
            return False
        return True

    def fetch(self) -> Iterator[NormalizedJob]:
        total = 0
        for role in self.roles:
            for page in range(1, self.max_pages + 1):
                payload = self._get_json(API_URL, params={
                    "Keyword": role,
                    "ResultsPerPage": self.results_per_page,
                    "Page": page,
                })
                self._sleep()
                items = (((payload or {}).get("SearchResult") or {}).get("SearchResultItems")) or []
                if not items:
                    break

                for wrapper in items:
                    d = wrapper.get("MatchedObjectDescriptor") or {}
                    ext_id = str(d.get("PositionID") or wrapper.get("MatchedObjectId") or "").strip()
                    if not ext_id:
                        continue
                    title = d.get("PositionTitle") or ""

                    # Salary (annual) from the remuneration block.
                    smin = smax = None
                    for rem in (d.get("PositionRemuneration") or []):
                        if str(rem.get("RateIntervalCode", "")).lower() in ("per year", "py", "annum", "annual"):
                            smin = coerce_number(rem.get("MinimumRange"))
                            smax = coerce_number(rem.get("MaximumRange"))
                            break

                    summary = (((d.get("UserArea") or {}).get("Details") or {}).get("JobSummary")) or ""
                    org = d.get("OrganizationName") or ""
                    loc = d.get("PositionLocationDisplay") or "United States"

                    yield NormalizedJob(
                        source=self.name,
                        external_id=ext_id,
                        search_role=role,
                        country_code="us",
                        title=title,
                        company_name=org,
                        description=html_to_text(summary),
                        redirect_url=d.get("PositionURI") or "",
                        location_display=loc,
                        location_areas=[loc],
                        category_tag="it-jobs",
                        category_label="IT Jobs",
                        salary_min=smin,
                        salary_max=smax,
                        salary_currency="USD",
                        contract_type="full_time",
                        job_posted_at=to_iso(d.get("PublicationStartDate")),
                        raw={k: d.get(k) for k in
                             ("PositionID", "PositionURI", "PositionLocationDisplay", "PublicationStartDate")},
                    )
                    total += 1

        self.log.info("usajobs: yielded %d jobs", total)
