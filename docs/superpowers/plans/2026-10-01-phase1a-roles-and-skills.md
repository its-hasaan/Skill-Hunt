# Phase 1a: Roles & Skill Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make roles and skills trustworthy enough to sell. That means 20 roles with titles validated against the role, one skill-matching engine shared by the ETL and the API, a curated taxonomy with no junk and no English-word false positives, and a backfill that re-cleans the 69k stored jobs.

**Architecture:**
- A new standalone module, `etl/skill_patterns.py`, compiles taxonomy terms into matchers. It supports case-sensitive terms and exclusion guards, and both `FastPathExtractor` (ETL) and `ResumeSkillExtractor` (API) use it, so the resume analyzer, extension, and dashboard always agree.
- A one-off curation script rewrites `skills_taxonomy.json`, and lint tests keep it clean from then on.
- `RoleMatcher` grows to 20 roles. The transformer re-validates the searched role of keyword-searched sources (Adzuna, Jooble) against the title.
- `ops/reextract.py` re-applies roles and skills to existing staging rows.

**Tech Stack:** Python 3.11, `re`, psycopg2, pytest (+ Postgres container), FastAPI backend.

**Spec:** `docs/superpowers/specs/2026-09-30-jobwise-product-roadmap-design.md` §6.4 (roles & taxonomy; PIPELINE_REVIEW #1 and #3) and decision D7.

## Global Constraints

- Roles (exact names): the 15 existing roles + `Software Engineer`, `QA Engineer`, `UI/UX Designer`, `Product Manager`, `Technical Support Engineer`.
- Adzuna keeps searching only the original 15 roles (`adzuna_roles` in `extraction_config.json`); the new roles come from sources without a query quota.
- Keyword-searched sources = `adzuna`, `jooble`. For those, the title decides the role; a title that matches no role is not transformed (it's recorded in `raw.jobs.skip_reason`).
- **Stop and ask the owner** if the backfill dry run would drop more than 25% of staging jobs.
- One skill-matching implementation (`etl/skill_patterns.py`); the backend imports it and does not keep its own copy.
- Git: commit and push each task to `main` when its tests pass; 5–8 word messages; no Claude attribution; stage only the touched files.

## Review Focus

1. **A lowercase English word that equals a skill term** ("go further", "the rest of", "next steps", "spring season", "excel at"). Expected: no skill match. Test: Task 3 `test_common_words_do_not_match` (real taxonomy).
2. **The same term claimed by two skills** (e.g. `sql server` under both SQL and Microsoft SQL Server) double-counts. Expected: every term belongs to exactly one skill. Test: Task 3 `test_no_term_owned_by_two_skills`.
3. **The backend and ETL disagree on a resume's skills.** Expected: identical results for the same text. Test: Task 2 `test_backend_and_etl_extract_identically`.
4. **Generic titles** ("Senior Software Engineer, Data Platform", "Software Engineer - Backend"). Expected: the specific role wins, and `Software Engineer` only catches truly generic titles. Test: Task 4 `test_role_precedence`.
5. **Re-running the backfill.** Expected: idempotent, with no duplicate skill rows. Test: Task 6 `test_reextract_is_idempotent`.

---

## File Structure

| File | Responsibility |
|---|---|
| `etl/skill_patterns.py` (new) | `SkillPattern`, `build_patterns(skills)`: term → regex with case/lookaround rules |
| `etl/skill_extractor/fast_path.py` (modify) | Use `build_patterns`; `count()` instead of `findall` |
| `backend/app/routers/resume.py` (modify) | `ResumeSkillExtractor` uses `build_patterns` (path to `etl/` added to `sys.path`) |
| `etl/tools/curate_taxonomy_2026_10.py` (new, one-off) | Declarative REMOVE / MERGE / RENAME / RULES / ALIAS fixes / NEW skills → rewrites `skills_taxonomy.json` |
| `etl/config/skills_taxonomy.json` (regenerated) | Curated taxonomy |
| `etl/tests/test_skill_patterns.py`, `test_taxonomy.py` | Compiler unit tests; taxonomy lint + real-text behaviour tests |
| `etl/connectors/utils.py` (modify) | `_ROLE_PATTERNS` for 20 roles |
| `etl/config/extraction_config.json` (modify) | `roles` (20) + `adzuna_roles` (15) |
| `etl/extractor.py` (modify) | Search `adzuna_roles` when present |
| `database/migrations/009_new_roles.sql` | Seed `staging.dim_job_roles` with the 5 new roles |
| `database/migrations/010_raw_skip_reason.sql` | `raw.jobs.skip_reason` |
| `etl/transformer.py` (modify) | Role validation for keyword sources; skip-marker; `get_unprocessed_jobs` ignores skipped rows |
| `etl/ops/reextract.py` (new) | Backfill: re-validate roles and re-extract skills on staging; sync `dim_skills` |
| `frontend/src/utils/helpers.js` (modify) | Colour slots for the new categories |
| `backend/tests/test_resume_extractor.py` (new) | Backend/ETL parity |

---

### Task 1: Shared skill-pattern compiler

**Files:** Create `etl/skill_patterns.py`, `etl/tests/test_skill_patterns.py`

**Interfaces — Produces:** `SkillPattern(canonical: str, regex: re.Pattern, not_preceded: re.Pattern | None)` with `.count(text) -> int`; `build_patterns(skills: list[dict]) -> list[SkillPattern]`; `SPECIAL_TERMS: dict[str, str]`.

Taxonomy entry fields honoured: `name`, `aliases`, `case_sensitive` (list of exact-case terms; a name/alias equal to one of them case-insensitively is compiled case-sensitively in that exact form), `not_followed_by` (regex; negative lookahead after every term of the skill), `not_preceded_by` (regex; checked against the 20 chars before a match).

- [ ] **Step 1: Write the failing tests** (`etl/tests/test_skill_patterns.py`)
```python
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
```

- [ ] **Step 2: Run to verify failure** — `cd etl && ../venv/Scripts/python -m pytest tests/test_skill_patterns.py -v` → `ModuleNotFoundError: skill_patterns`.

- [ ] **Step 3: Implement `etl/skill_patterns.py`**
```python
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
```

- [ ] **Step 4: Run the tests** → all pass. **Step 5: Commit** `git add etl/skill_patterns.py etl/tests/test_skill_patterns.py` → `git commit -m "Add shared skill pattern compiler"` → push.

---

### Task 2: ETL and API use the shared compiler

**Files:** Modify `etl/skill_extractor/fast_path.py` (`_load_taxonomy_data`, `_compile_pattern`, `extract_skills`, `add_skill`), `backend/app/routers/resume.py` (`ResumeSkillExtractor`); create `backend/tests/test_resume_extractor.py`.

**Interfaces — Consumes:** `build_patterns`, `SkillPattern.count`. **Produces:** `ResumeSkillExtractor(taxonomy_path: Path = TAXONOMY_PATH)` (optional path for tests); `FastPathExtractor.patterns: list[SkillPattern]`.

- [ ] **Step 1: Failing parity test** (`backend/tests/test_resume_extractor.py`)
```python
import json
import sys
from pathlib import Path

from app.routers.resume import ResumeSkillExtractor

ETL = Path(__file__).resolve().parents[2] / "etl"
sys.path.insert(0, str(ETL))
from skill_extractor.fast_path import FastPathExtractor  # noqa: E402

SKILLS = {"skills": [
    {"name": "Go", "aliases": ["golang"], "case_sensitive": ["Go"],
     "not_followed_by": r"[\s\-]+(?:to|further)\b", "category": "Programming Language"},
    {"name": "Apache Spark", "aliases": ["spark"], "case_sensitive": ["Spark"], "category": "Big Data"},
]}
TEXT = "We go further. Go to market. Python, Go, golang and Spark; sparks fly."


def names(results):
    return {r["skill_name"]: r["mention_count"] for r in results}


def test_backend_and_etl_extract_identically(tmp_path):
    path = tmp_path / "tax.json"
    path.write_text(json.dumps(SKILLS))
    backend = names(ResumeSkillExtractor(path).extract_skills(TEXT))
    etl = names(FastPathExtractor(taxonomy_path=path).extract_skills(TEXT))
    assert backend == etl == {"Go": 2, "Apache Spark": 1}
```
- [ ] **Step 2: Run** `cd backend && ./venv/Scripts/python -m pytest tests/test_resume_extractor.py -v` → FAIL (`ResumeSkillExtractor()` takes no path / counts "go further").
- [ ] **Step 3: Implement.**
  - In `fast_path.py`: `from skill_patterns import build_patterns` (with `sys.path` holding `etl/`, as it does for the transformer). `_load_taxonomy_data` stores metadata as today, then does `self.patterns = build_patterns(skills_list)`. `extract_skills` loops `for p in self.patterns: n = p.count(text)`, keyed by `p.canonical`. `add_skill` extends via `build_patterns([{"name": name, "aliases": aliases}])`. Delete `_compile_pattern` (its special cases now live in `SPECIAL_TERMS`).
  - In `resume.py`: add `ETL_DIR = Path(__file__).resolve().parents[3] / "etl"`, then `sys.path.insert(0, str(ETL_DIR))` and `from skill_patterns import build_patterns`. `ResumeSkillExtractor.__init__(self, taxonomy_path: Path = TAXONOMY_PATH)` builds `self.patterns = build_patterns(skills)` and keeps `self.skills` metadata. `extract_skills` uses `p.count(text)` and looks up category and subcategory from `self.skills[p.canonical.lower()]`.
- [ ] **Step 4: Run both suites** — `cd etl && ../venv/Scripts/python -m pytest -q` and `cd backend && ./venv/Scripts/python -m pytest -q` → all pass. Also run `./venv/Scripts/python -c "import app.main"` → no error.
- [ ] **Step 5: Commit** — `git commit -m "Share skill matching between ETL and API"` → push. (Render redeploys the API; the extraction behaviour is unchanged until Task 3's taxonomy lands.)

---

### Task 3: Curate the taxonomy + lint tests

**Files:** Create `etl/tools/curate_taxonomy_2026_10.py`, `etl/tests/test_taxonomy.py`; regenerate `etl/config/skills_taxonomy.json`; modify `frontend/src/utils/helpers.js` (`CATEGORY_SLOTS`).

**Interfaces — Consumes:** `build_patterns`. **Produces:** a taxonomy with no `_discovered` flags. Every term belongs to one skill. Terms that are English words are case-sensitive.

- [ ] **Step 1: Failing lint + behaviour tests** (`etl/tests/test_taxonomy.py`)
```python
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
```
- [ ] **Step 2: Run** → FAIL (discovered leftovers, clashes, English words, false matches).
- [ ] **Step 3: Write `etl/tools/curate_taxonomy_2026_10.py`.** A declarative, idempotent one-off script. It reads the taxonomy and applies, in order, then writes it back sorted by (category, name):
  1. `REMOVE` — companies and employers: adjoe, ADP, airSlate, Atolls, Backbase, BEKO, Brighte, Cloud Imperium Games, CONXAI, Deel, DKV Mobility, Doctrine, Dropbox, Equinix, Fresha, Genpact, Gorgias, Gynzy, HUB24, ICE Data Services, Improvado, Lantern, LetsGrow.com, Luxury Presence, Marina Bay Sands, "Meta Platforms, Inc.", Mirakl Nexus, Mirakl Platform, OVHcloud, Prudential, QEMI, Rakuten Symphony, Rakuten Viki, Reaxys, Samsara, Service NSW, Service Stream, Sia, Spotify, SSP, Standard Chartered nexus, Stripe, The Key to Life, Veem, WPP Open, KnowBe4, Machine Learning Maestro, Materia AI, Secure Code Warrior, Sensorfact, ATHIA, High Touch, Human OS, Perplexity, CKEditor, Proofpoint, Eucalyptus, CGI.
     - Generic phrases: Azure Services, big data platform, Cloud DX, cloud platform, cloud platforms, cloud-based services, cloud-native platform, Container platform, Customer 360 platforms, Customer Data Platform, Digital Identity Services, enterprise data platform, enterprise-grade platforms, financial intelligence platform, fintech platform, Global Business Services, Global Data Platform, global investment platform, global platform, modern cloud platform, multi-cloud platform, next-generation AI infrastructure platform, next-generation ecommerce search and discovery platform, Next-generation Managed Services, Research and Data Platform, shared services, agentic frameworks, AI Engines, AI Studio, analytical frameworks, Architectures multi-agents, Custom API, Deep Learning algorithms, high-performance APIs, ML frameworks, trading systems, unified API, user access controls, 20tb databases, database schemas, La risorsa, Storage, warehouse, team backend, industry aligned programming languages, programming languages, Java-based, Python-based, Pythonie, Kotlin/Java, containerisation, containerization, container orchestration, data visualization tools, Investment Data Engineering, model versioning, monitoring systems, orchestration frameworks, orchestrazione agentica, performance monitoring, proactive monitoring, production monitoring, real-time monitoring, Transaction Monitoring, meccanismi di sicurezza, NATO SECRET, version control, versioning, Security Groups, SMS, Vertex, relational databases, SQL databases, data security, Data Analytics, CTR, CVR, RoAS, English, French, German, deutsch, eng, Englisch, Ingles, OData services, Secure SD-WAN, Global Data Platform.
  2. `MERGE` (variant → existing canonical; the variant's name and aliases become aliases of the canonical):
     - EC2→AWS EC2, EKS→Kubernetes, Lambda→AWS Lambda, RDS→AWS RDS, S3→AWS S3, Redshift→AWS Redshift, DynamoDB→AWS DynamoDB, Data Factory→Azure Data Factory, Azure Machine Learning→Azure ML, Google BigQuery→BigQuery, Dataflow→Google Dataflow, dbt Cloud→dbt, Airflow→Apache Airflow, Spark→Apache Spark, PySpark→Apache Spark, Confluent→Apache Kafka.
     - MariaDB→MySQL, MS SQL Server→Microsoft SQL Server, MSSQL→Microsoft SQL Server, SQL Server→Microsoft SQL Server, Oracle→Oracle Database, Postgres→PostgreSQL, T-SQL→SQL, vector databases→Vector Database.
     - data lakes→Data Lake, Data Warehouses→Data Warehouse, datawarehouses→Data Warehouse, enterprise data warehouse→Data Warehouse.
     - CSS3→CSS, HTML5→HTML, ES6→JavaScript, Golang→Go, AngularJS→Angular, Core Java→Java, Node→Node.js, NodeJS→Node.js, vuejs→Vue.js, React 18→React, React JS→React, React.js→React, SwiftUI→Swift, TS→TypeScript, Shell→Bash, PHP-developer→PHP, C# .Net→C#, C#.Net→C#, .NET Core→.NET, .NET 8→.NET.
     - CNNs→Deep Learning, LSTM→Deep Learning, Keras→TensorFlow, transformers→Hugging Face, Large Language Model→LLM, GPT→OpenAI, CUDNN→CUDA, CUDA kernels→CUDA, J2EE→Java EE, JEE→Java EE, SPRING BATCH→Spring Batch.
     - BitBucket→Git, Github→Git, Gitlab→Git, CI/CD pipelines→CI/CD, firewalls→Firewall, DevSecOps Engineer→DevSecOps, Swagger→OpenAPI, API development→REST API, REST→REST API, Recommendation Systems→Recommender Systems, multi-agent systems→AI Agents, agent orchestration→AI Agents, Agentic AI→AI Agents.
     - Oracle Cloud Infrastructure→Oracle Cloud, Salesforce Data Cloud→Salesforce, Salesforce Platform→Salesforce, Force.com platform→Salesforce, ServiceNow-based→ServiceNow, VMware Cloud Foundation→VMware, Microsoft Power Platform stays.
  3. `RENAME`: API Gateway→AWS API Gateway, CloudFront→AWS CloudFront, Cloud Functions→Google Cloud Functions, App Service→Azure App Service, Cosmos DB→Azure Cosmos DB, ECS→AWS ECS, SQS→AWS SQS, KMS→AWS KMS, MQ→IBM MQ (aliases: websphere mq, mqseries), Sentinel→Microsoft Sentinel (aliases: azure sentinel), RHEL→Red Hat Enterprise Linux (aliases: rhel), MDM→Master Data Management, jasmine→Jasmine, karma→Karma, langgraph→LangGraph, crewai→CrewAI, JetPack Compose→Jetpack Compose, LLaMA→Llama, Model Context Pro→Model Context Protocol, Monte Carlo→Monte Carlo Methods (category Statistics, aliases: monte carlo simulation), Recommender Systems (created by merge if absent), AI Agents (created if absent, category Machine Learning).
  4. `CATEGORY` fixes: JSON, XML, SOAP, OAuth, SAML, OpenAPI → "API & Integration"; Selenium, Jest, Jasmine, Karma → "Testing"; Microsoft 365 → "Productivity"; Microsoft Fabric → "Data Platform"; everything kept from the "Cloud Platform" bucket that isn't a cloud platform gets its real category (Salesforce, ServiceNow → "Business Applications"; Vercel → "DevOps"; VMware, OpenStack → "Cloud").
  5. `ALIAS_REMOVALS` (dangerous or duplicated aliases): Next.js −`next`; Express.js −`express`; Computer Vision −`image`; Great Expectations −`ge`; CSS −`less`; Elasticsearch −`elastic`; Plotly −`dash`; Vertex AI −`vertex`; TensorFlow −`tf`; Pandas −`pd`; Deep Learning −`dl`; Bash −`shell`; Flutter −`dart`; C# −`dotnet`, −`.net`; React −`react native`; SQL −`sql server`; Git −`version control`; Kubernetes keeps eks/aks/gke.
  6. `RULES` (`case_sensitive`, `not_followed_by`, `not_preceded_by`):
     - Go: `["Go"]`, `[\s\-]+(?:to|live|further|beyond|ahead|back|forward|above|through|out|green|big|home|get|global|deep|over|faster|far|wrong)\b`.
     - R: `["R"]`, `\s*[&+']|\.\s?[A-Z]`, preceded `&\s*$`.
     - REST API: `["REST"]`; Apache Spark `["Spark"]`; Swift `["Swift"]`; Rust `["Rust"]`; Dart `["Dart"]`; Excel `["Excel"]`; Spring Boot `["Spring"]`; Apache Airflow `["Airflow"]`; Superset `["Superset"]`; AWS Glue `["Glue"]`; AWS Lambda `["Lambda"]`; Azure Synapse `["Synapse"]`; AWS Athena `["Athena"]`; Apache Hive `["Hive"]`; Prefect `["Prefect"]`; Luigi `["Luigi"]`; Presto `["Presto"]`; Stitch `["Stitch"]`; Puppet `["Puppet"]`; Windows `["Windows"]`; Karma `["Karma"]`; Node.js `["Node"]`; Claude `["Claude"]`; Gemini `["Gemini"]`; TypeScript `["TS"]`; SAS `["SAS"]`; SOAP `["SOAP"]`; WAF `["WAF"]`; AWS ECS `["ECS"]`; JMS `["JMS"]`; AWS KMS `["KMS"]`; EDR `["EDR"]`; SSO `["SSO"]`; React `["React"]`; Tableau `["Tableau"]`; Oracle Database `["Oracle"]`; Microsoft Sentinel `["Sentinel"]` (if kept as alias); RAG `["RAG"]`; PRD `["PRD"]`.
  7. `NEW` skills for the new roles:
     - Design: Figma, Sketch, Adobe XD, Adobe Photoshop (photoshop), Adobe Illustrator (illustrator), InVision, Framer, Zeplin, Balsamiq, Miro, Prototyping (prototypes), Wireframing (wireframes, wireframe), User Research (ux research), Usability Testing (usability tests), Design Systems (design system), Interaction Design, Visual Design, UX Writing, Information Architecture, Accessibility (wcag, a11y).
     - Product Management: Product Roadmap (roadmapping, product roadmaps), Product Strategy, Product Discovery, PRD (product requirements document), User Stories (user story), OKRs (okr), Stakeholder Management, Market Research, Product Analytics, Amplitude, Mixpanel, Google Analytics (ga4), Hotjar, Productboard, Pendo, Go-to-Market (gtm strategy).
     - Testing: Cypress, Playwright, Appium, TestNG, JUnit, pytest, Postman, JMeter, LoadRunner, Cucumber, BDD (behavior-driven development, behaviour-driven development), TDD (test-driven development), Test Automation (automated testing, automation testing), Manual Testing, Regression Testing, API Testing, Performance Testing (load testing), TestRail, Katalon, Robot Framework, WebdriverIO, Mocha.
     - Customer Support: Zendesk, Freshdesk, Intercom, Jira Service Management, ITIL, Active Directory, Help Desk (helpdesk, service desk), Troubleshooting, Ticketing Systems (ticketing system), Customer Success, HubSpot, Gainsight, Customer Onboarding, Remote Desktop (rdp), DNS, TCP/IP, SLA Management (with `case_sensitive` `["SLA"]` for the alias SLA).
     - Also: Data Lake, Data Warehouse, AWS, Azure, Google Cloud (aliases gcp, google cloud platform) if not already present.
  - Finally, drop the `_discovered`, `_first_seen` and `_occurrence_count` keys from every entry, and set `type` via the existing `CATEGORY_TYPE` rules in `clean_taxonomy.py` (import them).
  - Print a summary (removed, merged, renamed, added, rules).
- [ ] **Step 4: Run the script, then the tests.** Run `cd etl && ../venv/Scripts/python tools/curate_taxonomy_2026_10.py && ../venv/Scripts/python -m pytest tests/test_taxonomy.py -v`. Fix any remaining clash or false match by adding the smallest rule/removal to the script (never by editing the JSON by hand). Re-run until green, then run the full ETL and backend suites.
- [ ] **Step 5: Frontend colour slots.** In `frontend/src/utils/helpers.js`, `CATEGORY_SLOTS`: map `'Design'`, `'Product Management'`, `'Customer Support'`, `'Business Applications'` onto existing slots, so they don't render neutral grey. Then `cd frontend && npm run build` → succeeds.
- [ ] **Step 6: Commit** — `git add etl/tools/curate_taxonomy_2026_10.py etl/config/skills_taxonomy.json etl/tests/test_taxonomy.py frontend/src/utils/helpers.js` → `git commit -m "Curate skills taxonomy and block false matches"` → push.

---

### Task 4: Twenty roles

**Files:** Modify `etl/connectors/utils.py` (`_ROLE_PATTERNS`), `etl/config/extraction_config.json`, `etl/extractor.py` (role list source); create `database/migrations/009_new_roles.sql`, `etl/tests/test_roles.py`.

**Interfaces — Produces:** `RoleMatcher(roles).match(title)` for 20 roles; `extraction_config.json` keys `roles` (20) and `adzuna_roles` (15).

- [ ] **Step 1: Failing tests** (`etl/tests/test_roles.py`)
```python
import json
from pathlib import Path

import pytest

from connectors.utils import RoleMatcher

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "config" / "extraction_config.json").read_text())
M = RoleMatcher(CONFIG["roles"])


@pytest.mark.parametrize("title,role", [
    ("Senior Software Engineer", "Software Engineer"),
    (".NET Software Engineer", "Software Engineer"),
    ("Senior Java Developer", "Software Engineer"),
    ("Software Engineer - Backend", "Backend Developer"),
    ("Senior Software Engineer, Machine Learning", "Machine Learning Engineer"),
    ("Mobile App Developer (m/w/d)", "Mobile Developer"),
    ("Architecte Cloud H/F", "Cloud Architect"),
    ("Senior Cloud Systems Architect", "Cloud Architect"),
    ("Data Architect", "Data Engineer"),
    ("Data Analist", "Data Analyst"),
    ("QA Automation Engineer", "QA Engineer"),
    ("SDET II", "QA Engineer"),
    ("Senior Product Designer", "UI/UX Designer"),
    ("UI/UX Designer", "UI/UX Designer"),
    ("UI Developer", "Frontend Developer"),
    ("Senior Product Manager", "Product Manager"),
    ("Product Owner", "Product Manager"),
    ("Technical Support Engineer", "Technical Support Engineer"),
    ("Customer Success Engineer", "Technical Support Engineer"),
    ("IT Help Desk Specialist", "Technical Support Engineer"),
])
def test_role_precedence(title, role):
    assert M.match(title) == role


@pytest.mark.parametrize("title", ["Business Development Manager", "Sales Engineer",
                                   "Project Manager", "Accountant", "Security Guard"])
def test_non_tech_titles_do_not_match(title):
    assert M.match(title) is None


def test_config_role_lists():
    assert len(CONFIG["roles"]) == 20
    assert len(CONFIG["adzuna_roles"]) == 15
    assert set(CONFIG["adzuna_roles"]) < set(CONFIG["roles"])
```
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
  - `extraction_config.json`: add `adzuna_roles` (the current 15) and append the 5 new roles to `roles`.
  - In `extractor.py`, where it reads `config["roles"]`, use `config.get("adzuna_roles", config["roles"])`.
  - `_ROLE_PATTERNS` (order matters, most specific first):
    - Insert `("UI/UX Designer", [r"\bux\b", r"ui ?/ ?ux", r"ux ?/ ?ui", r"\bui designer", r"user experience", r"product designer", r"interaction designer", r"visual designer", r"web designer"])` before Frontend.
    - Insert `("QA Engineer", [r"\bqa\b", r"quality assurance", r"\bsqa\b", r"\bsdet\b", r"test automation", r"automation (test|qa)", r"software test", r"test engineer", r"\btester\b"])` before Backend.
    - Insert `("Product Manager", [r"product manager", r"product owner", r"product management", r"\btechnical pm\b"])`.
    - Insert `("Technical Support Engineer", [r"(technical|tech|it|application|product|customer) support", r"support engineer", r"help ?desk", r"service desk", r"customer success engineer", r"technical account manager", r"support specialist", r"desktop support"])`.
    - Extend the existing roles: Data Engineer + `r"data architect"`; Data Analyst + `r"data analist"`; Mobile + `r"mobile (app|application)"`; Cloud Architect + `r"cloud .*architect"`, `r"architecte cloud"`, `r"systems architect"`.
    - Append **last**: `("Software Engineer", [r"software (engineer|developer|development engineer)", r"\bswe\b", r"\bsde\b", r"application (developer|engineer)", r"\b(java|python|golang|c\+\+|c#|\.net|ruby|php|rust|scala|kotlin|typescript|javascript) (developer|engineer)\b", r"\bprogrammer\b"])`.
  - `009_new_roles.sql`: `BEGIN; INSERT INTO staging.dim_job_roles (role_name, role_category) VALUES ('Software Engineer','Engineering'),('QA Engineer','Engineering'),('UI/UX Designer','Design'),('Product Manager','Product'),('Technical Support Engineer','Support') ON CONFLICT (role_name) DO NOTHING; COMMIT;` Check `database/schema.sql:29` for the unique column and `role_category` values before writing; adapt the `ON CONFLICT` target to the real constraint.
- [ ] **Step 4: Run** → pass. Apply 009: `cd etl && ../venv/Scripts/python -m ops.migrate up` → `applied 009_new_roles.sql`.
- [ ] **Step 5: Commit** — `git commit -m "Expand tracked roles to twenty"` → push.

---

### Task 5: Title-validated roles in the transformer

**Files:** Create `database/migrations/010_raw_skip_reason.sql`; modify `etl/transformer.py` (`get_unprocessed_jobs`, the per-job loop); extend `etl/tests/test_transformer_guard.py` and `etl/tests/fixtures/pipeline_schema.sql` (add `skip_reason`).

**Interfaces — Produces:** `transformer.KEYWORD_SOURCES = {"adzuna", "jooble"}`; `transformer.validated_role(source, search_role, title, matcher) -> str | None`.

- [ ] **Step 1: Failing tests** (append to `test_transformer_guard.py`)
```python
def test_keyword_source_role_comes_from_title(transformer):
    from connectors.utils import RoleMatcher
    import json
    from pathlib import Path
    roles = json.loads((Path(__file__).resolve().parents[1] / "config" / "extraction_config.json").read_text())["roles"]
    m = RoleMatcher(roles)
    assert transformer.validated_role("adzuna", "Data Engineer", "Senior Data Scientist", m) == "Data Scientist"
    assert transformer.validated_role("adzuna", "Data Engineer", "Warehouse Operative", m) is None
    assert transformer.validated_role("remoteok", "Data Engineer", "Warehouse Operative", m) == "Data Engineer"


def test_skipped_rows_are_not_picked_up(pipeline_db, transformer):
    run_sql(pipeline_db, """INSERT INTO raw.jobs (job_platform_id, raw_data, skip_reason)
                            VALUES ('skip', '{"title": "x"}', 'role_mismatch'), ('ok', '{"title": "y"}', NULL)""")
    conn = psycopg2.connect(pipeline_db)
    try:
        with conn.cursor() as cur:
            jobs = transformer.get_unprocessed_jobs(cur, batch_size=10)
    finally:
        conn.close()
    assert [j["job_platform_id"] for j in jobs] == ["ok"]
```
  Also add `skip_reason TEXT` to `raw.jobs` in `tests/fixtures/pipeline_schema.sql`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
  - `010_raw_skip_reason.sql`: `BEGIN; ALTER TABLE raw.jobs ADD COLUMN IF NOT EXISTS skip_reason TEXT; COMMIT;`
  - In `transformer.py`: import `RoleMatcher` from `connectors.utils` (add `sys.path` for `etl/` if the file lacks it), and load roles from `config/extraction_config.json` once in `transform_and_load`.
  - Add:
```python
KEYWORD_SOURCES = {"adzuna", "jooble"}


def validated_role(source, search_role, title, matcher):
    """Keyword search is fuzzy ("Data Engineer" returns warehouse jobs), so
    for keyword-searched sources the TITLE decides the role. Feed sources
    were already classified by title in their connector."""
    if source not in KEYWORD_SOURCES:
        return search_role
    return matcher.match(title)
```
  - In the loop, after `parse_raw_job(...)`: compute `role = validated_role(source, parsed_job["search_role"], parsed_job["title"], matcher)`. If `role is None`, run `UPDATE raw.jobs SET skip_reason = 'role_mismatch' WHERE id = %s`, `RELEASE SAVEPOINT job_sp`, count it as a skip (not a failure), and `continue`. Otherwise set `parsed_job["search_role"] = role`.
  - `get_unprocessed_jobs` adds `AND r.skip_reason IS NULL`.
  - The zero-progress guard must count skips as progress.
- [ ] **Step 4: Run all ETL tests** → pass. Apply 010: `../venv/Scripts/python -m ops.migrate up`.
- [ ] **Step 5: Commit** — `git commit -m "Validate keyword-source roles against titles"` → push.

---

### Task 6: Backfill existing jobs (`ops.reextract`)

**Files:** Create `etl/ops/reextract.py`, `etl/tests/test_reextract.py`; extend `tests/fixtures/pipeline_schema.sql` with `staging.dim_skills` (the `database/schema.sql` columns) and `stg_jobs.description`/`source` if missing.

**Interfaces — Consumes:** `RoleMatcher`, `transformer.validated_role`/`KEYWORD_SOURCES` (import from transformer is avoided — reimplement the one-liner via `KEYWORD_SOURCES` in `ops.reextract` to keep ops free of transformer's import side effects), `FastPathExtractor`. **Produces:** `plan(conn, matcher) -> dict` (counts: keep, retag, drop), `apply(conn, matcher, extractor, batch=2000) -> dict`, `sync_dim_skills(conn, taxonomy) -> dict`, CLI `python -m ops.reextract --dry-run | --apply [--max-drop-pct 25]`.

- [ ] **Step 1: Failing tests** (`etl/tests/test_reextract.py`) on `pipeline_db` with a small inline taxonomy and matcher:
  - `test_plan_counts_retag_and_drop`: three Adzuna jobs (a matching title, a retag title, a non-tech title) plus one RemoteOK non-tech title (kept as is) → `{"keep": 2, "retag": 1, "drop": 1}`.
  - `test_apply_retags_drops_and_reextracts`: after `apply`, the dropped job is gone from `stg_jobs` and its raw row has `skip_reason='role_mismatch'`. The retagged job has the new role. Skills are recomputed: a description "we go further with Python" yields only Python.
  - `test_reextract_is_idempotent`: applying twice gives the same `stg_job_skills` row count.
  - `test_sync_dim_skills_adds_new_and_removes_unused`: new taxonomy skills get inserted. A dim skill absent from the taxonomy and unreferenced is deleted. Categories are updated.
  - `test_cli_refuses_large_drop`: `main(["--apply", "--max-drop-pct", "10"])` with 50% droppable → exits 1, and nothing changes.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `etl/ops/reextract.py`.**
  - Roles: `SELECT job_id, raw_job_id, source, search_role, title FROM staging.stg_jobs`. For keyword sources, `matcher.match(title)` → keep, retag, or drop.
  - Retags go in one `UPDATE … FROM (VALUES …)` statement.
  - Drops: `UPDATE raw.jobs SET skip_reason='role_mismatch' WHERE id = ANY(%s)`, then `DELETE FROM staging.stg_jobs WHERE job_id = ANY(%s)` (skills cascade).
  - Skills: `sync_dim_skills` first, so the new skill ids exist. Then, per batch of `batch` jobs, read `(job_id, title, description)`, extract with `FastPathExtractor(taxonomy_data=…)` on `f"{title} {description}"`, delete the batch's `stg_job_skills` and insert the new rows with `execute_values`, then commit per batch.
  - Finally, delete `dim_skills` rows that the taxonomy no longer has and that nothing references.
  - `--dry-run` prints `plan()` plus the number of skill rows before and after for a 2,000-job sample; `--apply` refuses when `drop / total * 100 > --max-drop-pct`.
  - Loads `etl/.env` only under `__main__` (the Phase 0 convention).
- [ ] **Step 4: Run all tests** → pass.
- [ ] **Step 5: Production dry run** — run `cd etl && ../venv/Scripts/python -m ops.reextract --dry-run` and record keep/retag/drop. **If drop > 25%, stop and ask the owner.** Otherwise run `--apply` and record the counts in the task report. The marts stay as they are until the next pipeline run passes the marts guard (Phase 0), which rebuilds them from the cleaned staging data.
- [ ] **Step 6: Commit** — `git commit -m "Backfill roles and skills on staging"` → push.

---

### Task 7: Docs + memory

- [ ] Update `CLAUDE.md`:
  - Phase 1a status.
  - `etl/skill_patterns.py`, the shared matcher; taxonomy rules fields; "never hand-edit taxonomy JSON for curation — add to a curation script + lint test".
  - `raw.jobs.skip_reason`; keyword-source role validation; `adzuna_roles`; `ops.reextract` usage.
- [ ] Update the `sellable-product-planning` memory: Phase 1a done, Phase 1b (company job-board connectors) next.
- [ ] Commit — `git commit -m "Document Phase 1a roles and skills"` → push.

## Self-review notes
- Spec §6.4 coverage: 5 new roles (T4), RoleMatcher precedence with SWE last (T4), taxonomy additions (T3), PIPELINE_REVIEW #1 (T5 + T6) and #3 (T1–T3). Discovery auto-promotion (#5) is untouched: production runs `--fast-only`, and removing the `_discovered` entries (T3) removes its output.
- Type consistency: `build_patterns`/`SkillPattern.count` are used identically in T2 and T3; `KEYWORD_SOURCES` is defined in the transformer (T5) and mirrored in ops (T6) on purpose (import isolation), and both are covered by tests.
