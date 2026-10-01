"""
SmartRecruiters public postings API — api.smartrecruiters.com/v1/companies/{board}/postings

The list gives title, location (with `remote`/`hybrid` flags) and a `ref`
detail URL; the description needs that detail call, so it is made only for
postings that already passed the role and location filters.
"""
from __future__ import annotations

from typing import Optional

from .ats_base import AtsConnector
from .ats_endpoints import job_items, list_url
from .utils import html_to_text

MAX_PAGES = 10
PAGE_SIZE = 100
_COUNTRY_NAMES = {"pk": "Pakistan", "in": "India"}


def map_job(board: str, item: dict) -> Optional[dict]:
    if not item.get("id") or not item.get("name"):
        return None
    loc = item.get("location") or {}
    full = loc.get("fullLocation") or ", ".join(p for p in (loc.get("city"), loc.get("region"), loc.get("country")) if p)
    locations = [full] + ([_COUNTRY_NAMES[loc["country"]]] if loc.get("country") in _COUNTRY_NAMES else [])
    return {
        "id": str(item["id"]),
        "title": item["name"].strip(),
        "company_name": (item.get("company") or {}).get("name") or board,
        "description": "",
        "redirect_url": f"https://jobs.smartrecruiters.com/{board}/{item['id']}",
        "location_display": full,
        "location_areas": [full] if full else [],
        "locations": locations,
        "workplace_hint": "hybrid" if loc.get("hybrid") else None,
        "remote_flag": loc.get("remote"),
        "job_posted_at": item.get("releasedDate"),
        "raw": {k: item.get(k) for k in ("id", "ref", "location", "releasedDate", "typeOfEmployment")},
    }


def description_from_detail(detail: dict) -> str:
    sections = ((detail or {}).get("jobAd") or {}).get("sections") or {}
    parts = []
    for key in ("jobDescription", "qualifications", "additionalInformation", "companyDescription"):
        text = html_to_text((sections.get(key) or {}).get("text"))
        if text:
            parts.append(text)
    return "\n\n".join(parts)


class SmartRecruitersConnector(AtsConnector):
    name = "smartrecruiters"

    def map_job(self, board, item):
        return map_job(board, item)

    def fetch_board(self, board):
        items, offset = [], 0
        for _ in range(MAX_PAGES):
            payload = self._get_json(list_url("smartrecruiters", board, offset))
            page = job_items("smartrecruiters", payload)
            if page is None:
                return None if offset == 0 else items
            items.extend(page)
            offset += PAGE_SIZE
            if offset >= int(payload.get("totalFound") or 0):
                break
        return items

    def enrich(self, board, item, job):
        detail = self._get_json(item["ref"]) if item.get("ref") else None
        if detail:
            job["description"] = description_from_detail(detail)
            job["redirect_url"] = detail.get("postingUrl") or job["redirect_url"]
        return job
