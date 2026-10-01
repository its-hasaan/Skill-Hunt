"""
Lever public postings API — api.lever.co/v0/postings/{board}?mode=json

Each posting has `workplaceType` (remote | hybrid | onsite | unspecified),
an ISO `country`, all locations, and plain-text description parts.
"""
from __future__ import annotations

from typing import Optional

from .ats_base import AtsConnector
from .ats_endpoints import job_items, list_url
from .utils import epoch_to_iso, html_to_text

# ISO country -> a name classify_location recognises (only the ones we bucket)
_COUNTRY_NAMES = {"PK": "Pakistan", "IN": "India"}
_COMMITMENT = {"full-time": ("full_time", "permanent"), "permanent": ("full_time", "permanent"),
               "part-time": ("part_time", "permanent"), "contract": ("contract", "temporary"),
               "contractor": ("contract", "temporary"), "intern": ("part_time", "temporary"),
               "internship": ("part_time", "temporary")}


def _description(item: dict) -> str:
    parts = [item.get("descriptionPlain") or ""]
    for block in item.get("lists") or []:
        parts.append(f"{block.get('text', '')}\n{html_to_text(block.get('content'))}")
    parts.append(item.get("additionalPlain") or "")
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def map_job(board: str, item: dict) -> Optional[dict]:
    if not item.get("id") or not item.get("text"):
        return None
    cats = item.get("categories") or {}
    locations = list(cats.get("allLocations") or [])
    if cats.get("location") and cats["location"] not in locations:
        locations.insert(0, cats["location"])
    if item.get("country") in _COUNTRY_NAMES:
        locations.append(_COUNTRY_NAMES[item["country"]])
    ctype, ctime = _COMMITMENT.get(str(cats.get("commitment", "")).lower(), ("", ""))
    salary = item.get("salaryRange") or {}
    yearly = "year" in str(salary.get("interval", "")).lower()
    created = item.get("createdAt")
    return {
        "id": str(item["id"]),
        "title": item["text"].strip(),
        "company_name": board,
        "description": _description(item),
        "redirect_url": item.get("hostedUrl") or item.get("applyUrl") or "",
        "location_display": cats.get("location") or "",
        "location_areas": locations,
        "locations": locations,
        "workplace_hint": item.get("workplaceType"),
        "contract_type": ctype,
        "contract_time": ctime,
        "salary_min": salary.get("min") if yearly else None,
        "salary_max": salary.get("max") if yearly else None,
        "salary_currency": (salary.get("currency") or "USD") if yearly else "USD",
        "job_posted_at": epoch_to_iso(int(created) // 1000) if created else None,
        "raw": {k: item.get(k) for k in ("id", "hostedUrl", "categories", "workplaceType", "country", "createdAt")},
    }


class LeverConnector(AtsConnector):
    name = "lever"

    def map_job(self, board, item):
        return map_job(board, item)

    def fetch_board(self, board):
        return job_items("lever", self._get_json(list_url("lever", board)))
