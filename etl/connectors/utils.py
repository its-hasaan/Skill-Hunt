"""
Shared helpers for job-source connectors.

Pure, dependency-light utilities: HTML -> text, role classification,
salary/date coercion. Kept separate from `base.py` so connectors can
import just what they need and so this stays easy to unit-test.
"""

from __future__ import annotations

import re
import html as _html
from datetime import datetime, timezone
from typing import List, Optional, Iterable


# ---------------------------------------------------------------------------
# HTML -> plain text
# ---------------------------------------------------------------------------
# Most remote-board APIs return job descriptions as HTML. The skill extractor
# works on plain text (its regex would otherwise match inside tags/entities),
# so we strip markup here at ingestion time.

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\f\v]+")
_MULTINEWLINE_RE = re.compile(r"\n{3,}")


def html_to_text(raw: Optional[str]) -> str:
    """Convert an HTML fragment to readable plain text.

    Uses BeautifulSoup when available (better handling of block elements and
    entities); falls back to a regex strip so the pipeline never hard-depends
    on lxml/bs4 being installed.
    """
    if not raw:
        return ""

    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(raw, "html.parser")
        # Turn <br>, </p>, </li> etc. into line breaks for readability.
        for br in soup.find_all(["br"]):
            br.replace_with("\n")
        text = soup.get_text(separator="\n")
    except Exception:
        # Fallback: naive tag strip.
        text = _TAG_RE.sub(" ", raw)

    text = _html.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = _MULTINEWLINE_RE.sub("\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Date coercion -> ISO 8601 string (what the transformer expects)
# ---------------------------------------------------------------------------

def epoch_to_iso(epoch: Optional[int]) -> Optional[str]:
    """Unix seconds -> ISO 8601 UTC string."""
    if epoch in (None, "", 0):
        return None
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
    except (ValueError, OSError, TypeError):
        return None


def to_iso(value) -> Optional[str]:
    """Best-effort parse of common date formats -> ISO 8601 string.

    Accepts ISO strings (with/without 'Z'), RFC-2822 (RSS pubDate), and
    epoch ints. Returns None when it cannot be parsed — the orchestrator
    then falls back to "now" so the job still lands inside dbt's freshness
    window instead of being silently dropped.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return epoch_to_iso(int(value))

    s = str(value).strip()

    # Pure epoch delivered as a string.
    if s.isdigit():
        return epoch_to_iso(int(s))

    # ISO 8601.
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).isoformat()
    except (ValueError, TypeError):
        pass

    # RFC 2822 (typical RSS <pubDate>: "Mon, 30 Jun 2026 12:00:00 +0000").
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(s)
        if dt is not None:
            return dt.isoformat()
    except (ValueError, TypeError):
        pass

    return None


# ---------------------------------------------------------------------------
# Salary coercion
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"\d[\d,\.]*")


def coerce_number(value) -> Optional[float]:
    """Extract a numeric value from an int/float/str like '$90,000'."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _NUM_RE.search(str(value).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def parse_salary_range(text: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """Pull (min, max) out of a free-text salary string like
    '$70,000 - $90,000 a year'. Returns (None, None) if nothing usable.
    """
    if not text:
        return (None, None)
    nums = [float(n.replace(",", "")) for n in _NUM_RE.findall(str(text))]
    # Drop obviously-not-salary small numbers (e.g. "401k" -> 401).
    nums = [n for n in nums if n >= 1000]
    if not nums:
        return (None, None)
    if len(nums) == 1:
        return (nums[0], nums[0])
    return (min(nums[:2]), max(nums[:2]))


# ---------------------------------------------------------------------------
# Role classification
# ---------------------------------------------------------------------------
# The platform tracks a fixed set of 15 roles. Feed-style sources (RemoteOK,
# WeWorkRemotely, ...) return everything, so we classify each job title into
# one of those roles — or None (which the orchestrator drops). Ordering is
# deliberate: more specific roles are tested before the generic ones so a
# "Full Stack Developer" is not misfiled as "Backend Developer".

# (canonical_role_name, [regex keyword patterns])
_ROLE_PATTERNS: List[tuple[str, List[str]]] = [
    ("Analytics Engineer", [r"analytics engineer"]),
    ("Machine Learning Engineer", [r"machine learning", r"\bml engineer", r"\bmlops\b"]),
    ("Computer Vision Engineer", [r"computer vision", r"\bcv engineer"]),
    ("AI Engineer", [r"\bai engineer", r"artificial intelligence engineer",
                     r"generative ai", r"\bgen ?ai", r"\bllm\b", r"\bnlp engineer"]),
    ("Data Scientist", [r"data scientist", r"data science"]),
    ("Data Engineer", [r"data engineer", r"data engineering", r"\betl developer",
                       r"big data engineer"]),
    ("Business Intelligence Developer", [r"business intelligence", r"\bbi developer",
                                         r"\bbi engineer", r"power ?bi", r"tableau developer"]),
    ("Data Analyst", [r"data analyst", r"data analytics", r"business analyst.*data"]),
    ("Full Stack Developer", [r"full[\s\-]?stack"]),
    ("Mobile Developer", [r"mobile developer", r"mobile engineer", r"\bios (developer|engineer)",
                          r"android (developer|engineer)", r"react native", r"\bflutter\b"]),
    ("Frontend Developer", [r"front[\s\-]?end", r"\bui engineer", r"\bui developer",
                            r"react(\.js)? developer", r"angular developer", r"vue(\.js)? developer"]),
    ("Backend Developer", [r"back[\s\-]?end", r"server[\s\-]?side",
                           r"\b(node|java|python|php|go|ruby|\.net)\b.*developer.*api"]),
    ("DevOps Engineer", [r"devops", r"site reliability", r"\bsre\b", r"platform engineer",
                         r"infrastructure engineer"]),
    ("Cloud Architect", [r"cloud architect", r"solutions? architect", r"aws architect",
                         r"azure architect", r"gcp architect", r"cloud engineer"]),
    ("Cyber Security Engineer", [r"cyber ?security", r"security engineer", r"\binfosec\b",
                                 r"application security", r"security analyst", r"soc analyst",
                                 r"penetration test"]),
]

_COMPILED_ROLE_PATTERNS = [
    (role, [re.compile(p, re.IGNORECASE) for p in patterns])
    for role, patterns in _ROLE_PATTERNS
]


class RoleMatcher:
    """Maps a free-text job title to one of the platform's tracked roles.

    Only roles present in `active_roles` are eligible, so a connector run
    respects whatever subset of roles is configured. Returns None when the
    title does not clearly belong to a tracked role (the orchestrator then
    skips that job to keep the role dimension clean).
    """

    def __init__(self, active_roles: Iterable[str]):
        self.active = {r.strip() for r in active_roles}

    def match(self, title: Optional[str], tags: Optional[Iterable[str]] = None) -> Optional[str]:
        # Title is the primary (most trustworthy) signal.
        title = (title or "").strip()
        if title:
            for role, patterns in _COMPILED_ROLE_PATTERNS:
                if role not in self.active:
                    continue
                if any(p.search(title) for p in patterns):
                    return role
        # Fall back to tags, matched INDIVIDUALLY — joining them would let a
        # phrase span tag boundaries (["cloud","architect"] -> "cloud architect")
        # and misclassify unrelated jobs.
        for tag in (tags or []):
            tag = str(tag).strip()
            if not tag:
                continue
            for role, patterns in _COMPILED_ROLE_PATTERNS:
                if role not in self.active:
                    continue
                if any(p.search(tag) for p in patterns):
                    return role
        return None


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------

def detect_country_code(*location_texts: Optional[str]) -> str:
    """Map free-text location(s) to one of our country codes.

    Returns 'in' / 'pk' when a South-Asian location is named, otherwise
    'remote' (the default bucket for worldwide remote roles).
    """
    blob = " ".join(t for t in location_texts if t).lower()
    if not blob:
        return "remote"
    if re.search(r"\bpakistan\b|\bkarachi\b|\blahore\b|\bislamabad\b|\brawalpindi\b", blob):
        return "pk"
    if re.search(r"\bindia\b|\bbangalore\b|bengaluru|\bmumbai\b|\bdelhi\b|\bhyderabad\b|\bpune\b|\bchennai\b|\bnoida\b|gurgaon|gurugram", blob):
        return "in"
    return "remote"
