"""
Rule-based eligibility: can someone living in Pakistan / India apply?

classify(job) reads the structured location fields and the description and
returns an Eligibility with a tri-state per country (True / False / None =
unclear), the evidence it decided from, and a confidence. It only says True
on explicit evidence: a worldwide statement, a region that contains the
country, or the country itself. Missing a job is better than wrongly
promising someone they can apply (spec §6.3).

Decision order (first that applies wins):
  1. onsite / hybrid jobs (and keyword-source local jobs with no workplace
     field): eligible only in the job's own country
  2. restriction sentences in the description ("must be based in X",
     "authorized to work in X", "open to candidates in X", "remote within
     X", "US work authorization", ...): the places they name
  3. worldwide sentences ("work from anywhere in the world", "we hire
     globally") when the location fields name no country
  4. the places named in the location fields
  5. otherwise unclear

Boilerplate that mentions places without restricting the hire (export
control notices, pay-transparency ranges, legal notices, office lists) is
ignored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .fingerprint import title_place_text
from .geo import Places, membership, merge, parse_places

RULES_VERSION = 2  # 2: place suffixes in titles count as location evidence

COUNTRIES_OF_INTEREST = ("pk", "in")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|\s*[••]\s*")

# Sentences that mention places without restricting who can be hired.
_BOILERPLATE = re.compile(
    r"export|compensation|salary|salaries|pay range|base pay|\bote\b|on target|arrest|conviction|"
    r"e-verify|equal opportunity|equal employment|pay transparency|benefits|401\(k\)|headquarter|\bhq\b|"
    r"offices? (?:in|around|across)|customers? (?:in|across)|clients? (?:in|across)|founded|"
    r"the customer is", re.IGNORECASE)

# Each trigger is followed by the places it restricts to ("the tail").
_RESTRICTION_TRIGGERS = [
    # must be based / located / living in, need to reside in ...
    r"\b(?:must|need to|needs to|required to|require[sd]?|have to|has to|should)\b[^.;]{0,40}?"
    r"\b(?:based|located|living|residing|reside|resident|live|work(?:ing)? remotely|work|sit)"
    r"\s+(?:in|within|from|out of)\b",
    # open to / limited to candidates (based / residing) in ...
    r"\b(?:open|available|limited|restricted)\s+(?:only\s+)?to\s+"
    r"(?:(?:candidates|applicants|residents|people|individuals|those|anyone|talent)\s+)?"
    r"(?:(?:who are|who)\s+)?(?:currently\s+)?(?:(?:based|located|living|residing|reside|live)\s+)?"
    r"(?:in|within|from|of)\b",
    # candidates based in / applicants located in
    r"\b(?:candidates|applicants|residents)\s+(?:currently\s+)?(?:based|located|living|residing)\s+(?:in|within)\b",
    # authorised / eligible to work in, work authorisation in
    r"\b(?:authori[sz]ed|eligible|permitted|legally able|right)\s+to\s+work\s+(?:in|for)\b",
    r"\bwork\s+(?:authori[sz]ation|permit|visa)\s+(?:in|for)\b",
    # this role is (fully remote-)based in / can be remote in
    r"\b(?:role|position|job|opportunity)\s+(?:is|will be|can be|must be)\s+(?:[\w-]+\s+){0,3}?"
    r"(?:based|located|remote|remote-based|performed|done|executed|open)\s+(?:in|within|from|out of|to)\b",
    # remote in / remote within / remotely from
    r"\bremote(?:ly)?(?:[- ]based)?\s+(?:in|within|from)\b",
    # anywhere in X
    r"\banywhere\s+(?:with)?in\b",
    # hiring in / across X
    r"\bhiring\s+(?:in|across|from|throughout)\b",
]
_RESTRICTION_RE = [re.compile(p, re.IGNORECASE) for p in _RESTRICTION_TRIGGERS]

# Restrictions where the place comes first: "US work authorization", "US citizens".
_PREFIX_RE = re.compile(
    r"(?<![A-Za-z])(US|U\.S\.|USA|United States|UK|Canadian|American|EU|European)[- ]"
    r"(?:work authori[sz]ation|citizens?(?:hip)?|residents?|residency|work permit|based (?:candidates|applicants|only))",
    re.IGNORECASE)
_PREFIX_PLACES = {"us": "us", "u.s.": "us", "usa": "us", "united states": "us", "american": "us",
                  "uk": "gb", "canadian": "ca"}
_PREFIX_REGIONS = {"eu": "europe", "european": "europe"}

_WORLDWIDE_RE = re.compile(
    r"\banywhere in the world\b|\bwork(?:ing)? from anywhere\b(?!\s+(?:with)?in\b)|"
    r"\blocation[- ](?:independent|agnostic)\b|\b(?:fully )?remote,? (?:world ?wide|globally)\b|"
    r"\bhire (?:talent |people )?(?:from )?(?:all over|around) the world\b|"
    r"\b(?:hire|hiring|recruit(?:ing)?) (?:globally|worldwide|internationally|from anywhere)\b|"
    r"\bopen to (?:candidates|applicants|people|talent) (?:from )?(?:anywhere|worldwide|globally|"
    r"all over the world|around the world)\b", re.IGNORECASE)
_REGARDLESS_RE = re.compile(r"\bregardless of (?:your )?(?:location|where you live|country)\b", re.IGNORECASE)
_HIRING_CONTEXT = re.compile(r"\b(?:hire|hiring|candidates?|applicants?|apply|work from|join us)\b", re.IGNORECASE)

# Timezone names inside a restriction tail ("based in the Eastern Time zone").
_TZ_REGIONS = [
    # Words case-insensitive; abbreviations in capitals only ("est" is French for "is").
    (re.compile(r"(?i:\b(?:eastern|pacific|central|mountain)\s+(?:standard\s+)?time\b|\bnorth american\b|"
                r"\bus time ?zones?\b|\bamericas? time ?zones?\b)|\b(?:EST|EDT|PST|PDT|CST|MST)\b"), "americas"),
    (re.compile(r"(?i:\bcentral european\b)|\b(?:CET|CEST|GMT|BST)\b"), "europe"),
]

_TAIL_CHARS = 100


@dataclass
class Eligibility:
    remote_scope: str
    eligible_countries: list = field(default_factory=list)
    eligible_regions: list = field(default_factory=list)
    eligible_pk: Optional[bool] = None
    eligible_in: Optional[bool] = None
    confidence: float = 0.3
    evidence: str = ""
    method: str = "rules"


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s and s.strip()]


def _tail_places(tail: str) -> Places:
    places = parse_places(tail, structured=False)
    regions = set(places.regions)
    for pattern, region in _TZ_REGIONS:
        if pattern.search(tail):
            regions.add(region)
    if (places.countries or regions - {"worldwide"}) and "worldwide" in regions:
        regions.discard("worldwide")  # "anywhere in the UK" means the UK
    return Places(places.countries, frozenset(regions), places.remote)


def _restriction(sentence: str) -> Optional[Places]:
    if _BOILERPLATE.search(sentence):
        return None
    found = []
    for pattern in _RESTRICTION_RE:
        for m in pattern.finditer(sentence):
            places = _tail_places(sentence[m.end(): m.end() + _TAIL_CHARS])
            if not places.empty:
                found.append(places)
    for m in _PREFIX_RE.finditer(sentence):
        word = m.group(1).lower()
        if word in _PREFIX_PLACES:
            found.append(Places(frozenset({_PREFIX_PLACES[word]}), frozenset(), False))
        else:
            found.append(Places(frozenset(), frozenset({_PREFIX_REGIONS[word]}), False))
    return merge(*found) if found else None


def _is_worldwide(sentence: str) -> bool:
    if _WORLDWIDE_RE.search(sentence):
        return True
    return bool(_REGARDLESS_RE.search(sentence) and _HIRING_CONTEXT.search(sentence))


def _scope(places: Places) -> str:
    """The broadest place named: worldwide > regions > countries."""
    if "worldwide" in places.regions:
        return "worldwide"
    if places.regions:
        return "regions"
    return "countries" if places.countries else "unclear"


def _location_membership(places: Places, country: str):
    """Location fields like "Asia; Hong Kong; Taiwan, Taipei" use the region as
    a label next to the real places, so a region only counts as a promise
    when no specific countries are listed (worldwide/global always counts)."""
    answer = membership(places, country)
    if (answer is True and country not in places.countries and places.countries
            and "worldwide" not in places.regions):
        return None
    return answer


def _labelled(places: Places, confidence: float, evidence: str, from_location: bool = False) -> Eligibility:
    member = _location_membership if from_location else membership
    pk, inn = (member(places, c) for c in COUNTRIES_OF_INTEREST)
    scope = _scope(places)
    if pk is None or inn is None:
        confidence = min(confidence, 0.5)
    return Eligibility(
        remote_scope=scope,
        eligible_countries=sorted(places.countries),
        eligible_regions=sorted(places.regions),
        eligible_pk=pk, eligible_in=inn,
        confidence=confidence,
        evidence=evidence[:300],
    )


def _location_text(job: dict) -> str:
    parts = [job.get("location_display") or ""] + list(job.get("location_areas") or [])
    seen, unique = set(), []
    for p in parts:
        p = (p or "").strip()
        if p and p.lower() not in seen:
            seen.add(p.lower())
            unique.append(p)
    return "; ".join(unique)


def classify(job: dict) -> Eligibility:
    workplace = (job.get("workplace_type") or "").lower()
    country = (job.get("country_code") or "").lower()
    location = _location_text(job)

    # 1. onsite / hybrid: you have to be there.
    if workplace in ("onsite", "hybrid") or (not workplace and country in COUNTRIES_OF_INTEREST):
        here = {country} if country in COUNTRIES_OF_INTEREST else set(parse_places(location).countries)
        return Eligibility(
            remote_scope=workplace or "onsite",
            eligible_countries=sorted(here),
            eligible_pk="pk" in here, eligible_in="in" in here,
            confidence=0.9, evidence=location[:300],
        )

    sentences = _sentences(job.get("description") or "")

    # 2. restriction sentences
    restrictions = [(s, p) for s in sentences if (p := _restriction(s)) is not None]
    if restrictions:
        places = merge(*(p for _, p in restrictions))
        return _labelled(places, 0.85, restrictions[0][0])

    # "Data Engineer (US Remote)", "... - EMEA Remote": the title's place suffix counts as a location
    location = "; ".join(p for p in (location, title_place_text(job.get("title"))) if p)
    location_places = parse_places(location)

    # 3. worldwide statements, unless the location fields name countries
    if not location_places.countries:
        for s in sentences:
            if _is_worldwide(s):
                return _labelled(Places(frozenset(), frozenset({"worldwide"}), True), 0.8, s)

    # 4. the location fields
    if not location_places.empty:
        confidence = 0.8 if location_places.countries else 0.7
        if location_places.regions == {"worldwide"} and not location_places.countries:
            confidence = 0.75
        return _labelled(location_places, confidence, location, from_location=True)

    # 5. nothing to go on
    return Eligibility(remote_scope="unclear", confidence=0.3, evidence="")
