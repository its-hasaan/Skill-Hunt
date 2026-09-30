import json
from pathlib import Path

from skill_patterns import build_patterns

TAXONOMY = json.loads((Path(__file__).resolve().parents[1] / "config" / "skills_taxonomy.json")
                      .read_text(encoding="utf-8"))["skills"]
# Lowercase English words that are also skill names/aliases: they may only
# appear as case-sensitive terms (or not at all).
ENGLISH_WORDS = {"go", "r", "rest", "spark", "swift", "rust", "dart", "excel", "next", "express",
                 "image", "less", "spring", "airflow", "superset", "glue", "lambda", "synapse",
                 "athena", "hive", "prefect", "luigi", "presto", "stitch", "puppet", "windows",
                 "karma", "node", "elastic", "dash", "vertex", "sentinel", "storage", "shell",
                 "claude", "gemini", "ts", "sas", "soap", "waf", "ecs", "jms", "kms", "edr",
                 "sso", "mq", "ge", "tf", "pd", "dl", "react", "tableau", "warehouse", "oracle"}


def skill_counts(text):
    out = {}
    for p in build_patterns(TAXONOMY):
        n = p.count(text)
        if n:
            out[p.canonical] = out.get(p.canonical, 0) + n
    return out


def test_no_discovered_leftovers():
    assert [s["name"] for s in TAXONOMY if s.get("_discovered")] == []


def test_no_term_owned_by_two_skills():
    owner = {}
    clashes = []
    for s in TAXONOMY:
        for term in {s["name"].lower(), *(a.lower() for a in s.get("aliases", []))}:
            if term in owner and owner[term] != s["name"]:
                clashes.append((term, owner[term], s["name"]))
            owner[term] = s["name"]
    assert clashes == []


def test_english_words_are_only_case_sensitive():
    offenders = []
    for s in TAXONOMY:
        exact = {t.lower() for t in s.get("case_sensitive", [])}
        for term in [s["name"], *s.get("aliases", [])]:
            if term.lower() in ENGLISH_WORDS and term.lower() not in exact:
                offenders.append((s["name"], term))
    assert offenders == []


def test_common_words_do_not_match():
    text = ("We go further and go live soon. The rest of the team will excel at next steps. "
            "Express interest in our company image. Less is more; spring season sparks joy. "
            "Glue code, lambda functions and a superset of R&D ideas.")
    assert skill_counts(text) == {}


def test_real_skills_still_match():
    found = skill_counts("Python, Go, R, REST APIs, Apache Spark, Excel, Next.js, Express.js, "
                         "Spring Boot, Airflow, AWS Glue, AWS Lambda, React, Tableau, Figma, Cypress")
    for skill in ["Python", "Go", "R", "REST API", "Apache Spark", "Excel", "Next.js", "Express.js",
                  "Spring Boot", "Apache Airflow", "AWS Glue", "AWS Lambda", "React", "Tableau",
                  "Figma", "Cypress"]:
        assert skill in found, skill


def test_every_skill_has_a_category():
    assert [s["name"] for s in TAXONOMY if not s.get("category")] == []
