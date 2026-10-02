"""
Gemini Flash fallback for jobs the eligibility rules couldn't decide.

Only public job-posting text is sent (decision D4: personal data goes to
Groq, never here). One call labels up to 20 jobs and must return JSON; each
yes/no needs an evidence quote that really appears in the posting, or the
label falls back to unclear.

    client = GeminiClient(api_key, model)
    labels = client.label(jobs)   # {job_id: Eligibility(method="llm")}

The key travels in the x-goog-api-key header, never in the URL. Repeated
429s raise QuotaExhausted so the caller can stop for the day.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Callable, Optional

from .eligibility import Eligibility
from .geo import parse_places

log = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"
BATCH_SIZE = 20
MAX_EXCERPT = 1500
SCOPES = ["worldwide", "regions", "countries", "unclear"]
FALLBACK_EXCERPT = 600

INSTRUCTIONS = """You label remote tech job postings for job seekers who live in Pakistan or India.
For each job decide whether someone living in Pakistan (eligible_pk) and someone living in India
(eligible_in) can be hired for it while staying in their own country.
- "yes": the posting allows it: worldwide / anywhere, a region that includes the country
  (e.g. APAC, Asia, South Asia), or it names the country.
- "no": the posting limits hiring to places that exclude the country (e.g. "must be based in the US",
  "Remote - Canada", "EU only", US work authorization required, onsite or hybrid elsewhere).
- "unclear": the posting does not say. Do not guess from the company's headquarters or salary currency.
remote_scope: worldwide, regions, countries or unclear.
evidence: copy the exact sentence or location text from the posting that decided it, word for word
(at most 300 characters). Use "" when both answers are unclear.
Return one entry for every job id below."""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "jobs": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "INTEGER"},
                    "remote_scope": {"type": "STRING", "enum": SCOPES},
                    "eligible_pk": {"type": "STRING", "enum": ["yes", "no", "unclear"]},
                    "eligible_in": {"type": "STRING", "enum": ["yes", "no", "unclear"]},
                    "evidence": {"type": "STRING"},
                },
                "required": ["id", "remote_scope", "eligible_pk", "eligible_in", "evidence"],
            },
        }
    },
    "required": ["jobs"],
}

_RELEVANT = re.compile(
    r"remote|locat|based|resid|reside|live in|authori[sz]|visa|time ?zone|anywhere|worldwide|global|"
    r"countr|relocat|hybrid|on-?site|office|citizen|work permit|eligib|hire|hiring", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_ANSWERS = {"yes": True, "no": False, "unclear": None}


class QuotaExhausted(Exception):
    """The free-tier quota is used up (repeated HTTP 429)."""


def _locations(job: dict) -> str:
    parts = [job.get("location_display") or ""] + list(job.get("location_areas") or [])
    return "; ".join(dict.fromkeys(p.strip() for p in parts if p and p.strip()))


def excerpt(description: Optional[str]) -> str:
    """The sentences that talk about place, remote work or hiring; else the opening."""
    text = description or ""
    picked, size = [], 0
    for sentence in _SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if _RELEVANT.search(sentence) or not parse_places(sentence, structured=False).empty:
            if size + len(sentence) > MAX_EXCERPT:
                break
            picked.append(sentence)
            size += len(sentence) + 1
    return " ".join(picked) if picked else text[:FALLBACK_EXCERPT]


def build_prompt(jobs: list[dict]) -> str:
    blocks = []
    for job in jobs:
        blocks.append(f"Job id={job['job_id']}\nTitle: {job.get('title') or ''}\n"
                      f"Company: {job.get('company_name') or ''}\nLocations: {_locations(job)}\n"
                      f"Text: {excerpt(job.get('description'))}")
    return INSTRUCTIONS + "\n\n" + "\n\n".join(blocks)


def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", re.sub(r"[\"'`…]|\.{3}", " ", text)).strip()


def _quoted(evidence: str, job: dict) -> bool:
    needle = _normalise(evidence).strip(" .;:,")
    if len(needle) < 3:
        return False
    haystack = _normalise(" ".join([job.get("title") or "", _locations(job), job.get("description") or ""]))
    return needle in haystack


def parse_labels(text: str, jobs: list[dict]) -> dict[int, Eligibility]:
    try:
        items = json.loads(text)["jobs"]
    except (ValueError, KeyError, TypeError):
        log.warning("Gemini returned malformed JSON; batch skipped")
        return {}
    by_id = {job["job_id"]: job for job in jobs}
    labels = {}
    for item in items if isinstance(items, list) else []:
        try:
            job = by_id.get(int(item["id"]))
        except (KeyError, TypeError, ValueError):
            continue
        if job is None:
            continue
        pk = _ANSWERS.get(str(item.get("eligible_pk", "")).lower())
        inn = _ANSWERS.get(str(item.get("eligible_in", "")).lower())
        evidence = str(item.get("evidence") or "")[:300]
        if (pk is not None or inn is not None) and not _quoted(evidence, job):
            pk = inn = None  # a decision needs a real quote from the posting
        scope = item.get("remote_scope") if item.get("remote_scope") in SCOPES else "unclear"
        decided = pk is not None or inn is not None
        labels[job["job_id"]] = Eligibility(
            remote_scope=scope if decided else "unclear",
            eligible_pk=pk, eligible_in=inn,
            confidence=0.8 if decided else 0.3,
            evidence=evidence if decided else "",
            method="llm",
        )
    return labels


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, post: Optional[Callable] = None,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 min_interval: float = 6.5, max_retries: int = 3):
        if post is None:
            import requests
            post = requests.post
        self.api_key, self.model = api_key, model
        self._post, self._sleep, self._clock = post, sleep, clock
        self.min_interval, self.max_retries = min_interval, max_retries
        self._last_call: Optional[float] = None

    def _throttle(self) -> None:
        if self._last_call is not None:
            wait = self.min_interval - (self._clock() - self._last_call)
            if wait > 0:
                self._sleep(wait)
        self._last_call = self._clock()

    def label(self, jobs: list[dict]) -> dict[int, Eligibility]:
        body = {
            "contents": [{"role": "user", "parts": [{"text": build_prompt(jobs)}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                 "responseSchema": RESPONSE_SCHEMA},
        }
        rate_limited = 0
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self._post(API_URL.format(model=self.model), json=body, timeout=120,
                                  headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"})
            except Exception as exc:  # noqa: BLE001 - network trouble: try again, then give up on this batch
                log.warning("Gemini request failed: %s", exc.__class__.__name__)
                self._sleep(10 * (attempt + 1))
                continue
            if resp.status_code == 200:
                try:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                except (ValueError, KeyError, IndexError, TypeError):
                    log.warning("Gemini response had no text part; batch skipped")
                    return {}
                return parse_labels(text, jobs)
            if resp.status_code == 429:
                rate_limited += 1
                self._sleep(30 * rate_limited)
                continue
            if resp.status_code >= 500:
                self._sleep(10 * (attempt + 1))
                continue
            log.warning("Gemini HTTP %s; batch skipped", resp.status_code)
            return {}
        if rate_limited >= self.max_retries:
            raise QuotaExhausted(f"HTTP 429 {rate_limited} times in a row")
        return {}
