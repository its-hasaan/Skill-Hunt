"""
Greenhouse public job board API — boards-api.greenhouse.io/v1/boards/{board}/jobs

Unauthenticated, read-only, published for job boards and career pages.
`content=true` returns the full description as HTML-escaped HTML. There is
no structured remote flag: location text ("Remote, Bangalore") and office
names carry it, and classify_location reads both.
"""
from __future__ import annotations

import html
from typing import Optional

from .ats_base import AtsConnector
from .ats_endpoints import job_items, list_url
from .utils import html_to_text


def map_job(board: str, item: dict) -> Optional[dict]:
    if not item.get("id") or not item.get("title"):
        return None
    location = (item.get("location") or {}).get("name") or ""
    offices = [o.get("name") for o in item.get("offices") or [] if o.get("name")]
    return {
        "id": str(item["id"]),
        "title": item["title"].strip(),
        "company_name": item.get("company_name") or board,
        "description": html_to_text(html.unescape(item.get("content") or "")),
        "redirect_url": item.get("absolute_url") or "",
        "location_display": location,
        "location_areas": [p.strip() for p in location.split(";") if p.strip()] + offices,
        "locations": [location, *offices],
        "job_posted_at": item.get("first_published") or item.get("updated_at"),
        "raw": {k: item.get(k) for k in ("id", "absolute_url", "location", "offices",
                                         "updated_at", "first_published")},
    }


class GreenhouseConnector(AtsConnector):
    name = "greenhouse"

    def map_job(self, board, item):
        return map_job(board, item)

    def fetch_board(self, board):
        return job_items("greenhouse", self._get_json(list_url("greenhouse", board)))
