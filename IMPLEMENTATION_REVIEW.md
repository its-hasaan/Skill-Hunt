# Skill Hunt - Implementation Review

*Generated: January 27, 2026*

---

## 1. Project Overview

Skill Hunt is a job market analysis dashboard that extracts job postings from the Adzuna API, performs skill extraction, and presents analytics via a React frontend.

**Tech Stack:**
- **ETL**: Python (extractor.py, transformer.py)
- **Skill Extraction**: Hybrid (Regex + GLiNER NER model)
- **Database**: PostgreSQL (Supabase)
- **Transformation**: dbt (Data Build Tool)
- **Backend**: FastAPI
- **Frontend**: React + Vite + Tailwind CSS
- **Deployment**: Render (backend), Vercel (frontend)

---

## 2. Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                       │
└─────────────────────────────────────────────────────────────────────────────┘

1. EXTRACTION (extractor.py)
   Adzuna API → raw.jobs (JSONB storage)
   - 15 roles × 17 countries × 2 pages = max 2,550 API calls per run
   - Stores raw JSON response as-is
   - Deduplicates via (job_platform_id, country_code) constraint

2. TRANSFORMATION (transformer.py)
   raw.jobs → staging.stg_jobs + staging.stg_job_skills
   - Parses JSONB into flat columns
   - Extracts skills via HybridSkillExtractor
   - Links skills to staging.dim_skills

3. SKILL EXTRACTION (skill_extractor/)
   ┌────────────────┐
   │  Fast Path     │ ← Regex matching against skills_taxonomy.json
   │  (Always runs) │    ~200+ skills with aliases
   └───────┬────────┘
           │
           ▼
   ┌────────────────┐
   │  Slow Path     │ ← GLiNER NER model (local, free)
   │  (Conditional) │    Triggered when:
   └───────┬────────┘    - < 5 skills found by fast path
           │             - Discovery sampling (10% of jobs)
           ▼             - --discovery-mode flag
   ┌────────────────┐
   │ Discovery Mgr  │ ← Tracks new skills, auto-promotes
   └────────────────┘

4. DBT TRANSFORMATION (dbt_project/)
   staging.* → marts.*  (via dbt models)
   - int_job_skills_enriched (intermediate view)
   - mart_skill_demand
   - mart_skill_cooccurrence
   - mart_company_leaderboard
   - mart_role_similarity
   - mart_salary_by_skill
   - mart_skills_by_country

5. SERVING (backend/)
   FastAPI reads from staging_marts.* schema
   Endpoints: /skills, /salary, /companies, /career, /stats

6. PRESENTATION (frontend/)
   React SPA with pages:
   - Dashboard (summary metrics)
   - Skills (demand, co-occurrence, network graph)
   - Salary (skill premiums)
   - Companies (hiring leaderboard)
   - Career (role similarity)
   - Global (geographic view)
