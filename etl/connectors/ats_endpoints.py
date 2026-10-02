"""
Public job-board API endpoints of the hiring systems (ATS) we read.

These are the endpoints the hiring systems publish so job boards and
company career pages can list open jobs: unauthenticated, read-only, and
meant to be consumed. One place for URLs so the connectors and the board
validator never drift apart.
"""
from __future__ import annotations

from typing import Any, Optional

LIST_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{board}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{board}/postings?limit=100&offset={offset}",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{board}?details=true",
}
ATS_SYSTEMS = tuple(LIST_URLS)


# Lighter variants for the board validator: it only needs to know the board
# exists (and roughly how many jobs it has), not every description.
PROBE_URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
    "lever": "https://api.lever.co/v0/postings/{board}?mode=json&limit=1",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{board}",
}


def list_url(ats: str, board: str, offset: int = 0) -> str:
    return LIST_URLS[ats].format(board=board, offset=offset)


def probe_url(ats: str, board: str) -> str:
    return PROBE_URLS[ats].format(board=board) if ats in PROBE_URLS else list_url(ats, board)


def job_items(ats: str, payload: Any) -> Optional[list]:
    """The list of job items in a list-endpoint payload, or None if the
    payload isn't a valid board response (unknown board, error body)."""
    if ats == "lever":
        return payload if isinstance(payload, list) else None
    if not isinstance(payload, dict):
        return None
    if ats == "greenhouse":
        return payload.get("jobs") if isinstance(payload.get("jobs"), list) else None
    if ats == "ashby":
        return payload.get("jobs") if isinstance(payload.get("jobs"), list) else None
    if ats == "smartrecruiters":
        return payload.get("content") if isinstance(payload.get("content"), list) else None
    if ats == "workable":
        return payload.get("jobs") if isinstance(payload.get("jobs"), list) else None
    raise ValueError(f"unknown ats: {ats}")
