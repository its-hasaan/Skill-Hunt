"""
Compile taxonomy terms into skill matchers — the single implementation
shared by the ETL (skill_extractor.FastPathExtractor) and the API
(backend ResumeSkillExtractor), so a resume, a job post and the dashboard
always agree on which skills a text contains.

Taxonomy entry fields:
  name, aliases      terms to match; case-insensitive, whole-word by default
  case_sensitive     exact-case forms for terms whose lowercase form is an
                     ordinary English word ("Go", "REST", "Spark", "Excel")
  not_followed_by    regex; the match must NOT be followed by it ("Go to")
  not_preceded_by    regex; tested against the 20 chars before the match
                     (Python lookbehind must be fixed-width, so it's checked
                     in code), e.g. "&\\s*$" so "P&R" isn't the R language
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Terms whose punctuation needs hand-written boundaries.
SPECIAL_TERMS = {
    "C++": r"(?<![a-zA-Z])C\+\+(?![a-zA-Z])",
    "C#": r"(?<![a-zA-Z])C#(?![a-zA-Z])",
    ".NET": r"(?<![a-zA-Z])\.NET(?![a-zA-Z0-9])",
    "Node.js": r"\bNode\.?js\b",
    "Vue.js": r"\bVue\.?js\b",
    "Next.js": r"\bNext\.?js\b",
    "Nuxt.js": r"\bNuxt\.?js\b",
    "D3.js": r"\bD3\.?js\b",
    "Three.js": r"\bThree\.?js\b",
}
PRECEDING_WINDOW = 20


@dataclass(frozen=True)
class SkillPattern:
    canonical: str
    regex: re.Pattern
    not_preceded: re.Pattern | None = None

    def count(self, text: str) -> int:
        if self.not_preceded is None:
            return sum(1 for _ in self.regex.finditer(text))
        return sum(
            1 for m in self.regex.finditer(text)
            if not self.not_preceded.search(text[max(0, m.start() - PRECEDING_WINDOW):m.start()])
        )


def _term_regex(term: str, case_sensitive: bool, not_followed_by: str | None) -> re.Pattern:
    body = SPECIAL_TERMS.get(term) or rf"(?<!\w){re.escape(term)}(?!\w)"
    if not_followed_by:
        body = f"{body}(?!{not_followed_by})"
    return re.compile(body, 0 if case_sensitive else re.IGNORECASE)


def build_patterns(skills: list[dict]) -> list[SkillPattern]:
    patterns = []
    for skill in skills:
        exact = {t.lower(): t for t in skill.get("case_sensitive", [])}
        guard = skill.get("not_followed_by")
        before = re.compile(skill["not_preceded_by"]) if skill.get("not_preceded_by") else None
        seen = set()
        for term in [skill["name"], *skill.get("aliases", [])]:
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            if key in exact:
                regex = _term_regex(exact[key], True, guard)
            else:
                regex = _term_regex(term, False, guard)
            patterns.append(SkillPattern(skill["name"], regex, before))
    return patterns
