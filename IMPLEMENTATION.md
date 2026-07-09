# 🔧 Job Script — Implementation Guide

> **Technical Documentation**  
> A deep dive into the architecture and implementation details behind Job Script, kept in sync with the actual codebase.

---

## 📋 Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Database Design](#2-database-design)
3. [ETL Pipeline Implementation](#3-etl-pipeline-implementation)
4. [Backend Implementation](#4-backend-implementation)
5. [Frontend Implementation](#5-frontend-implementation)
6. [Data Transformation Layer (dbt)](#6-data-transformation-layer-dbt)
7. [Deployment & DevOps](#7-deployment--devops)
8. [Performance & Current Limitations](#8-performance--current-limitations)
9. [Security & Best Practices](#9-security--best-practices)
10. [Testing Status](#10-testing-status)

---

## 1. System Architecture

### 1.1 High-Level Architecture

Job Script follows a **Modern Data Stack (MDS)** architecture:
- **Separation of Concerns**: distinct layers for extraction, storage, transformation, and presentation
- **ELT over ETL**: load raw data first, transform in-database with dbt
- **Cloud-Native**: managed services (Supabase, Render, Vercel)
- **API-First**: FastAPI service layer with RESTful endpoints
- **Stateless Frontend**: React SPA consuming the API

### 1.2 Technology Decisions

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Database** | PostgreSQL (Supabase) | ACID, JSONB support, analytics, managed hosting + storage |
| **Backend** | FastAPI + asyncpg | Async, automatic OpenAPI docs, Pydantic validation |
| **Frontend** | React + Vite | Component reuse, fast HMR, modern tooling |
| **Transformation** | dbt (dbt-postgres) | SQL-based, version-controlled, lineage & docs |
| **Skill Discovery** | GLiNER NER (local) | Free, no API cost, discovers skills outside the taxonomy |
| **Orchestration** | GitHub Actions | Free, integrated with version control, declarative YAML |
| **Charting** | Recharts + D3.js | Recharts for standard charts, D3 for network graph & heatmap |
| **Styling** | Tailwind CSS | Utility-first, class-based dark mode |

### 1.3 Data Flow

```
Adzuna API ─► extractor.py ────────┐
                                   ├─► raw.jobs (JSONB + source tag)
Multi-source bots ─► ingest_sources.py
(RemoteOK, WWR, Arbeitnow,         │
 Jobicy, Himalayas, Jooble 🇵🇰🇮🇳,   │
 The Muse, USAJobs)                │
                        transformer.py (fast path + GLiNER;
                        dispatches per source on the normalized envelope)
                                   │
                    staging.stg_jobs / staging.stg_job_skills
                                   │
                              dbt (int + marts)
                                   │
                              marts.* (tables)
                                   │
                                FastAPI  ──►  React SPA ◄── Supabase Auth
                                   │           (email/password + Google OAuth)
                    (resume endpoints read staging + taxonomy;
                     /user endpoints read public.* with verified JWT)
```

Two companion guides cover the newer subsystems in depth:
[SCRAPING_BOTS.md](SCRAPING_BOTS.md) (multi-source ingestion) and
[AUTH_SETUP.md](AUTH_SETUP.md) (auth manual setup).

---

## 2. Database Design

### 2.1 Schema Organization

The database uses **four schemas** (plus `public` for resume metadata):

1. **`raw`** — immutable landing zone (unprocessed API responses as JSONB)
2. **`staging`** — normalized/flattened data + dimension tables (roles, countries, skills)
3. **`marts`** — analytical aggregations (pre-computed by dbt)
4. **`archive`** — historical demand snapshots
5. **`public`** — Resume Analyzer tables: `resume_uploads` (parent), `resume_skills`, `resume_gap_analysis`, `resume_role_matches`

The canonical DDL lives in [`database/schema.sql`](database/schema.sql); the resume table in [`database/Resume_upload.sql`](database/Resume_upload.sql).

### 2.2 Key Tables (as defined in `database/schema.sql`)

#### `staging.dim_job_roles`
Seeded with the **15 target roles** (`role_id`, `role_name` unique, `role_category`, `is_active`, `created_at`).

#### `staging.dim_countries`
Seeded with **20 geographies** (`country_code` PK, `country_name`, `is_active`) — the original 18 plus `pk` (Pakistan) and the `remote` pseudo-country (worldwide-remote roles), added by migration 001 for the multi-source bots.

#### `staging.dim_skills`
```sql
CREATE TABLE staging.dim_skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name TEXT UNIQUE NOT NULL,   -- canonical name, e.g. "Python"
    skill_category TEXT,               -- e.g. 'Programming Language', 'Cloud'
    skill_subcategory TEXT,
    aliases TEXT[],                    -- e.g. {"python3","py"}
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `raw.jobs`
```sql
CREATE TABLE raw.jobs (
    id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,        -- provider job ID ("<source>:<id>" for non-Adzuna)
    search_role TEXT NOT NULL,
    country_code TEXT NOT NULL,
    raw_data JSONB NOT NULL,              -- API response, or connector's normalized envelope
    source TEXT NOT NULL DEFAULT 'adzuna',-- 'adzuna' | 'remoteok' | 'jooble' | ...
    extracted_at TIMESTAMP DEFAULT NOW(),
    extraction_batch_id UUID DEFAULT uuid_generate_v4(),
    CONSTRAINT raw_jobs_unique UNIQUE (job_platform_id, country_code)
);
```
**Design notes:** JSONB preserves the full response for reprocessing; the composite unique key allows the same job to appear per-country; the batch ID tracks extraction runs. Multi-source connectors namespace `job_platform_id` as `<source>:<external_id>` so IDs never collide across providers, and store an envelope `{"_source", "_normalized", "_raw"}` in `raw_data` (the transformer reads `_normalized` directly).

#### `staging.stg_jobs`
```sql
CREATE TABLE staging.stg_jobs (
    job_id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    search_role TEXT NOT NULL,
    country_code TEXT NOT NULL,
    title TEXT,
    company_name TEXT,
    description TEXT,
    location_display TEXT,
    location_areas TEXT[],                -- hierarchical location
    category_tag TEXT,                    -- e.g. 'it-jobs'
    category_label TEXT,                  -- e.g. 'IT Jobs'
    salary_min NUMERIC,
    salary_max NUMERIC,
    salary_is_predicted BOOLEAN DEFAULT FALSE,
    salary_currency TEXT DEFAULT 'GBP',   -- derived from country
    contract_type TEXT,                   -- 'full_time','part_time','contract'
    contract_time TEXT,                   -- 'permanent','temporary'
    redirect_url TEXT,
    job_posted_at TIMESTAMP,              -- when posted on Adzuna
    extracted_at TIMESTAMP,               -- when we extracted it
    processed_at TIMESTAMP DEFAULT NOW(), -- when we cleaned it
    raw_job_id INTEGER REFERENCES raw.jobs(id),
    source TEXT NOT NULL DEFAULT 'adzuna', -- provider this job came from
    CONSTRAINT stg_jobs_unique UNIQUE (job_platform_id, country_code)
);
```

#### `staging.stg_job_skills`
```sql
CREATE TABLE staging.stg_job_skills (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES staging.stg_jobs(job_id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES staging.dim_skills(skill_id),
    skill_name TEXT NOT NULL,             -- denormalized for convenience
    mention_count INTEGER DEFAULT 1,      -- occurrences in the description
    extracted_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT stg_job_skills_unique UNIQUE (job_id, skill_id)
);
```
> Note: this table stores a `mention_count`, not extraction-method/confidence metadata. Confidence lives only in the in-memory extractor; it is not persisted here.

#### Marts tables
`schema.sql` pre-creates `marts.skill_demand`, `marts.skill_cooccurrence`, `marts.company_leaderboard`, `marts.role_similarity`, and `marts.salary_by_skill` as empty placeholders. **dbt does not actually materialize into `marts`** — its `generate_schema_name` macro (implicit default) prefixes the custom schema onto the target, so `mart_skill_demand.sql` (which sets `schema='marts'`) lands in **`staging_marts.mart_skill_demand`**, the table every API endpoint queries. The `marts.*` tables from `schema.sql` stay permanently empty; they're a pre-CI vestige, not a bug that affects the app.

#### Archive & functions
- `archive.skill_demand_history` — dated snapshots of demand, meant to power skill-demand-over-time (§4.4 `/skills/trend` also serves this from `staging.stg_jobs` directly, without depending on snapshot cadence).
- `archive_skill_demand()` — plpgsql function that snapshots the mart into the archive (invoked by the CI `archive` job). **Fixed in `database/migrations/003_fix_archive_snapshots.sql`**: the original definition read from `marts.skill_demand` (always empty per above), so every scheduled archive run silently wrote 0 rows and `archive.skill_demand_history` was empty in practice. The fix repoints it at `staging_marts.mart_skill_demand`, guards for the mart not existing yet, is idempotent per day, and the migration takes the first real snapshot immediately.
- `get_currency_by_country(country TEXT)` — maps a country code to its currency.

#### Resume Analyzer tables (`database/Resume_upload.sql`)

- **`public.resume_uploads`** (parent) — one row per analysis: `id` (UUID), `filename`, `file_size`, `analysis_type` (`gap_analysis` | `role_match`), `target_role`, `country`, `extracted_skills_count`, `extracted_skills` (JSONB snapshot), `match_score`, `storage_path`, `storage_url`, `uploaded_at`, and (migration 002) `user_id` — NULL for anonymous uploads, the Supabase Auth user id when the analysis ran signed-in.
- **`public.resume_skills`** — one row per skill extracted from the resume (`resume_id` FK, `skill_name`, `skill_category`, `mention_count`).
- **`public.resume_gap_analysis`** — gap-run detail, one row per market skill for the target role (`resume_id` FK, `target_role`, `country`, `skill_name`, `skill_category`, `has_skill`, `job_count`, `demand_percentage`, `avg_salary`, `market_rank`).
- **`public.resume_role_matches`** — role-match detail, one ranked row per evaluated role (`resume_id` FK, `country`, `role`, `match_score`, `matched_skills_count`, `total_skills_evaluated`, `rank`, `top_matched_skills` JSONB, `top_missing_skills` JSONB).

All three detail tables reference `resume_uploads(id)` with `ON DELETE CASCADE`.

#### Auth & personalization tables (`database/migrations/002_auth_personalization.sql`)

- **`public.user_profiles`** — 1:1 with `auth.users` (`id` UUID PK/FK): `email`, `display_name`, `avatar_url`, `default_role`, `default_country`. Auto-created by an `AFTER INSERT ON auth.users` trigger (`handle_new_user()`, SECURITY DEFINER) for both email and Google signups; the API also creates it lazily as a fallback.
- **`public.saved_searches`** — `user_id` FK, `name`, `role`, `country` (NULL = all), unique per `(user_id, role, country)`.
- **Row-Level Security** is enabled on `user_profiles`, `saved_searches`, and all four resume tables with own-row policies (`auth.uid()`). The FastAPI backend connects as the `postgres` role and bypasses RLS; the policies protect against direct PostgREST access with the public anon key.

### 2.3 Indexing

Indexes defined in `schema.sql`:
```sql
-- raw.jobs
CREATE INDEX idx_raw_jobs_extracted_at ON raw.jobs(extracted_at);
CREATE INDEX idx_raw_jobs_search_role  ON raw.jobs(search_role);
CREATE INDEX idx_raw_jobs_country      ON raw.jobs(country_code);
CREATE INDEX idx_raw_jobs_batch        ON raw.jobs(extraction_batch_id);
-- staging.stg_jobs
CREATE INDEX idx_stg_jobs_search_role  ON staging.stg_jobs(search_role);
CREATE INDEX idx_stg_jobs_country      ON staging.stg_jobs(country_code);
CREATE INDEX idx_stg_jobs_company      ON staging.stg_jobs(company_name);
CREATE INDEX idx_stg_jobs_posted_at    ON staging.stg_jobs(job_posted_at);
-- staging.stg_job_skills
CREATE INDEX idx_stg_job_skills_skill  ON staging.stg_job_skills(skill_id);
CREATE INDEX idx_stg_job_skills_job    ON staging.stg_job_skills(job_id);
-- archive
CREATE INDEX idx_skill_demand_history_date  ON archive.skill_demand_history(snapshot_date);
CREATE INDEX idx_skill_demand_history_skill ON archive.skill_demand_history(skill_name, search_role);
```

---

## 3. ETL Pipeline Implementation

### 3.1 Extraction (`etl/extractor.py`)

The extractor queries the **Adzuna Job Search API** and stores raw responses in `raw.jobs`.

**Configuration-driven** via `etl/config/extraction_config.json`:
```json
{
  "roles": ["Data Engineer", "Analytics Engineer", "... 15 total"],
  "countries": { "gb": "United Kingdom", "us": "United States", "... 17 total": "" },
  "api": {
    "results_per_page": 50,
    "max_pages_per_role_country": 2,
    "rate_limit_delay_seconds": 1
  }
}
```

**Key functions:** `load_config()`, `validate_credentials()`, `get_jobs()` (fetch a page, handling HTTP 429 with a 60s backoff and timeouts), `save_to_database()` (batch insert), `extract_all()`, `main()`.

**Endpoint & auth:**
```python
url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
# params: app_id, app_key, what=role, results_per_page=50, [max_days_old]
```
Credentials come from `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`; the DB connection from `SUPABASE_URL`.

> **Known limitation — description length.** Adzuna's Search API truncates the `description` field to **500 characters** (mid-word, with an ellipsis) and offers no parameter to lift it and no job-detail endpoint (`/jobs/{country}/{id}` returns 404). Full text lives only on the `redirect_url` landing page. So Adzuna descriptions are inherently partial; the multi-source connectors (§3.1b) return full/fuller text, and skill extraction is minimally affected because skills are typically listed early in a posting.

**Batch, idempotent insert** (via `psycopg2.extras.execute_values`):
```sql
INSERT INTO raw.jobs (job_platform_id, search_role, country_code, raw_data, extraction_batch_id)
VALUES %s
ON CONFLICT (job_platform_id, country_code) DO NOTHING
```

**CLI flags:** `--role`, `--country`, `--pages`, `--delay`, `--days`, `--months`, `--test`. Each run is tagged with a UUID `batch_id`. The scheduled CI job invokes `python extractor.py --days 60 --pages 3 --delay 1.5`.

`etl/check_progress.py` prints row counts across `raw.jobs`, `staging.stg_jobs`, and `staging.stg_job_skills`. `etl/truncate_old.sql` truncates staging/marts tables for a clean rebuild.

### 3.1a Full Refresh Orchestrator (`etl/refresh_all.py`)

Runs the whole pipeline end-to-end so the dashboard reflects the LATEST data across ALL sources, then rebuilds the marts — a convenience script for local/manual runs that mirrors the same stages the CI pipeline runs on its bi-weekly schedule:

1. **Snapshot** current marts → `archive.skill_demand_history` (preserves the current insights *before* anything changes — the trend history is never lost to a rebuild).
2. **Extract** fresh Adzuna postings (`--days`/`--pages`).
3. **Ingest** the multi-source connectors.
4. **Transform** new raw jobs → staging + skills.
5. **Fetch currency rates** (`fetch_currency_rates.py`) — live currency→USD rates for salary normalization (§6.7).
6. **dbt** `run --profiles-dir . --target dev --full-refresh` → rebuilds `staging_marts.*`.
7. **Snapshot** again (starts the next trend point from the fresh state).

**Why the order matters:** dbt's intermediate model keeps only jobs posted in the last 60 days, so the marts must be rebuilt *after* fresh data lands or they'd rebuild empty (e.g. when the newest existing postings are already >60 days old); fresh FX rates must land before the dbt rebuild too, since the salary conversion is computed at build time. Flags: `--skip-adzuna`, `--skip-ingest`, `--skip-transform`, `--skip-fx`, `--skip-dbt`, `--days`, `--dry-run`.

> **Is this the same as the scheduled CI run?** Conceptually yes — same stages, same order — but **not literally the same code path**. `.github/workflows/etl_pipeline.yml` runs each stage as its own GitHub Actions job (`extract` → `transform` → `fx_rates` → `dbt` → `archive`) with its own checkout/install/secrets, rather than invoking this script. Keep both in sync by hand if you change the pipeline shape; there is currently no shared entry point between them.

> **Gotcha — Supabase pooler mode.** `SUPABASE_URL` points at the **transaction** pooler (port `6543`), which drops long-lived connections; the multi-minute transform dies with `connection already closed`. Both `refresh_all.py` (via `session_pooler_url()`) and the CI `transform` job rewrite the transform's connection to the **session** pooler (port `5432`, same host) so the long run survives. dbt derives its `DB_*` env from `SUPABASE_URL` automatically. (The transform commits per batch and is idempotent, so a dropped run can simply be re-run — but the session pooler avoids the drop entirely.) This was discovered and fixed in both places after the first production full-refresh (Jul 2026) died mid-transform on the transaction pooler.

### 3.1b Multi-Source Ingestion (`etl/ingest_sources.py` + `etl/connectors/`)

Runs alongside the Adzuna extractor in the same CI job. Each source has a
connector class (subclass of `BaseConnector`) that fetches jobs and yields
`NormalizedJob` records — one shared dataclass whose fields mirror
`staging.stg_jobs`. The orchestrator wraps each record in a
`{"_source", "_normalized", "_raw"}` envelope and batch-inserts into `raw.jobs`
(idempotent, `source`-tagged, per-run batch UUID).

**Connectors** (registry in `connectors/__init__.py`, config in
`config/sources_config.json`): `remoteok`, `weworkremotely` (RSS),
`arbeitnow`, `jobicy`, `himalayas` — keyless; `jooble` (local Pakistan+India,
free key), `themuse` (keyless, optional key), `usajobs` (free key, disabled by
default), plus a robots.txt-respecting `generic_scraper` template (disabled).

**Shared machinery** (`connectors/utils.py` + `base.py`):
- `RoleMatcher` — classifies free-text titles into the 15 tracked roles
  (specific-before-generic regex ordering; title is primary, tags are matched
  individually as fallback). Non-matching jobs are dropped.
- `html_to_text`, `to_iso`/`epoch_to_iso`, `parse_salary_range`,
  `detect_country_code` (maps PK/IN city+country mentions → `pk`/`in`,
  default `remote`).
- `build_session` — requests.Session with 4 retries, exponential backoff on
  429/5xx, `Retry-After` support, honest `SkillHuntBot/1.0` User-Agent, 30s
  timeouts. Per-source `delay_seconds` rate limiting; per-source isolation
  (one failing source never kills the run); missing keys → logged skip.

**CLI:** `--source X`, `--test`, `--dry-run`. Logs to `etl/ingestion.log`.
Compliance stance and full setup/usage: [SCRAPING_BOTS.md](SCRAPING_BOTS.md).

### 3.2 Transformation & Skill Extraction (`etl/transformer.py`)

Transforms `raw.jobs` → `staging.stg_jobs` (+ `staging.stg_job_skills`):
- `get_unprocessed_jobs()` — selects `raw.jobs` rows that don't yet have a `stg_jobs` row (LEFT JOIN, batched), including each row's `source`.
- `parse_raw_job()` — dispatches by source: connector-ingested rows carry a `_normalized` envelope and pass straight through (`parse_normalized_job()`); Adzuna rows are flattened as before (title, company, description, location display + areas, category tag/label, salary min/max/predicted, contract type/time, redirect URL, `job_posted_at`) with country → currency mapping (now incl. `pk`→PKR, `remote`→USD). Both paths carry `source` into `stg_jobs`.
- Upserts into `stg_jobs` (`ON CONFLICT ... DO UPDATE SET processed_at = NOW()`), then runs the hybrid extractor on `title + description`.
- `get_or_create_skill()` — looks up/creates a `dim_skills` row, then upserts into `stg_job_skills` (`ON CONFLICT (job_id, skill_id)`).

**CLI flags:** `--batch-size`, `--reprocess`, `--discovery-mode` (force GLiNER for all jobs), `--fast-only` (disable GLiNER). Env overrides: `ENABLE_GLINER`, `GLINER_MODEL`, `DISCOVERY_SAMPLE_RATE`. The scheduled CI job runs `--fast-only`.

### 3.3 Hybrid Skill Extractor (`etl/skill_extractor/`)

The `skill_extractor` package implements a two-path design (exported from `__init__.py`): `FastPathExtractor`, `SlowPathExtractor` + `SlowPathConfig`, `HybridSkillExtractor` + `HybridConfig`, and `SkillDiscoveryManager`.

#### Fast Path (`fast_path.py`)
Pre-compiles word-boundary regex patterns for each skill name + aliases from the taxonomy, with special-casing for tokens like `C++`, `C#`, `.NET`, `Node.js`, `Vue.js`. Matches case-insensitively and returns a `mention_count`. Zero cost, near-instant.

**Taxonomy structure** (`etl/config/skills_taxonomy.json`, ~430 skills across ~26 categories):
```json
{
  "skills": [
    {
      "name": "Python",
      "category": "Programming Language",
      "subcategory": "General Purpose",
      "aliases": ["python3", "py"]
    }
  ]
}
```
Auto-promoted entries also carry `_discovered`, `_first_seen`, and `_occurrence_count`.

#### Slow Path — GLiNER NER (`slow_path.py`)
```python
class SlowPathExtractor:
    def _load_model(self):
        if self._model is None and self.config.enabled:
            from gliner import GLiNER
            self._model = GLiNER.from_pretrained(self.config.model_name)
            # default: urchade/gliner_medium-v2.1
        return self._model
```
Predicts entities against ~25 skill labels (mapped to taxonomy categories via `LABEL_TO_CATEGORY`), filters by confidence (`threshold` 0.4 / `min_confidence` 0.5), and drops generic terms. **It is a local NER model, not an LLM — there are no API calls or costs.** (`gliner` is an optional dependency; install with `pip install gliner`.)

> Historical note: an earlier design used Google Gemini. That path has been removed — the `gemini_api_key` parameter on `HybridSkillExtractor` is deprecated and ignored, and `google-generativeai` remains only as a stale entry in `etl/requirements.txt`.

#### Hybrid Orchestrator (`hybrid.py`)
Always runs the fast path. It additionally invokes GLiNER when the fast path finds fewer than `min_skills_for_fast_only` (5), when `always_discover=True`, or by random sampling (`discovery_sample_rate`, default 0.1). GLiNER hits are validated against the taxonomy: known → `taxonomy`/`gliner_verified`; unknown → `gliner_unverified`.

#### Discovery Manager (`skill_discovery.py`)
Tracks unverified discoveries with occurrence counts and average confidence, and **auto-promotes a skill to the taxonomy when `occurrence_count >= 3` and `avg_confidence >= 0.75`** — writing the new entry to both the taxonomy JSON file and `staging.dim_skills`.

**Auto-promotion workflow:**
1. GLiNER discovers a term not in the taxonomy (e.g. "Astro").
2. It is recorded as an unverified discovery (count = 1).
3. Subsequent sightings increment the count and update average confidence.
4. Once ≥3 occurrences at ≥0.75 confidence, it is promoted into the taxonomy JSON + `dim_skills`, so the fast path picks it up on future runs.

> **Trade-off:** auto-promotion inevitably admits some noise (common words GLiNER over-tags, e.g. "it"/"security") and near-duplicates (variants like "Microsoft Azure" promoted alongside "Azure"). These are cleaned up periodically — see below.

#### Taxonomy cleanup (`etl/tools/`)
Two companion tools keep the discovered taxonomy tidy; they share one set of rule dicts (`REMOVE` / `MERGE` / `RENAME`) so JSON and DB never drift:

- **`clean_taxonomy.py`** — rewrites `skills_taxonomy.json`: drops non-skills (company names, garbled/foreign tokens, generic phrases, noise words like `it`/`security`/`NET`), folds variant clusters into a canonical (`Amazon Web Services`/`AWS Cloud` → **AWS**; `Microsoft Azure`/… → **Azure**; `GCP`/`Google Cloud Platform` → **Google Cloud**; `GenAI`/`Gen AI` → **Generative AI**; `REST APIs`/… → **REST**) with the variants kept as aliases, assigns a `type`, backs up the original, and writes `taxonomy_cleanup_changelog.md`. Idempotent.
- **`apply_taxonomy_cleanup_to_db.py`** — imports those same rules and applies them to the ALREADY-extracted data (`staging.dim_skills` + `staging.stg_job_skills`): deletes removed skills, repoints each variant's job-skill rows to the canonical skill (deduping per job so a job that mentioned both "Azure" and "Microsoft Azure" counts once), and deletes the emptied variant rows. Run it, then rebuild marts (`dbt run --profiles-dir . --target dev --full-refresh`) so the dashboard reflects the merge without a full re-extraction. `--dry-run` previews every change. `raw.jobs` is never touched, so a fresh transform can always regenerate staging from scratch.

The first full cleanup (Jul 2026) took the taxonomy 608 → 487 skills (95 removed, 17 merged in the DB) and deleted ~35k noise/duplicate job-skill rows — e.g. `it` (8,567 rows, matched the pronoun in nearly every posting) and the split Azure/AWS cloud counts.

---

## 4. Backend Implementation

### 4.1 Application Setup (`backend/app/main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()

app = FastAPI(title="Job Script API", version="1.0.0", lifespan=lifespan)
```

The app also registers: `CORSMiddleware`, an `X-Process-Time` HTTP middleware, and a global `Exception` handler (which only exposes error detail when `settings.debug` is true). Swagger is at `/docs`, ReDoc at `/redoc`.

**Root endpoints:** `GET /` (metadata), `GET /health` (runs `SELECT 1`, reports DB status), `GET /api/v1` (endpoint map).

### 4.2 Database Layer (`backend/app/database.py`)

A singleton `Database` creates an `asyncpg` pool:
```python
self.pool = await asyncpg.create_pool(
    self.settings.supabase_url,
    min_size=2, max_size=10,
    ssl="require",
    command_timeout=30,
    statement_cache_size=0,   # disabled for Supabase PgBouncer (transaction mode)
)
```
Helpers: `fetch_all`, `fetch_one`, `execute`. A global `db` instance is injected into routers via the `get_db()` dependency. Queries use positional parameters (`$1, $2, …`) so they are parameterized (not string-interpolated).

### 4.3 Configuration (`backend/app/config.py`)

Pydantic `Settings(BaseSettings)` loaded from environment/`.env`:
- `app_name` = "Job Script API", `app_version` = "1.0.0", `debug` = False
- `supabase_url` (**required**, DB connection string), `supabase_anon_key` (optional)
- `supabase_project_url`, `supabase_service_key` (optional — for resume storage)
- `supabase_jwt_secret` (optional — enables fast local verification of user tokens; without it the backend verifies remotely via `supabase_project_url` + `supabase_anon_key`)
- `cors_origins` (comma-split), `cache_ttl_seconds` = 3600, `api_prefix` = "/api/v1"
- `rate_limit_per_minute` = 100 (declared for future use; **not enforced yet**)

`get_settings()` is wrapped with `@lru_cache()`. Note: `cache_ttl_seconds` is defined but there is **no active response caching** in the current code (`cachetools` is listed in requirements but unused).

### 4.4 Routers

Routers live in `backend/app/routers/` and are mounted under `settings.api_prefix` (`/api/v1`). The `skills`, `companies`, `salary`, `career`, and `stats` routers are exported via `routers/__init__.py`; the `resume` and `user` routers are imported separately in `main.py`.

| Router | Prefix | Endpoints |
|--------|--------|-----------|
| skills | `/skills` | `demand`, `demand/all`, `trend`, `jobs`, `cooccurrence`, `network`, `by-country`, `categories`, `list` |
| salary | `/salary` | `by-skill`, `top-paying-skills`, `premium-skills`, `range` |
| companies | `/companies` | `leaderboard`, `contract-types`, `search` |
| career | `/career` | `role-similarity`, `transitions/{current_role}`, `similarity-matrix`, `skill-gap` |
| stats | `/stats` | `summary`, `filters`, `roles`, `countries` |
| resume | `/resume` | `extract-skills` (POST), `analyze` (POST), `match-roles` (POST), `supported-roles` (GET) |
| user 🔐 | `/user` | `me` (GET/PUT), `saved-searches` (GET/POST/DELETE), `resume-history` (GET/DELETE) — all require a Supabase session token |

**Example — `routers/skills.py`:**
```python
@router.get("/demand", response_model=SkillDemandResponse)
async def get_skill_demand(
    role: str = Query(..., description="Job role to filter by"),
    country: Optional[str] = Query(None, description="Country code, e.g. 'gb'"),
    limit: int = Query(30, ge=1, le=100),
    db: Database = Depends(get_db),
):
    # queries staging_marts.mart_skill_demand; when country is None,
    # aggregates across countries. Returns SkillDemandResponse.
```

**Skill drill-down (`GET /skills/jobs`).** Turns an aggregate skill count into the underlying postings. It joins `staging.stg_jobs` × `staging.stg_job_skills` to page through every job where the skill was detected (for a role, optionally a country), and returns each posting's metadata + full `description`. Alongside the jobs it returns `highlight_skills` — the role's top skills from `mart_skill_demand`, each with its `dim_skills` aliases and an `is_selected` flag — so the frontend can highlight all top skills in each description and colour the clicked one distinctly. No schema or pipeline changes were needed: the job text and job↔skill links already exist in `staging`.

**Demand trend (`GET /skills/trend`).** Deliberately built on `staging.stg_jobs`/`staging.stg_job_skills` directly rather than `archive.skill_demand_history` — the archive only gets one row per skill per calendar day the CI `archive` job runs (bi-weekly, and was silently broken until migration 003; see §2.2), which is too sparse and fragile for a live chart. The endpoint instead buckets postings by `date_trunc('month', job_posted_at)` for up to 5 comma-separated skill names, computing `demand_percentage = jobs_with_skill / total_jobs_that_month` per bucket — a share, not a raw count, because extraction volume varies run-to-run and only the share is comparable across months. The window is anchored to `MAX(job_posted_at)` in the filtered set (not `NOW()`), so the chart stays meaningful even when the pipeline is behind schedule. Two queries: one for the per-month `total_jobs` denominator, one for per-skill-per-month counts (`ANY($skills)` + `GROUP BY`), joined in Python into zero-filled series so every skill has a point for every period even with no mentions that month.

### 4.5 Pydantic Schemas (`backend/app/models/schemas.py`)

Response models reflect the mart columns. For example:
```python
class SkillDemand(BaseModel):
    skill_name: str
    skill_category: Optional[str] = None
    search_role: str
    country_code: Optional[str] = None
    job_count: int
    demand_percentage: Optional[float] = None
    avg_salary_min: Optional[float] = None
    avg_salary_max: Optional[float] = None
    avg_salary_midpoint: Optional[float] = None
    rank_in_role_country: Optional[int] = None
    rank_in_role_global: Optional[int] = None

class SkillDemandResponse(BaseModel):
    role: str
    country: Optional[str] = None
    total_count: int
    data: List[SkillDemand]
```
Other models include `SkillCooccurrence`, `SkillNetworkResponse`, `SalaryBySkill`/`SalaryResponse`, `CompanyLeaderboard`/`CompanyResponse`, `RoleSimilarity`, `CareerTransition`/`CareerPathResponse`, `SkillByCountry`/`GlobalComparisonResponse`, `DashboardStats`, `FilterOptions`, and the resume models below.

### 4.6 Resume Analyzer (`backend/app/routers/resume.py` + `storage.py`)

The resume feature is fully implemented:

- **Text extraction** (`extract_text_from_bytes`): plain text (`.txt/.md/.csv`), PDF (`PyPDF2.PdfReader`), Word (`python-docx`), and images (`.png/.jpg/.jpeg/.webp/.bmp` via optional `pytesseract` OCR). Missing optional libraries raise HTTP 500; unknown types fall back to UTF-8 decode.
- **Skill extraction** (`ResumeSkillExtractor`): loads `etl/config/skills_taxonomy.json` and matches with compiled regex (same approach as the ETL fast path, special-casing `C++`/`C#`/`.NET`). If the taxonomy file is missing it logs and extracts nothing.
- **`POST /resume/analyze`**: extracts resume skills, queries `mart_skill_demand` for the `target_role`, splits into `skills_you_have` / `skills_you_need`, and computes a demand-weighted `match_percentage` (→ `ResumeAnalysisResponse`).
- **`POST /resume/match-roles`**: scores the resume against every role in `mart_skill_demand` (demand-weighted) and returns the top N (→ `List[RoleMatchResult]`).
- **Persistence**: `/analyze` and `/match-roles` register a FastAPI `BackgroundTasks` job (`_persist_analysis`) that runs after the response. When storage is configured it uploads the file to the Supabase Storage `resumes` bucket (`storage.py`, `upload_resume_file`), then in a single DB transaction writes:
  - `public.resume_uploads` — the parent row (filename, analysis_type, target_role, country, match_score, storage path/url, skills snapshot),
  - `public.resume_skills` — one row per extracted resume skill,
  - `public.resume_gap_analysis` — for gap runs, one row per market skill flagged `has_skill` (owned) or a gap, with demand %, salary, and rank,
  - `public.resume_role_matches` — for role-match runs, one ranked row per evaluated role with score, matched/total counts, and top matched/missing skills (JSONB).

  The whole task is best-effort: any storage/DB failure is logged and never propagates to the user's response. (An earlier implementation used a fire-and-forget `asyncio.ensure_future`, which could be garbage-collected mid-run; `BackgroundTasks` is awaited by Starlette and is reliable.)

Relevant schemas: `ExtractedSkill`, `SkillGapAnalysis`, `ResumeAnalysisResponse`, `MatchedSkill`, `RoleMatchResult`. (`ResumeSkill`/`ResumeAnalysis` remain as older "future" models and are not used by the active endpoints.)

`/analyze` and `/match-roles` also take `Depends(get_optional_user)`: anonymous uploads keep working, but when a valid session token is present the persisted `resume_uploads` row gets the caller's `user_id`, which powers the Account page's history.

### 4.6b Authentication (`backend/app/auth.py` + `routers/user.py`)

The frontend authenticates directly with **Supabase Auth** (email/password or
Google OAuth via supabase-js) and sends the resulting access token as
`Authorization: Bearer <token>`. The backend never handles passwords — it only
**verifies** tokens, with two strategies:

1. **Local HS256** (preferred): `jwt.decode(token, SUPABASE_JWT_SECRET, audience="authenticated")` via PyJWT — fast, no network.
2. **Remote fallback**: `GET {SUPABASE_PROJECT_URL}/auth/v1/user` with the anon key — works with any signing algorithm; results cached in-process for 5 minutes.

Two dependencies: `get_current_user` (401 on missing/invalid; 503 when neither
strategy is configured) and `get_optional_user` (returns `None`, never raises).
`routers/user.py` implements profile get/update (lazy profile creation as a
fallback to the DB trigger), saved-search CRUD (capped at 30, upsert on
duplicate role+country), and resume history (list + delete, cascade removes
detail rows). Manual setup steps: [AUTH_SETUP.md](AUTH_SETUP.md).

### 4.7 CORS, Timing & Error Handling

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{round((time.time()-start)*1000, 2)}ms"
    return response
```

---

## 5. Frontend Implementation

### 5.1 Structure

```
frontend/src/
├── main.jsx                 # Bootstrap: ThemeProvider → AuthProvider → QueryClientProvider → App
├── App.jsx                  # BrowserRouter + routes under <Layout> (incl. /login, /account)
├── index.css                # Global styles (Tailwind)
├── api/
│   └── index.js             # Axios client (auto-attaches Supabase token) + grouped API objects incl. userApi
├── lib/
│   └── supabase.js          # supabase-js client (auth only); null-safe when env vars absent
├── components/
│   ├── Layout.jsx           # Sidebar nav, global filters, theme toggle, sign-in/avatar, save-search bookmark
│   ├── charts/
│   │   ├── Charts.jsx       # Recharts components
│   │   ├── Heatmap.jsx      # D3 SimilarityHeatmap
│   │   └── NetworkGraph.jsx # D3 SkillNetworkGraph
│   └── ui/
│       └── index.jsx        # Skeleton, Spinner, StatCard, Card, Tabs, Badge, ...
├── context/
│   ├── ThemeContext.jsx     # Light/dark theme (localStorage + prefers-color-scheme)
│   └── AuthContext.jsx      # Supabase session state + signIn/signUp/signInWithGoogle/signOut
├── hooks/
│   └── useData.js           # React Query hooks
├── pages/
│   ├── Dashboard.jsx
│   ├── SkillsPage.jsx
│   ├── SalaryPage.jsx
│   ├── CompaniesPage.jsx
│   ├── CareerPage.jsx
│   ├── GlobalPage.jsx
│   ├── ResumePage.jsx       # Resume Analyzer (upload + gap analysis / role match)
│   ├── JobsPage.jsx         # Skill drill-down: real postings for a skill, with highlights
│   ├── LoginPage.jsx        # Email/password + "Continue with Google"
│   └── AccountPage.jsx      # Profile & defaults, saved searches, resume history
└── utils/
    └── helpers.js           # Country metadata, formatters, color palettes
```

### 5.2 Tech Stack

React 18.2, Vite 5, React Router 6, TanStack React Query 5, Recharts 2.10, D3 7, Axios 1.6, Tailwind 3.4, Lucide icons, supabase-js 2 (auth). The dev server (`vite.config.js`) proxies `/api` → `http://localhost:8000`.

**Auth flow:** `AuthContext` subscribes to `supabase.auth.onAuthStateChange`; the session persists in localStorage with silent token refresh, and `detectSessionInUrl` completes the Google OAuth redirect. An axios request interceptor attaches the access token to every API call. `Layout` shows a Sign-in link or the user's avatar, plus a bookmark button that saves the current role+country as a saved search. `AccountPage` redirects to `/login` when signed out; signed-in users get their `default_role`/`default_country` applied to the global filters once per visit.

### 5.3 API Client (`src/api/index.js`)

```javascript
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (response) => response.data,       // auto-unwrap
  (error) => { console.error('API Error:', error.response?.data || error.message); throw error }
)
```
Grouped exports: `statsApi`, `skillsApi`, `companiesApi`, `salaryApi`, `careerApi`, `resumeApi`, and `userApi` (profile, saved searches, resume history). A request interceptor awaits `getAccessToken()` from the Supabase session and adds `Authorization: Bearer <token>` when signed in. The resume calls post `multipart/form-data` through the same instance with a 60s timeout, so they carry the token too (linking analyses to the account).

### 5.4 Data Fetching (`src/hooks/useData.js`)

Most endpoints are wrapped in React Query hooks (`useSummaryStats`, `useFilterOptions`, `useSkillDemand`, `useSkillTrend`, `useSkillCooccurrence`, `useCompanyLeaderboard`, `useSalaryBySkill`, `useRoleSimilarity`, `useSkillGap`, …). The global `QueryClient` (in `main.jsx`) sets `staleTime` 5 min, `cacheTime` 30 min, `refetchOnWindowFocus: false`, `retry: 2`. `useSkillTrend` additionally sets `placeholderData: (prev) => prev` so the line chart holds its previous render (no skeleton flash) while refetching after a skill is added/removed. `ResumePage` calls `resumeApi` directly rather than through a hook.

### 5.5 Theming (`src/context/ThemeContext.jsx`)

`ThemeProvider`/`useTheme` provide `{ theme, toggleTheme, isDark }`. The initial theme reads `localStorage['jobscript-theme']`, falling back to `prefers-color-scheme`. Toggling adds/removes the `dark` class on `<html>`; Tailwind uses class-based dark mode with `dark:` variants throughout.

### 5.6 Charts

- **Recharts** (`charts/Charts.jsx`): `SkillBarChart`, `CategoryBarChart`, `CategoryPieChart`, `SalaryPremiumChart`, `SalaryComparisonChart`, `CompanyBarChart`, `ContractTypePieChart`, `CountryComparisonChart`, `SkillTrendChart`, with a `useChartColors` hook that adapts to the theme.
- **D3** (named exports): `SimilarityHeatmap` (`Heatmap.jsx`) and `SkillNetworkGraph` (`NetworkGraph.jsx`) — force-directed graph and RdYlGn heatmap with zoom, drag, tooltips, and legends. These components exist in the codebase; the Skills and Career pages currently render their relationship data as tables/lists.

#### Chart design system (`utils/helpers.js` + `charts/Charts.jsx`)

All charts were rebuilt on a CVD-validated, theme-aware palette (light/dark hue sets chosen to clear a ≥12 ΔE colorblind-separation target and a lightness/chroma band against each theme's card surface — validated with the Claude Code `dataviz` skill's palette script, not eyeballed):

- **`SERIES_COLORS.light` / `.dark`** — 8 fixed categorical hue slots (blue, aqua, yellow, green, violet, red, magenta, orange). `getSeriesColor(index, isDark)` reads by slot; **slot order is the colorblind-safety mechanism** and is never reordered or extended — a 9th series folds into `SERIES_NEUTRAL` gray rather than generating a new hue.
- **`CATEGORY_SLOTS`** — a fixed skill-category → slot map covering all ~26 real taxonomy categories (grouped into 8 semantic families, e.g. `Data Warehouse`/`Database`/`Data Platform` all → the "yellow" storage slot), so a category keeps the *same* color on every chart, filter, and page — color follows the entity, never its current rank in a sorted list. `getCategoryColor(category, isDark)` looks it up; anything not in the map renders neutral gray (visibly "uncategorized") instead of silently colliding with a real slot.
- **Shared `ChartTooltip`** — one tooltip implementation used by every chart via a `rows(payload, label)` render-prop, so every chart gets a consistent color-chip-per-row, formatted values, and a themed border/background instead of each chart hand-rolling `formatter`/`contentStyle`.
- **Diverging measures** (salary premium: above/below market) use the blue↔red diverging pair with a `ReferenceLine` at zero, not a single hue — the sign is the point.
- **Bar charts**: solid hairline grids (never dashed), rounded data-ends, axis-label truncation (`truncate(n)`) with the full name still in the tooltip, and a `ReferenceLine` for "market average" on the salary-comparison chart so raw bars read as an instant comparison.
- **Pie/donut charts**: fold anything past the top 6 slices into an "Other" gray wedge (a chart can't carry more than ~6-7 color classes and stay readable), a center total label, and a legend with computed shares — no per-slice text labels cluttering the ring.
- **`SkillTrendChart`** (new): multi-series line chart for `/skills/trend`. Takes a `colorMap: {skill_name: slotIndex}` from the caller rather than assigning colors by array position, so a skill keeps its line color when another tracked skill is removed (the anti-pattern this avoids: "recolor on filter"). Small-sample months (< 200 postings) are flagged in the tooltip rather than hidden, so a spike isn't misread as a demand shift when it's really a thin month of data.

**`SkillsPage.jsx`** owns the trend UI: a chip row (add up to 5 skills via a `+ Add skill` select, remove via the chip's ×) backed by a `useRef` slot map that assigns each skill the next free color slot and never reassigns on removal; a 6m/12m/24m range toggle; and it auto-seeds the chart with the current role's top 3 skills the first time a role's data loads.

---

## 6. Data Transformation Layer (dbt)

### 6.1 Project Structure

```
dbt_project/
├── dbt_project.yml
├── profiles.yml.example      # copy to profiles.yml (uses DB_* env vars)
├── models/
│   ├── sources.yml
│   ├── intermediate/
│   │   ├── int_job_skills_enriched.sql
│   │   └── schema.yml
│   └── marts/
│       ├── mart_skill_demand.sql
│       ├── mart_skill_cooccurrence.sql
│       ├── mart_salary_by_skill.sql
│       ├── mart_company_leaderboard.sql
│       ├── mart_role_similarity.sql
│       ├── mart_skills_by_country.sql
│       └── schema.yml
```

The dbt project is named `job_script`. Vars `analysis_start_date` / `analysis_end_date` define a rolling window.

### 6.2 Sources (`models/sources.yml`)

Two source schemas:
- **`raw`** → `jobs`
- **`staging`** → `stg_jobs`, `stg_job_skills`, `dim_skills`, `dim_job_roles`, `dim_countries`

### 6.3 Profiles (`profiles.yml.example`)

`type: postgres` (dbt-postgres) with two outputs:
- **`dev`** — schema `staging` (default target)
- **`prod`** — schema `marts`

Both read `DB_HOST`, `DB_PORT` (default `6543`, the Supabase pooler), `DB_USER`, `DB_PASSWORD`, `DB_NAME` (default `postgres`), with `sslmode: require` and 4 threads. (The CI workflow generates its own `~/.dbt/profiles.yml` pointing at the Supabase host on port 5432.)

### 6.4 Intermediate Model

```sql
-- models/intermediate/int_job_skills_enriched.sql
{{ config(materialized='view', schema='staging') }}

SELECT
    js.job_id, js.skill_id, js.skill_name, js.mention_count,
    ds.skill_category, ds.skill_subcategory,
    j.search_role, j.country_code, j.company_name,
    j.salary_min, j.salary_max, j.salary_currency,
    (j.salary_min + j.salary_max) / 2.0 AS salary_midpoint,
    -- USD-normalized (§6.7) — cr.rate_to_usd is units of currency per $1
    j.salary_min / cr.rate_to_usd AS salary_min_usd,
    j.salary_max / cr.rate_to_usd AS salary_max_usd,
    ((j.salary_min + j.salary_max) / 2.0) / cr.rate_to_usd AS salary_midpoint_usd,
    j.contract_type, j.contract_time,
    j.job_posted_at::date AS job_posted_date
FROM {{ source('staging', 'stg_job_skills') }} js
LEFT JOIN {{ source('staging', 'dim_skills') }} ds ON js.skill_id = ds.skill_id
LEFT JOIN {{ source('staging', 'stg_jobs') }} j    ON js.job_id = j.job_id
LEFT JOIN {{ source('staging', 'currency_rates') }} cr ON j.salary_currency = cr.currency_code
WHERE j.job_id IS NOT NULL
  AND j.job_posted_at >= CURRENT_DATE - INTERVAL '60 days'
```
> The join key is `skill_id`, the freshness filter is a 60-day posting window, and the model is a **view in the `staging` schema**. There is no `confidence_score` column in the source table, so no confidence filter is applied.

### 6.5 Marts

| Model | Purpose | Notable logic |
|-------|---------|---------------|
| `mart_skill_demand` | Top skills per role+country | `job_count`, `demand_percentage`, ranks; native + `_usd` salary averages; top 50 per role/country |
| `mart_salary_by_skill` | Salary vs. market per skill | premium absolute/%/USD, requires ≥5 jobs |
| `mart_skills_by_country` | Skill demand across countries | `rank_by_country`, `top_country_for_skill`; min 3 jobs |
| `mart_skill_cooccurrence` | Skill pairs in the same job | `jaccard_similarity`, conditional probabilities; min 5 co-occurrences |
| `mart_company_leaderboard` | Top hiring companies | contract breakdown, `roles_hiring`, native + `_usd` salary averages; top 100 per role/country |
| `mart_role_similarity` | Role skill overlap | Jaccard, overlap & dice coefficients, top 10 shared skills |

All marts are materialized as `table` in the `marts` schema (physically landing in `staging_marts` per the dbt target — see §2.2 "Marts tables").

### 6.6 Tests (`schema.yml`)

Data tests are intentionally minimal: `not_null` on `int_job_skills_enriched.job_id`, and on `mart_skill_demand.skill_name` / `search_role`. `dbt test` runs these in CI after `dbt run`.

### 6.7 Currency Normalization (salary comparisons across countries)

**The bug this fixes:** every mart groups salary by `(search_role, country_code)`, which is currency-safe *within* a row — one country maps to one currency. But the API's "All Countries" view blends rows *across* countries with a plain `AVG()`, which silently averaged native-currency numbers as if they were the same unit. An Indian salary of `INR 2,500,000–3,600,000` (a normal ~$30–43k USD role) got averaged directly against a US salary of `USD 130,000`, inflating reported averages for some skills to **~$700–800k** (real example: "ETL" and "Claude" before the fix — see the migration comment for the full before/after).

**The fix — a dynamic conversion table, not hardcoded rates:**
- **`staging.currency_rates`** (`database/migrations/004_currency_rates.sql`): `currency_code` (PK), `rate_to_usd` (units of that currency per $1 USD), `fetched_at`, `source`.
- **`etl/fetch_currency_rates.py`**: fetches LIVE rates from [frankfurter.dev](https://frankfurter.dev) (ECB reference rates, free, no key) for whatever currencies are *actually present* in `staging.stg_jobs.salary_currency` right now — not a fixed list, so a new source's currency is picked up automatically — and upserts them. **Self-healing, never hardcoded**: if the API is unreachable or a currency isn't covered, the previous cached rate is left untouched (logged, not fatal) rather than falling back to any made-up number. Runs as its own step in both `refresh_all.py` and the CI workflow (`fx_rates` job), right before the dbt rebuild.
- **`int_job_skills_enriched.sql`** LEFT JOINs `currency_rates` and computes `salary_min_usd`/`salary_max_usd`/`salary_midpoint_usd` (`usd_amount = native_amount / rate_to_usd`) alongside the untouched native-currency fields.
- **Marts** (`mart_skill_demand`, `mart_salary_by_skill`, `mart_company_leaderboard`) carry both native and `_usd` aggregates. `salary_premium_percentage` is left alone everywhere — it's a ratio relative to that row's own same-currency market average, so it's already currency-invariant and safe to blend directly.
- **Backend** (`skills.py` `/demand`, `/demand/all`; `salary.py` all four endpoints; `companies.py` `/leaderboard`): every absolute salary figure is selected from the `_usd` columns — **even for a single-country query**, not just the blended one. Reason: the frontend renders every salary value through `formatCurrency()` with no currency argument (always labeled "$"), so returning native currency there would just be a correctly-computed number under the wrong label. `salary_currency: 'USD'` is returned as a literal in the blended branches. Genuine native-currency display (e.g. literal £ for a UK-only view) would be a good separate enhancement if ever wanted — it isn't implemented today, so USD-everywhere is the consistent, honest choice given the current frontend.

**Verified** (Jul 2026): "Machine Learning" under AI Engineer dropped from a corrupted blended figure to **$61,129** (matches a direct, job-count-weighted recomputation); "Claude" from ~$765k to **$98,311**; "ETL" from ~$784k to **$65,224**. Confirmed live via the running dashboard (Salary Analysis page), not just the API response — see the debugging note below about stale dev-server processes if you're re-verifying this.

> **Debugging note:** while verifying this fix, a screenshot briefly showed stale inflated figures again — root cause was an *orphaned uvicorn process from an earlier session*, still bound to port 8000, started before the code fix and never restarted with `--reload`. Python doesn't hot-reload without that flag, so an old process keeps serving old query logic indefinitely even after the files change and the database is correct. If a fix looks like it "isn't taking effect," check for stale listeners on the port before suspecting the database or the code: `Get-NetTCPConnection -LocalPort 8000 -State Listen` (PowerShell) or `lsof -i :8000` (Unix).

---

## 7. Deployment & DevOps

### 7.1 GitHub Actions — ETL (`.github/workflows/etl_pipeline.yml`)

- **Schedule**: `cron: '0 3 1,15 * *'` — the 1st and 15th of each month at 03:00 UTC. Also supports `workflow_dispatch` with `run_extraction` / `run_transformation` / `run_dbt` / `test_mode` inputs.
- **Python** 3.11, `actions/checkout@v4`, `actions/setup-python@v5`.
- **Secrets**: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `SUPABASE_URL`, `SUPABASE_HOST`, `SUPABASE_USER`, `SUPABASE_PASSWORD`, `SUPABASE_DB`, plus optional multi-source keys `JOOBLE_API_KEY`, `THEMUSE_API_KEY`, `USAJOBS_API_KEY`/`USAJOBS_USER_AGENT` (sources auto-skip when blank). (No Gemini key — discovery is local GLiNER.)
- **Jobs**:
  1. `extract` — `python extractor.py --days 60 --pages 3 --delay 1.5` followed by `python ingest_sources.py` (multi-source bots); both use `--test` in test mode. Uploads `extraction.log` + `ingestion.log` as artifacts.
  2. `transform` — `python transformer.py --batch-size 500 --fast-only` (taxonomy-only; GLiNER disabled).
  3. `dbt` — writes a `~/.dbt/profiles.yml`, then `dbt debug`, `dbt deps`, `dbt run --full-refresh`, `dbt test`, `dbt docs generate`; uploads artifacts.
  4. `archive` — (scheduled runs) calls `SELECT archive_skill_demand()`.
  5. `notify` — reports the status of all jobs.

### 7.2 Keep-Warm (`.github/workflows/keep_warm.yml`)

Cron `*/5 * * * *` curls `https://skill-hunt.onrender.com/health` to prevent the Render free-tier service from sleeping.

### 7.3 Backend Hosting — Render (`render.yaml`)

```yaml
services:
  - type: web
    name: skill-hunt-api
    env: python                 # Python buildpack (no Dockerfile)
    rootDir: backend
    buildCommand: pip install -r backend/requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    autoDeploy: true
    envVars:
      - key: SUPABASE_URL      # sync: false (set in dashboard)
      - key: CORS_ORIGINS      # jobscript.vercel.app + localhost
      - key: DEBUG             # false
      - key: CACHE_TTL_SECONDS # 3600
```
> There is no Dockerfile in the repo — Render builds the app with its Python buildpack.

### 7.4 Frontend Hosting — Vercel (`vercel.json`)

```json
{
  "version": 2,
  "builds": [
    { "src": "frontend/package.json", "use": "@vercel/static-build", "config": { "distDir": "dist" } }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "https://skill-hunt.onrender.com/api/$1" },
    { "src": "/(.*)", "dest": "/frontend/$1" }
  ],
  "env": { "VITE_API_URL": "@vite_api_url" }
}
```
A second `frontend/vercel.json` handles SPA client-side routing (rewrites to `index.html`).

---

## 8. Performance & Current Limitations

**Implemented:**
- **Pre-computed marts** — dbt aggregates once so the API serves ready-made tables.
- **Connection pooling** — asyncpg pool (min 2 / max 10), statement cache disabled for the Supabase pooler.
- **Indexing** — filter/join indexes on `raw.jobs` and `staging.*` (see §2.3).
- **Client caching** — React Query caches responses (5-min stale time) and dedupes requests.
- **CDN** — the frontend is served from Vercel's edge network.

**Declared but not yet active** (candidates for future work):
- Response-level API caching (`CACHE_TTL_SECONDS` / `cachetools` are wired but unused).
- API rate limiting (`rate_limit_per_minute` is configured but not enforced).
- Frontend code-splitting / route-level lazy loading and response gzip compression.

---

## 9. Security & Best Practices

- **Secrets** are provided via environment variables / GitHub Actions secrets, not committed.
- **Authentication**: Supabase Auth issues the tokens (passwords/OAuth never touch this backend); FastAPI verifies JWTs locally (HS256, `SUPABASE_JWT_SECRET`) or remotely against the Supabase Auth API. Personalized tables are protected by Row-Level Security against direct anon-key access.
- **SQL injection**: queries use asyncpg positional parameters (`$1, $2, …`); the company search builds an ILIKE pattern but still passes it as a bound parameter.
- **CORS**: restricted to an explicit origin whitelist from `CORS_ORIGINS`.
- **HTTPS**: enforced by Render and Vercel in production.
- **Error handling**: a global exception handler returns generic 500s and only reveals detail when `DEBUG=true`.
- **Code style**: Black (Python) and ESLint (JS/React) are configured.

---

## 10. Testing Status

There is currently **no automated test suite committed** to the repository. `pytest` / `pytest-asyncio` are listed in `backend/requirements.txt` and dbt data tests exist (§6.6), but there are no backend or frontend test files yet. Adding an API test suite (e.g. FastAPI `TestClient`) and frontend component tests is tracked on the roadmap.

---

## 📌 Summary

Job Script implements:

✅ **Layered ELT architecture** — raw → staging → marts → API → SPA  
✅ **Multi-source ingestion** — Adzuna + 7 connector bots (incl. Jooble for local 🇵🇰/🇮🇳 postings and 5 remote-jobs boards) normalized into one contract ([SCRAPING_BOTS.md](SCRAPING_BOTS.md))  
✅ **Hybrid skill extraction** — regex fast path + local GLiNER NER discovery (no LLM cost)  
✅ **Modern stack** — FastAPI + asyncpg, React + Vite, dbt-postgres, Supabase  
✅ **Auth & personalization** — Supabase Auth (email + Google OAuth), profiles with dashboard defaults, saved searches, resume history ([AUTH_SETUP.md](AUTH_SETUP.md))  
✅ **Resume Analyzer** — upload, parse, gap analysis, and role matching (account-linked when signed in)  
✅ **Automated pipeline** — GitHub Actions on the 1st & 15th, plus keep-warm ping  
✅ **Honest docs** — this guide reflects the code as it actually stands, including current limitations

---

**Last Updated:** July 2026  
**Version:** 1.0.0
