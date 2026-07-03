"""
Connector base classes and the normalized job contract.

Every source connector produces `NormalizedJob` records with the SAME shape,
regardless of how wildly the upstream API/feed differs. The orchestrator then
stores them uniformly in `raw.jobs`, and the transformer reads the normalized
envelope without needing per-source parsing logic.

Design goals:
- Robust, not evasive. We use a real User-Agent, back off on 429/5xx, respect
  each source's rate limits, and stop politely. We do NOT rotate residential
  proxies, spoof fingerprints, or defeat bot-detection — that is what gets a
  platform banned/sued and is out of scope by design.
- Fail soft. A single source erroring out never takes down the run; the
  orchestrator logs it and moves on.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Iterator, List, Optional, Dict, Any

import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 v1/v2 compatibility
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    Retry = None  # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The normalized record — the single contract between connectors and the DB
# ---------------------------------------------------------------------------

@dataclass
class NormalizedJob:
    source: str                       # e.g. "remoteok"
    external_id: str                  # the job's id on that source
    search_role: str                  # one of the platform's tracked roles
    country_code: str                 # 'pk' | 'in' | 'remote' | ...
    title: str
    company_name: str
    description: str                  # PLAIN TEXT (HTML already stripped)
    redirect_url: str                 # link back to the posting (attribution)

    location_display: str = ""
    location_areas: List[str] = field(default_factory=list)
    category_tag: str = ""
    category_label: str = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_is_predicted: bool = False
    salary_currency: str = "USD"
    contract_type: str = ""           # 'full_time' | 'part_time' | 'contract'
    contract_time: str = ""           # 'permanent' | 'temporary'
    job_posted_at: Optional[str] = None  # ISO 8601 string, or None
    raw: Dict[str, Any] = field(default_factory=dict)  # original payload

    @property
    def job_platform_id(self) -> str:
        """Namespaced id so ids never collide across providers and the
        existing `raw.jobs (job_platform_id, country_code)` unique constraint
        keeps guaranteeing idempotency."""
        return f"{self.source}:{self.external_id}"

    def to_raw_envelope(self) -> Dict[str, Any]:
        """The JSON stored in `raw.jobs.raw_data`. Carries both the clean
        normalized fields (read by the transformer) and the original payload
        (kept for reprocessing / provenance)."""
        normalized = asdict(self)
        original = normalized.pop("raw", {})
        return {
            "_source": self.source,
            "_normalized": normalized,
            "_raw": original,
        }


# A small pool of realistic, honest User-Agents. Rotating these is standard
# etiquette for public APIs (many block the default "python-requests/x.y"
# agent) — it is NOT fingerprint spoofing to defeat bot-detection.
_USER_AGENTS = [
    "SkillHuntBot/1.0 (+https://skill-hunt.onrender.com; job-market-analytics)",
    "Mozilla/5.0 (compatible; SkillHuntBot/1.0; +https://skill-hunt.onrender.com)",
]


def build_session(
    timeout: int = 30,
    total_retries: int = 4,
    backoff_factor: float = 1.5,
    extra_headers: Optional[Dict[str, str]] = None,
) -> requests.Session:
    """A requests.Session with automatic retry + exponential backoff on
    429/5xx and a real User-Agent. `timeout` is stashed on the session and
    applied by connectors on each call."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": _USER_AGENTS[0],
        "Accept": "application/json, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    if extra_headers:
        session.headers.update(extra_headers)

    if Retry is not None:
        retry = Retry(
            total=total_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

    session.request_timeout = timeout  # type: ignore[attr-defined]
    return session


# ---------------------------------------------------------------------------
# Base connector
# ---------------------------------------------------------------------------

class BaseConnector:
    """Subclass and implement `fetch()`. See existing connectors for examples."""

    #: unique, stable name — becomes the `source` value in the DB
    name: str = "base"
    #: whether this connector needs an API key present to run
    requires_key: bool = False

    def __init__(self, config: Dict[str, Any], role_matcher, logger_=None):
        self.config = config or {}
        self.role_matcher = role_matcher
        self.log = logger_ or logging.getLogger(f"connector.{self.name}")
        self.delay_seconds = float(self.config.get("delay_seconds", 2))
        self.session = self._build_session()

    # -- overridable hooks ---------------------------------------------------

    def _build_session(self) -> requests.Session:
        return build_session()

    def is_available(self) -> bool:
        """Return False (with a logged reason) when the connector cannot run —
        e.g. a required key is missing. Base connectors are always available."""
        return True

    def fetch(self) -> Iterator[NormalizedJob]:  # pragma: no cover - abstract
        """Yield NormalizedJob records. Implemented by each source."""
        raise NotImplementedError

    # -- shared helpers ------------------------------------------------------

    def _get_json(self, url: str, **kwargs) -> Optional[Any]:
        """GET + parse JSON with the session's timeout and soft failure."""
        try:
            resp = self.session.get(url, timeout=getattr(self.session, "request_timeout", 30), **kwargs)
            if resp.status_code != 200:
                self.log.warning("%s: GET %s -> HTTP %s", self.name, url, resp.status_code)
                return None
            return resp.json()
        except requests.exceptions.RequestException as e:
            self.log.warning("%s: request failed for %s: %s", self.name, url, e)
            return None
        except ValueError as e:  # JSON decode
            self.log.warning("%s: bad JSON from %s: %s", self.name, url, e)
            return None

    def _get_text(self, url: str, **kwargs) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=getattr(self.session, "request_timeout", 30), **kwargs)
            if resp.status_code != 200:
                self.log.warning("%s: GET %s -> HTTP %s", self.name, url, resp.status_code)
                return None
            return resp.text
        except requests.exceptions.RequestException as e:
            self.log.warning("%s: request failed for %s: %s", self.name, url, e)
            return None

    def _sleep(self) -> None:
        """Polite delay between requests to respect the source."""
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

    def _match_role(self, title: str, tags=None) -> Optional[str]:
        return self.role_matcher.match(title, tags)
