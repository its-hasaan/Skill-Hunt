"""
Job fingerprints for duplicate removal.

fingerprint = "<company>|<title>|<places>": the same job posted on the
company's own board and re-listed by a remote board ("GitLab" /
"gitlab", "Senior Backend Engineer (Remote)" / "Senior Backend Engineer")
gets one fingerprint. Seniority words stay in the title, so "Senior Data
Engineer" and "Data Engineer" remain different jobs, and the places key
keeps "Remote - US" and "Remote - Canada" postings apart.

SOURCE_PRIORITY picks which listing of a duplicate group is shown (spec
§6.2): the company's hiring system first, then its career page, then
remote boards and Jooble, then Adzuna. ops.dedup's SQL mirrors it.
"""
from __future__ import annotations

import re
from typing import Optional

from .geo import REMOTE_RE, parse_places

_LEGAL_SUFFIX = re.compile(
    r"\s+(inc|incorporated|llc|l\.l\.c|ltd|limited|gmbh|corp|corporation|co|plc|sa|ag|bv|b\.v|pty|pvt|"
    r"private limited|srl|oy|ab|sas)\.?$")
_NON_WORD = re.compile(r"[^\w\s]+")
_SPACES = re.compile(r"\s+")
_BRACKETS = re.compile(r"[(\[][^)\]]*[)\]]")
_SEPARATORS = re.compile(r"\s+[-–—|/]\s+|\s*\|\s*")
_ABBREVIATIONS = [
    (re.compile(r"\bsr\b\.?"), "senior"),
    (re.compile(r"\bjr\b\.?"), "junior"),
    (re.compile(r"&"), " and "),
]


class _Priority(dict):
    def __missing__(self, key):
        return self["default"]


SOURCE_PRIORITY = _Priority({
    "greenhouse": 1, "lever": 1, "ashby": 1, "smartrecruiters": 1, "workable": 1,
    "careerpage": 2,
    "default": 3,
    "adzuna": 4,
})


def _clean(text: str) -> str:
    return _SPACES.sub(" ", _NON_WORD.sub(" ", text)).strip()


def normalise_company(name: Optional[str]) -> str:
    text = _SPACES.sub(" ", (name or "").lower().replace(",", " ")).strip()
    while True:
        stripped = _LEGAL_SUFFIX.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    return _clean(text)


def _place_like(segment: str) -> bool:
    return bool(REMOTE_RE.search(segment)) or not parse_places(segment).empty


def normalise_title(title: Optional[str]) -> str:
    # "(Remote)" / "[US]" are where the job is; "(Payments)" is which team, so it stays.
    text = _BRACKETS.sub(lambda m: " " if _place_like(m.group(0)[1:-1]) else f" {m.group(0)[1:-1]} ",
                         title or "")
    segments = _SEPARATORS.split(text)
    kept = [segments[0]] + [s for s in segments[1:] if not _place_like(s)]
    parts = []
    for i, segment in enumerate(kept):
        pieces = segment.split(",")
        parts.append(pieces[0])
        parts.extend(p for p in pieces[1:] if not _place_like(p))
    text = " ".join(parts).lower()
    for pattern, replacement in _ABBREVIATIONS:
        text = pattern.sub(replacement, text)
    return _clean(text)


def location_key(location_text: Optional[str]) -> str:
    places = parse_places(location_text or "")
    # "Remote" and "Worldwide" describe the same listing; only named places separate jobs.
    return ",".join(sorted((places.countries | places.regions) - {"worldwide"}))


def fingerprint(company: Optional[str], title: Optional[str], location_text: Optional[str]) -> str:
    return f"{normalise_company(company)}|{normalise_title(title)}|{location_key(location_text)}"
