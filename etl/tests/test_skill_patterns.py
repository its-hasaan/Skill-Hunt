from skill_patterns import build_patterns


def counts(skills, text):
    out = {}
    for p in build_patterns(skills):
        n = p.count(text)
        if n:
            out[p.canonical] = out.get(p.canonical, 0) + n
    return out


def test_default_terms_are_case_insensitive_whole_words():
    skills = [{"name": "Python", "aliases": ["py3"]}]
    assert counts(skills, "python and PY3, not pythonic") == {"Python": 2}


def test_case_sensitive_term_ignores_lowercase_word():
    skills = [{"name": "Apache Spark", "aliases": ["spark"], "case_sensitive": ["Spark"]}]
    assert counts(skills, "ideas that spark joy") == {}
    assert counts(skills, "Spark and apache spark") == {"Apache Spark": 2}


def test_not_followed_by_blocks_phrases():
    skills = [{"name": "Go", "aliases": ["golang"], "case_sensitive": ["Go"],
               "not_followed_by": r"[\s\-]+(?:to|live|further)\b"}]
    assert counts(skills, "Go-to-market. Go live. Go further.") == {}
    assert counts(skills, "Python, Go and golang") == {"Go": 2}


def test_not_preceded_by_blocks_prefix():
    skills = [{"name": "R", "case_sensitive": ["R"], "not_followed_by": r"\s*[&+']",
               "not_preceded_by": r"&\s*$"}]
    assert counts(skills, "R&D, P&R and R's") == {}
    assert counts(skills, "Python, R, SQL") == {"R": 1}


def test_symbol_edged_terms_match():
    skills = [{"name": "C++"}, {"name": "C#"}, {"name": ".NET"}, {"name": "CI/CD"}, {"name": "Node.js"}]
    assert counts(skills, "C++, C#, .NET 8, CI/CD and Node.js") == {
        "C++": 1, "C#": 1, ".NET": 1, "CI/CD": 1, "Node.js": 1}


def test_terms_do_not_match_inside_other_words():
    skills = [{"name": "Git"}, {"name": "SQL"}]
    assert counts(skills, "digital MySQL") == {}


def test_prefilter_never_changes_counts():
    import json
    from pathlib import Path
    taxonomy = json.loads((Path(__file__).resolve().parents[1] / "config" / "skills_taxonomy.json")
                          .read_text(encoding="utf-8"))["skills"]
    texts = ["Senior Data Engineer: Python, SQL, Apache Spark, AWS Glue, Airflow; C++ and C# a plus.",
             "We go further. REST APIs with Node.js, Next.js, Vue.js, .NET 8 and D3.js charts.",
             "Excel at client relations. R, Go, golang, TS/TypeScript, CI/CD on Kubernetes (EKS)."]
    for p in build_patterns(taxonomy):
        for text in texts:
            assert p.count(text, text.lower()) == p.count(text), (p.canonical, p.regex.pattern, text)


def test_needle_skips_regex_when_literal_absent():
    (p,) = build_patterns([{"name": "Kubernetes"}])
    assert p.needle == "kubernetes"
    assert p.count("we use docker", "we use docker") == 0
