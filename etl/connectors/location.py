"""
Decide whether a job belongs in a remote-first South Asia feed, and how to
bucket it.

classify_location(locations, workplace_hint, remote_flag) returns
(workplace_type, country_code) or None (drop the job):

- remote anywhere (flag, hint, or "remote/anywhere/worldwide..." in any
  location) -> ("remote", "pk"|"in" if every location is in that one
  country, else "remote"). Whether a "Remote (US)" job is open to someone
  in Pakistan is decided later by eligibility tagging (Phase 1c), which
  sees the full location list.
- not remote -> kept only when located in Pakistan or India, as
  (hint or "onsite", "pk"|"in").
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from .utils import detect_country_code

REMOTE_RE = re.compile(r"\b(remote|anywhere|worldwide|distributed|work from home|wfh)\b", re.IGNORECASE)
LOCAL_COUNTRIES = {"pk", "in"}


def _parts(locations: Iterable[str]) -> list[str]:
    parts = []
    for loc in locations or []:
        parts.extend(p.strip() for p in re.split(r"\s*;\s*", loc or "") if p.strip())
    return parts


def _normalise_hint(hint: Optional[str]) -> str:
    return re.sub(r"[\s\-_]", "", (hint or "").lower())


def classify_location(locations: Iterable[str], workplace_hint: Optional[str] = None,
                      remote_flag: Optional[bool] = None) -> Optional[tuple[str, str]]:
    parts = _parts(locations)
    hint = _normalise_hint(workplace_hint)
    remote = bool(remote_flag) or hint == "remote" or any(REMOTE_RE.search(p) for p in parts)

    countries = {detect_country_code(p) for p in parts}
    local = next(iter(countries)) if len(countries) == 1 and countries <= LOCAL_COUNTRIES else None

    if remote:
        return "remote", local or "remote"
    if local:
        return (hint if hint in ("hybrid", "onsite") else "onsite"), local
    return None
