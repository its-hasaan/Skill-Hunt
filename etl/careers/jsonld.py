"""
schema.org JobPosting JSON-LD: find it in a page and map it to the field
shape the company-board connectors use (see connectors.ats_base).

For remote postings (jobLocationType TELECOMMUTE) the locations passed on
are applicantLocationRequirements — where candidates may live — not the
office address, which is usually just the headquarters.
"""
from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
from typing import Optional

from connectors.utils import html_to_text

_SCRIPT_RE = re.compile(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
                        re.IGNORECASE | re.DOTALL)
_COUNTRY_CODES = {"US": "United States", "GB": "United Kingdom", "UK": "United Kingdom", "IN": "India",
                  "PK": "Pakistan", "CA": "Canada", "DE": "Germany", "FR": "France", "ES": "Spain",
                  "NL": "Netherlands", "IE": "Ireland", "AU": "Australia", "SG": "Singapore",
                  "AE": "United Arab Emirates", "BD": "Bangladesh", "LK": "Sri Lanka", "PL": "Poland",
                  "PT": "Portugal", "BR": "Brazil", "MX": "Mexico"}
_EMPLOYMENT = {"FULL_TIME": ("full_time", "permanent"), "PART_TIME": ("part_time", "permanent"),
               "CONTRACTOR": ("contract", "temporary"), "TEMPORARY": ("contract", "temporary"),
               "INTERN": ("part_time", "temporary")}
_PER_YEAR = {"YEAR": 1, "MONTH": 12, "WEEK": 52}


def _is_jobposting(node: dict) -> bool:
    kind = node.get("@type")
    return kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind)


def _walk(node, found: list, depth: int = 0) -> None:
    if depth > 5:
        return
    if isinstance(node, list):
        for child in node:
            _walk(child, found, depth + 1)
    elif isinstance(node, dict):
        if _is_jobposting(node):
            found.append(node)
        elif "@graph" in node:
            _walk(node["@graph"], found, depth + 1)


def extract_jobpostings(html: str) -> list[dict]:
    found: list[dict] = []
    for block in _SCRIPT_RE.findall(html or ""):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        _walk(data, found)
    return found


def _first(value):
    return value[0] if isinstance(value, list) and value else value


def _name(value) -> str:
    value = _first(value)
    if isinstance(value, dict):
        return str(value.get("name") or "")
    return str(value or "")


def _country(value) -> str:
    name = _name(value)
    return _COUNTRY_CODES.get(name.upper(), name) if len(name) <= 3 else name


def _address(place) -> str:
    address = (place or {}).get("address") if isinstance(place, dict) else None
    if isinstance(address, str):
        return address
    if not isinstance(address, dict):
        return ""
    parts = [address.get("addressLocality"), address.get("addressRegion"), _country(address.get("addressCountry"))]
    return ", ".join(str(p) for p in parts if p)


def _as_list(value) -> list:
    return value if isinstance(value, list) else ([value] if value else [])


def _salary(base) -> tuple[Optional[float], Optional[float], str]:
    base = _first(base)
    if not isinstance(base, dict):
        return None, None, "USD"
    currency = str(base.get("currency") or "USD")
    value = base.get("value")
    if not isinstance(value, dict):
        return None, None, currency
    multiplier = _PER_YEAR.get(str(value.get("unitText") or "YEAR").upper())
    low = value.get("minValue", value.get("value"))
    high = value.get("maxValue", value.get("value"))
    if multiplier is None or low is None:
        return None, None, currency
    try:
        return float(low) * multiplier, float(high) * multiplier, currency
    except (TypeError, ValueError):
        return None, None, currency


def map_jobposting(item: dict, page_url: str) -> Optional[dict]:
    title = html_lib.unescape(str(item.get("title") or "")).strip()
    if not title:
        return None
    url = str(item.get("url") or page_url)
    identifier = item.get("identifier")
    job_id = str(identifier.get("value") if isinstance(identifier, dict) else identifier or "").strip()
    if not job_id:
        job_id = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]

    remote = any(str(t).upper() == "TELECOMMUTE" for t in _as_list(item.get("jobLocationType")))
    if remote:
        locations = [_name(req) for req in _as_list(item.get("applicantLocationRequirements"))]
    else:
        locations = [_address(place) for place in _as_list(item.get("jobLocation"))]
    locations = [loc for loc in locations if loc]

    employment = str(_first(item.get("employmentType")) or "").upper()
    ctype, ctime = _EMPLOYMENT.get(employment, ("", ""))
    salary_min, salary_max, currency = _salary(item.get("baseSalary"))
    return {
        "id": job_id,
        "title": title,
        "company_name": _name(item.get("hiringOrganization")),
        "description": html_to_text(html_lib.unescape(str(item.get("description") or ""))),
        "redirect_url": url,
        "location_display": locations[0] if locations else ("Remote" if remote else ""),
        "location_areas": locations,
        "locations": locations,
        "workplace_hint": "remote" if remote else None,
        "remote_flag": remote,
        "contract_type": ctype,
        "contract_time": ctime,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency,
        "job_posted_at": item.get("datePosted"),
        "raw": {k: item.get(k) for k in ("identifier", "url", "datePosted", "validThrough", "jobLocationType",
                                         "applicantLocationRequirements", "employmentType")},
    }
