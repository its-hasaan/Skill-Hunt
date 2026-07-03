"""
Himalayas connector — https://himalayas.app/jobs/api

Free, no-key remote-jobs JSON API. Offset/limit pagination, max 20 per call.
`locationRestrictions` is an array of countries applicants must be based in;
an empty array means worldwide (which we bucket as 'remote').
"""

from __future__ import annotations

from typing import Iterator

from .base import BaseConnector, NormalizedJob
from .utils import html_to_text, epoch_to_iso, detect_country_code, coerce_number

API_URL = "https://himalayas.app/jobs/api"
PAGE_SIZE = 20

_CONTRACT_MAP = {
    "full_time": ("full_time", "permanent"),
    "full-time": ("full_time", "permanent"),
    "part_time": ("part_time", "permanent"),
    "part-time": ("part_time", "permanent"),
    "contract": ("contract", "temporary"),
    "freelance": ("contract", "temporary"),
    "internship": ("part_time", "temporary"),
}


class HimalayasConnector(BaseConnector):
    name = "himalayas"
    requires_key = False

    def fetch(self) -> Iterator[NormalizedJob]:
        max_records = int(self.config.get("max_records", 200))
        total = 0
        offset = 0

        while offset < max_records:
            payload = self._get_json(API_URL, params={"limit": PAGE_SIZE, "offset": offset})
            self._sleep()
            if not payload:
                break
            jobs = payload.get("jobs") if isinstance(payload, dict) else None
            if not jobs:
                break

            for item in jobs:
                title = item.get("title") or ""
                categories = item.get("categories") or []
                role = self._match_role(title, categories)
                if not role:
                    continue

                ext_id = str(item.get("guid") or "").strip()
                if not ext_id:
                    continue

                restrictions = item.get("locationRestrictions") or []
                country = detect_country_code(" ".join(str(r) for r in restrictions)) if restrictions else "remote"

                ctype, ctime = _CONTRACT_MAP.get(str(item.get("employmentType", "")).lower(), ("", ""))

                # Only trust salary when it is an annual figure.
                period = str(item.get("salaryPeriod", "")).lower()
                smin = smax = None
                if period in ("", "yearly", "annual", "year", "annually"):
                    smin = coerce_number(item.get("minSalary"))
                    smax = coerce_number(item.get("maxSalary"))

                yield NormalizedJob(
                    source=self.name,
                    external_id=ext_id,
                    search_role=role,
                    country_code=country,
                    title=title,
                    company_name=item.get("companyName") or "",
                    description=html_to_text(item.get("description") or item.get("excerpt")),
                    redirect_url=item.get("applicationLink") or "",
                    location_display=", ".join(str(r) for r in restrictions) if restrictions else "Worldwide",
                    location_areas=[str(r) for r in restrictions],
                    category_tag="it-jobs",
                    category_label="IT Jobs",
                    salary_min=smin,
                    salary_max=smax,
                    salary_currency=item.get("currency") or "USD",
                    contract_type=ctype,
                    contract_time=ctime,
                    job_posted_at=epoch_to_iso(item.get("pubDate")),
                    raw={k: item.get(k) for k in
                         ("guid", "applicationLink", "locationRestrictions", "employmentType", "pubDate")},
                )
                total += 1

            offset += PAGE_SIZE
            total_count = payload.get("totalCount") if isinstance(payload, dict) else None
            if total_count is not None and offset >= total_count:
                break

        self.log.info("himalayas: yielded %d matching jobs", total)
