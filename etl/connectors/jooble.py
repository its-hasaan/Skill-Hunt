"""
Jooble connector — https://jooble.org/api/<key>  (POST)

Jooble is a worldwide job AGGREGATOR with a free REST API. It is the most
valuable source for this platform's goal because it returns LOCAL, on-the-
ground postings for Pakistan and India (which the remote boards and Adzuna's
`in` endpoint only partially cover, and Adzuna does not cover Pakistan at all).

Get a free key: https://jooble.org/api/about  ->  set JOOBLE_API_KEY.

Request body: {"keywords": "...", "location": "...", "page": "1"}
Response:     {"totalCount": N, "jobs": [{title, location, snippet, salary,
              source, type, link, company, updated, id}]}

We search each tracked role in each configured location (Pakistan, India).
As with the Adzuna extractor, the searched role becomes `search_role`.
"""

from __future__ import annotations

import os
import json
from typing import Iterator, Dict, List

import requests

from .base import BaseConnector, NormalizedJob
from .utils import html_to_text, to_iso, parse_salary_range

API_BASE = "https://jooble.org/api/"

# Human location string -> (country_code, currency)
_LOCATION_MAP = {
    "pakistan": ("pk", "PKR"),
    "india": ("in", "INR"),
}

_CONTRACT_MAP = {
    "full-time": ("full_time", "permanent"),
    "full time": ("full_time", "permanent"),
    "part-time": ("part_time", "permanent"),
    "part time": ("part_time", "permanent"),
    "contract": ("contract", "temporary"),
    "temporary": ("contract", "temporary"),
    "internship": ("part_time", "temporary"),
}


class JoobleConnector(BaseConnector):
    name = "jooble"
    requires_key = True

    def __init__(self, config, role_matcher, logger_=None):
        super().__init__(config, role_matcher, logger_)
        self.api_key = os.getenv(config.get("env_key", "JOOBLE_API_KEY"), "")
        self.roles: List[str] = config.get("roles", [])
        self.locations: List[str] = config.get("locations", ["Pakistan", "India"])
        self.pages_per_query = int(config.get("pages_per_query", 3))

    def is_available(self) -> bool:
        if not self.api_key:
            self.log.warning("jooble: JOOBLE_API_KEY not set — skipping. "
                             "Get a free key at https://jooble.org/api/about")
            return False
        return True

    def _post(self, body: Dict) -> Dict:
        url = API_BASE + self.api_key
        try:
            resp = self.session.post(
                url,
                data=json.dumps(body),
                headers={"Content-Type": "application/json"},
                timeout=getattr(self.session, "request_timeout", 30),
            )
            if resp.status_code != 200:
                self.log.warning("jooble: POST -> HTTP %s", resp.status_code)
                return {}
            return resp.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            self.log.warning("jooble: request failed: %s", e)
            return {}

    def fetch(self) -> Iterator[NormalizedJob]:
        total = 0
        seen: set[str] = set()

        for location in self.locations:
            country, currency = _LOCATION_MAP.get(location.lower(), ("remote", "USD"))
            for role in self.roles:
                for page in range(1, self.pages_per_query + 1):
                    payload = self._post({
                        "keywords": role,
                        "location": location,
                        "page": str(page),
                    })
                    self._sleep()
                    jobs = payload.get("jobs") if isinstance(payload, dict) else None
                    if not jobs:
                        break

                    for item in jobs:
                        ext_id = str(item.get("id") or "").strip()
                        if not ext_id or ext_id in seen:
                            continue
                        seen.add(ext_id)

                        smin, smax = parse_salary_range(item.get("salary"))
                        ctype, ctime = _CONTRACT_MAP.get(str(item.get("type", "")).lower(), ("", ""))
                        loc = item.get("location") or location

                        yield NormalizedJob(
                            source=self.name,
                            external_id=ext_id,
                            search_role=role,
                            country_code=country,
                            title=item.get("title") or "",
                            company_name=item.get("company") or "",
                            description=html_to_text(item.get("snippet")),
                            redirect_url=item.get("link") or "",
                            location_display=loc,
                            location_areas=[a for a in [loc] if a],
                            category_tag="it-jobs",
                            category_label="IT Jobs",
                            salary_min=smin,
                            salary_max=smax,
                            salary_currency=currency,
                            contract_type=ctype,
                            contract_time=ctime,
                            job_posted_at=to_iso(item.get("updated")),
                            raw={k: item.get(k) for k in
                                 ("id", "link", "location", "salary", "type", "updated", "source")},
                        )
                        total += 1

        self.log.info("jooble: yielded %d jobs across %d locations", total, len(self.locations))
