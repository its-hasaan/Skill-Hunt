"""
Ashby public job board API — api.ashbyhq.com/posting-api/job-board/{board}

Richest of the four: `isRemote`, `workplaceType`, primary + secondary
locations with countries, plain-text description and (optionally)
compensation summaries like "$211.4K - $290.6K".
"""
from __future__ import annotations

import re
from typing import Optional

from .ats_base import AtsConnector
from .ats_endpoints import job_items, list_url
from .utils import html_to_text

_AMOUNT = re.compile(r"([$€£₹])?\s*(\d+(?:[.,]\d+)?)\s*([KkMm])?")
_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
_EMPLOYMENT = {"fulltime": ("full_time", "permanent"), "parttime": ("part_time", "permanent"),
               "contract": ("contract", "temporary"), "intern": ("part_time", "temporary"),
               "temporary": ("contract", "temporary")}


def parse_compensation(summary: Optional[str]) -> tuple[Optional[float], Optional[float], str]:
    """"$211.4K - $290.6K" -> (211400.0, 290600.0, "USD")."""
    if not summary:
        return None, None, "USD"
    values, currency = [], "USD"
    for symbol, number, suffix in _AMOUNT.findall(summary):
        value = float(number.replace(",", ""))
        value *= {"k": 1_000, "m": 1_000_000}.get(suffix.lower(), 1)
        if symbol:
            currency = _CURRENCY[symbol]
        if value >= 1000:
            values.append(value)
    if not values:
        return None, None, currency
    return min(values[:2]), max(values[:2]), currency


def _country_names(entry: dict) -> list[str]:
    country = (((entry or {}).get("address") or {}).get("postalAddress") or {}).get("addressCountry")
    return [country] if country else []


def map_job(board: str, item: dict) -> Optional[dict]:
    if item.get("isListed") is False or not item.get("id") or not item.get("title"):
        return None
    secondary = item.get("secondaryLocations") or []
    locations = [item.get("location") or ""] + [s.get("location") or "" for s in secondary]
    countries = _country_names(item) + [c for s in secondary for c in _country_names(s)]
    smin, smax, currency = parse_compensation(
        ((item.get("compensation") or {}).get("scrapeableCompensationSalarySummary")))
    ctype, ctime = _EMPLOYMENT.get(str(item.get("employmentType", "")).lower(), ("", ""))
    return {
        "id": str(item["id"]),
        "title": item["title"].strip(),
        "company_name": board,
        "description": item.get("descriptionPlain") or html_to_text(item.get("descriptionHtml")),
        "redirect_url": item.get("jobUrl") or item.get("applyUrl") or "",
        "location_display": item.get("location") or "",
        "location_areas": [loc for loc in locations if loc],
        "locations": [loc for loc in locations if loc] + countries,
        "workplace_hint": item.get("workplaceType"),
        "remote_flag": item.get("isRemote"),
        "contract_type": ctype,
        "contract_time": ctime,
        "salary_min": smin,
        "salary_max": smax,
        "salary_currency": currency,
        "job_posted_at": item.get("publishedAt"),
        "raw": {k: item.get(k) for k in ("id", "jobUrl", "location", "secondaryLocations", "isRemote",
                                         "workplaceType", "employmentType", "publishedAt")},
    }


class AshbyConnector(AtsConnector):
    name = "ashby"

    def map_job(self, board, item):
        return map_job(board, item)

    def fetch_board(self, board):
        return job_items("ashby", self._get_json(list_url("ashby", board)))
