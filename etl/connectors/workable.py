"""
Workable public job widget — apply.workable.com/api/v1/widget/accounts/{board}?details=true

The endpoint Workable serves for embedding a company's open jobs on its own
site: title, `telecommuting` (remote) flag, structured locations, HTML
description. For remote roles the office location is usually `hidden` and
the real scope lives in the title ("... - EMEA Remote"), so hidden locations
are not passed on as requirements.
"""
from __future__ import annotations

from typing import Optional

from .ats_base import AtsConnector
from .ats_endpoints import job_items, list_url
from .utils import html_to_text

_EMPLOYMENT = {"full-time": ("full_time", "permanent"), "part-time": ("part_time", "permanent"),
               "contract": ("contract", "temporary"), "temporary": ("contract", "temporary"),
               "internship": ("part_time", "temporary")}


def _truthy(value) -> bool:
    return value is True or str(value).lower() == "true"


def _location(entry: dict) -> str:
    return ", ".join(p for p in (entry.get("city"), entry.get("region"), entry.get("country")) if p)


def map_job(board: str, item: dict) -> Optional[dict]:
    if not item.get("shortcode") or not item.get("title"):
        return None
    locations = [_location(loc) for loc in item.get("locations") or []
                 if isinstance(loc, dict) and not _truthy(loc.get("hidden"))]
    locations = [loc for loc in locations if loc]
    ctype, ctime = _EMPLOYMENT.get(str(item.get("employment_type", "")).lower(), ("", ""))
    return {
        "id": str(item["shortcode"]),
        "title": item["title"].strip(),
        "company_name": board,
        "description": html_to_text(item.get("description")),
        "redirect_url": item.get("url") or item.get("shortlink") or "",
        "location_display": locations[0] if locations else ("Remote" if _truthy(item.get("telecommuting")) else ""),
        "location_areas": locations,
        "locations": locations,
        "workplace_hint": None,
        "remote_flag": _truthy(item.get("telecommuting")),
        "contract_type": ctype,
        "contract_time": ctime,
        "job_posted_at": item.get("published_on") or item.get("created_at"),
        "raw": {k: item.get(k) for k in ("shortcode", "url", "telecommuting", "locations", "published_on",
                                         "employment_type")},
    }


class WorkableConnector(AtsConnector):
    name = "workable"

    def map_job(self, board, item):
        return map_job(board, item)

    def fetch_board(self, board):
        return job_items("workable", self._get_json(list_url("workable", board)))
