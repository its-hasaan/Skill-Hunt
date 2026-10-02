"""
Job attributes read from the title and description:

- min_years(text)        smallest "N(+) years ... experience" requirement (1-15)
- seniority(title, yrs)  intern | junior | mid | senior | lead
- tz_overlap(text)       americas | europe | apac when the posting asks for
                         working-hours overlap with that zone
- salary_from_text(text) (low, high, currency) for an annual salary range in
                         the text; monthly ranges are annualised, hourly ones
                         ignored
"""
from __future__ import annotations

import re
from typing import Optional

# --- years of experience ------------------------------------------------------

_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                 "eight": 8, "nine": 9, "ten": 10}
_YEARS_RE = re.compile(
    r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:\+|plus)?\s*"
    r"(?:(?:-|–|to)\s*\d{1,2}\s*\+?\s*)?years?\b", re.IGNORECASE)
_EXPERIENCE_RE = re.compile(r"experience", re.IGNORECASE)
_EXPERIENCE_WINDOW = 60


def min_years(text: Optional[str]) -> Optional[int]:
    found = []
    for m in _YEARS_RE.finditer(text or ""):
        word = m.group(1).lower()
        value = int(word) if word.isdigit() else _WORD_NUMBERS[word]
        if not 1 <= value <= 15:
            continue
        window = text[max(0, m.start() - _EXPERIENCE_WINDOW): m.end() + _EXPERIENCE_WINDOW]
        if _EXPERIENCE_RE.search(window) and not re.search(r"\bago\b", text[m.end(): m.end() + 10]):
            found.append(value)
    return min(found) if found else None


# --- seniority ----------------------------------------------------------------

_SENIORITY_PATTERNS = [
    ("intern", re.compile(r"\b(?:intern|internship|co-?op)\b", re.IGNORECASE)),
    ("lead", re.compile(r"\b(?:staff|principal|lead|head of|director|vp|vice president|chief|architect|"
                        r"distinguished|fellow|(?:engineering|data|analytics|qa|software|development|"
                        r"devops|it|security|support) manager)\b", re.IGNORECASE)),
    ("senior", re.compile(r"\b(?:senior|sr)\b\.?|\b(?:iii|iv|v)\s*$", re.IGNORECASE)),
    ("junior", re.compile(r"\b(?:junior|jr|entry[- ]level|graduate|grad|trainee|apprentice|associate)\b|"
                          r"\bi\s*$", re.IGNORECASE)),
    ("mid", re.compile(r"\bii\s*$|\bmid[- ]level\b", re.IGNORECASE)),
]


def seniority(title: Optional[str], years: Optional[int] = None) -> str:
    title = (title or "").strip()
    for level, pattern in _SENIORITY_PATTERNS:
        if pattern.search(title):
            return level
    if years is not None:
        if years < 2:
            return "junior"
        if years >= 5:
            return "senior"
    return "mid"


# --- timezone overlap -----------------------------------------------------------

_TZ_CONTEXT = re.compile(r"overlap|hours|time ?zones?|timezone|working day|business day|standup|aligned with",
                         re.IGNORECASE)
_TZ_REGIONS = [
    ("americas", re.compile(r"\b(?:EST|EDT|PST|PDT|CST|CDT|MST|ET|PT|CT)\b|"
                            r"(?i:\b(?:us|u\.s\.|american|north american|americas|eastern|pacific)\s+"
                            r"(?:standard\s+)?(?:time ?zones?|hours|time)\b)")),
    ("europe", re.compile(r"\b(?:CET|CEST|GMT|BST|WET|EET|UTC\s?[+]\s?[0-2])\b|"
                          r"(?i:\b(?:european|europe|uk|central european)\s+(?:time ?zones?|hours|business hours)\b)")),
    ("apac", re.compile(r"\b(?:SGT|AEST|AEDT|JST|HKT)\b|(?i:\b(?:apac|asia|asian)\s+(?:time ?zones?|hours)\b)")),
]


def tz_overlap(text: Optional[str]) -> Optional[str]:
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        if not _TZ_CONTEXT.search(sentence):
            continue
        hits = [(m.start(), region) for region, pattern in _TZ_REGIONS for m in [pattern.search(sentence)] if m]
        if hits:
            return min(hits)[1]
    return None


# --- salary ---------------------------------------------------------------------

_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
_AMOUNT = r"(?P<{c}>[$€£₹]|USD|EUR|GBP|INR|CAD|AUD)?\s?(?P<{n}>\d{{1,3}}(?:[,.]\d{{2,3}})+|\d+(?:\.\d+)?)\s?(?P<{k}>[kK])?"
_RANGE_RE = re.compile(
    _AMOUNT.format(c="c1", n="n1", k="k1") + r"\s*(?:-|–|—|to)\s*" + _AMOUNT.format(c="c2", n="n2", k="k2"))
_HOURLY = re.compile(r"per hour|/\s?h(?:ou)?r\b|hourly|an hour", re.IGNORECASE)
_MONTHLY = re.compile(r"per month|/\s?mo(?:nth)?\b|monthly|a month", re.IGNORECASE)


def _amount(number: str, thousands: Optional[str]) -> float:
    if re.fullmatch(r"\d{1,3}(?:[,.]\d{2,3})+", number):
        value = float(re.sub(r"[,.]", "", number))
    else:
        value = float(number)
    return value * 1000 if thousands else value


def salary_from_text(text: Optional[str]):
    for m in _RANGE_RE.finditer(text or ""):
        currency = m.group("c1") or m.group("c2")
        if not currency:
            continue  # "3-5 years": a range needs a currency marker
        currency = _CURRENCY_SYMBOLS.get(currency, currency.upper())
        # "$120 - $150K": a K on either side applies to the low end too
        low = _amount(m.group("n1"), m.group("k1") or m.group("k2"))
        high = _amount(m.group("n2"), m.group("k2"))
        after = text[m.end(): m.end() + 40]
        if _HOURLY.search(after):
            continue
        if _MONTHLY.search(after):
            low, high = low * 12, high * 12
        if 10_000 <= low <= high < 50_000_000:
            return low, high, currency
    return None