```

---

## 3. Functionalities

| Module | Description | Status |
|--------|-------------|--------|
| **Job Extraction** | Pulls jobs from Adzuna API for 15 roles across 17 countries | Implemented |
| **Skill Extraction (Fast)** | Regex-based matching against taxonomy (~200 skills) | Implemented |
| **Skill Extraction (Slow)** | GLiNER NER model for discovering new skills | Implemented |
| **Skill Discovery Manager** | Tracks, counts, and auto-promotes new skills | Implemented |
| **dbt Transformations** | 6 mart tables for analytics | Implemented |
| **Skill Demand API** | Top skills by role/country | Implemented |
| **Skill Co-occurrence API** | Skills that appear together | Implemented |
| **Skill Network Graph** | D3.js compatible nodes/links | Implemented |
| **Company Leaderboard API** | Top hiring companies | Implemented |
| **Salary Analysis API** | Skill salary premiums | Implemented |
| **Career Transitions API** | Role similarity for career pivots | Implemented |
| **Dashboard UI** | Summary stats, charts | Implemented |
| **Skills Page UI** | Demand charts, network graph | Implemented |
| **Companies Page UI** | Leaderboard table | Implemented |
| **Salary Page UI** | Premium analysis | Implemented |
| **Career Page UI** | Role similarity heatmap | Implemented |
| **Historical Archiving** | Snapshots of skill_demand | Implemented (archive schema exists) |

---

## 4. Automated Scheduled ETL

### Implementation Status: **Fully Implemented**

Evidence: [.github/workflows/etl_pipeline.yml](.github/workflows/etl_pipeline.yml)

The GitHub Actions workflow includes:
- **Extract job**: Runs `extractor.py`
- **Transform job**: Runs `transformer.py` (with hybrid skill extraction)
- **dbt job**: Runs `dbt run --full-refresh` and `dbt test`
- **Archive job**: Calls `archive_skill_demand()` function

All jobs have proper dependency chaining (`needs:` clauses).

### Usage Status: **Ambiguous**

| Factor | Observation |
|--------|-------------|
| **Schedule defined** | Yes - `cron: '0 3 * * 0,3'` (Sun/Wed 3AM UTC) |
| **Workflow exists** | Yes - complete 251-line workflow file |
| **Secrets referenced** | Yes - `ADZUNA_APP_ID`, `SUPABASE_URL`, etc. |
| **Manual trigger** | Yes - `workflow_dispatch` enabled |
| **Evidence of runs** | **Unknown** - no workflow run history in repo |
| **dbt target** | GitHub Actions uses `prod` target, but local profiles.yml has `target: dev` |

**Reason for "Ambiguous":**  
While the workflow is fully defined, there is no observable evidence (e.g., run history, logged artifacts, or database timestamps) confirming whether the scheduled pipeline is actively running in production. The secrets configuration would need to be verified in the GitHub repository settings.

---

## 5. Use Cases

**Target Audience:** Job seekers, recruiters, data analysts, career coaches

| Use Case | Example Query |
|----------|---------------|
| Skill gap analysis | "What skills do I need to become a Data Engineer?" |
| Salary negotiation | "Do Python skills command a salary premium?" |
| Career transitions | "As a Backend Developer, what other roles share my skillset?" |
| Hiring trends | "Which companies are hiring the most Machine Learning Engineers?" |
| Geographic comparison | "Is SQL more in demand in the UK or US?" |
| Emerging skills | "What new skills are appearing in job postings?" (via GLiNER discovery) |

---

## 6. Inconsistencies and Issues

### Issue 1: Schema Mismatch Between dbt and Backend

**Severity:** High (potential runtime error)

**Evidence:**

dbt models output to `marts` schema (with prefix):
```sql
-- dbt_project/models/marts/mart_skill_demand.sql line 4
schema='marts'
```

Backend queries reference `staging_marts` schema:
```sql
-- backend/app/routers/skills.py line 42
FROM staging_marts.mart_skill_demand
```

**Impact:** If dbt runs with default settings, tables are created as `staging_marts.mart_*` (prefix `staging` + schema `marts`). This works. However, dbt documentation indicates the schema depends on target configuration and the `generate_schema_name` macro behavior.

**Recommendation:** Verify actual schema name in database or explicitly define `generate_schema_name` macro.

---

### Issue 2: Hardcoded Placeholder URL in vercel.json

**Severity:** Medium (blocks frontend API calls in production)

**Evidence:**
```json
// vercel.json line 15
"dest": "https://your-render-backend.onrender.com/api/$1"
```

**Impact:** Frontend deployed to Vercel will fail all API requests until this is updated to the actual Render backend URL.

---

### Issue 3: Database Credentials Exposed in profiles.yml

**Severity:** Critical (security vulnerability)

**Evidence:**
```yaml
# dbt_project/profiles.yml lines 9-10, 21-22
user: "postgres.jyxwmracnxszcqrnfbun"
password: "KOvfxupaV76rj32e"
```

**Impact:** Database credentials are hardcoded in a version-controlled file. Anyone with repo access can access the database.

**Recommendation:** Remove credentials, use environment variables, add `profiles.yml` to `.gitignore`.

---

### Issue 4: Documentation Inaccuracy - "Gemini" vs "GLiNER"

**Severity:** Low (documentation misleading)

**Evidence:**

Documentation claims Gemini LLM:
```markdown
// PROJECT_OVERVIEW.md line 15
**Slow Path**: LLM-based extraction (Google Gemini Flash) for skill discovery.

// etl/README.md line 24-25
Uses **Google Gemini Flash** for intelligent extraction
```

Actual implementation uses GLiNER (local NER model):
```python
# etl/skill_extractor/slow_path.py line 1-6
"""
Slow Path Skill Extractor (GLiNER NER-Based)
=============================================
Uses GLiNER (Generalist and Lightweight model for NER) for skill extraction.
"""

# etl/skill_extractor/hybrid.py line 63
gemini_api_key: Optional[str] = None,  # Deprecated, ignored
```

**Impact:** Documentation suggests API costs and external dependencies that don't exist. The actual implementation is local and free.

---

### Issue 5: GitHub Actions References GEMINI_API_KEY But It's Unused

**Severity:** Low (unnecessary secret)

**Evidence:**
```yaml
# .github/workflows/etl_pipeline.yml line 42
GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

But the code ignores this:
```python
# etl/skill_extractor/hybrid.py line 72
gemini_api_key: DEPRECATED - ignored
```

**Impact:** Misleading configuration; maintainers may think Gemini is required.

---

### Issue 6: dbt Default Target Mismatch

**Severity:** Low (local development only)

**Evidence:**
```yaml
# dbt_project/profiles.yml line 31
target: dev
```

But `dev` target uses `schema: staging` while `prod` uses `schema: marts`. GitHub Actions workflow correctly specifies `target: prod`, but local development might produce different schema structures.

---

### Issue 7: Missing Russia in Country Extraction Despite Being in Config

**Severity:** Low (data completeness)

**Evidence:**
```json
// etl/config/extraction_config.json
"ru": "Russia" is NOT in the countries object
```

But `database/schema.sql` line 79 includes:
```sql
('ru', 'Russia'),
```

**Impact:** Russia is in the database seed but not in the extraction config, so no jobs will be extracted for Russia.

---

## Summary Table

| Issue | File(s) | Severity | Type |
|-------|---------|----------|------|
| Schema mismatch | routers/*.py, dbt models | High | Configuration |
| Placeholder URL | vercel.json | Medium | Deployment |
| Exposed credentials | profiles.yml | Critical | Security |
| Gemini vs GLiNER docs | PROJECT_OVERVIEW.md, README.md | Low | Documentation |
| Unused GEMINI_API_KEY | etl_pipeline.yml | Low | Configuration |
| dbt target mismatch | profiles.yml | Low | Configuration |
| Missing Russia | extraction_config.json | Low | Data |

---

*Document purpose: Internal review for brainstorming next steps.*
