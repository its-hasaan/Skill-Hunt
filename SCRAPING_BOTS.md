# 🤖 Scraping Bots — Multi-Source Job Ingestion Guide

> How Job Script's data-collection bots work, how to set them up, and what you need to do manually.
> Focus: fresh job data every two weeks, with real coverage for **Pakistan, India, and worldwide-remote roles**.

---

## 📋 Table of Contents

1. [What Was Built](#1-what-was-built)
2. [Architecture](#2-architecture)
3. [The Sources](#3-the-sources)
4. [Legal & Compliance — Read This](#4-legal--compliance--read-this)
5. [Setup (Manual Steps)](#5-setup-manual-steps)
6. [Usage](#6-usage)
7. [Automation Schedule](#7-automation-schedule)
8. [Robustness Features](#8-robustness-features)
9. [Adding a New Source](#9-adding-a-new-source)
10. [Troubleshooting](#10-troubleshooting)
11. [FAQ](#11-faq)

---

## 1. What Was Built

A **multi-source ingestion layer** (`etl/ingest_sources.py` + `etl/connectors/`) that runs alongside the existing Adzuna extractor. Each source has a small "connector" bot that fetches jobs, normalizes them into one shared format, classifies each job into one of your 15 tracked roles, and lands them in `raw.jobs` — after which your **existing pipeline (transformer → dbt → API → frontend) handles them with almost no changes**.

New files:

```
etl/
├── ingest_sources.py              # Orchestrator: runs all enabled bots
├── config/sources_config.json     # Which bots run, and their settings
└── connectors/
    ├── __init__.py                # Connector registry
    ├── base.py                    # NormalizedJob contract + hardened HTTP session
    ├── utils.py                   # HTML→text, role classifier, date/salary parsing
    ├── remoteok.py                # RemoteOK API          (no key)
    ├── weworkremotely.py          # We Work Remotely RSS  (no key)
    ├── arbeitnow.py               # Arbeitnow API         (no key)
    ├── jobicy.py                  # Jobicy API            (no key)
    ├── himalayas.py               # Himalayas API         (no key)
    ├── jooble.py                  # Jooble API — LOCAL Pakistan + India (free key)
    ├── themuse.py                 # The Muse API          (keyless; free key = higher limits)
    ├── usajobs.py                 # USAJobs (US gov)      (free key; disabled by default)
    └── generic_scraper.py         # Polite HTML-scraper template (disabled by default)

database/migrations/
└── 001_multi_source_ingestion.sql # One-time DB migration (run manually — see §5)
```

Modified files:

| File | Change |
|------|--------|
| `etl/transformer.py` | `parse_raw_job()` now dispatches by source; connector jobs pass through a pre-normalized envelope; `source` carried into `stg_jobs` |
| `database/schema.sql` | `source` column on `raw.jobs`/`stg_jobs`, `pk` + `remote` countries, PKR currency |
| `backend/app/routers/stats.py` | Pakistan + Remote/Worldwide country names |
| `frontend/src/utils/helpers.js` | 🇵🇰 Pakistan + 🌐 Remote flags |
| `etl/requirements.txt` | `feedparser`, `beautifulsoup4`, `lxml` |
| `.github/workflows/etl_pipeline.yml` | Ingestion step added to the bi-weekly run + new optional secrets |
| `etl/.env.example` | New — documents every env var |

---

## 2. Architecture

```
                 ┌────────────────────────────────────────────┐
  every 2 weeks  │  GitHub Actions (cron: 1st & 15th, 03:00)  │
                 └───────────────┬────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────────┐
          │                      │                          │
   extractor.py           ingest_sources.py                 │
   (Adzuna, 17            (bots: RemoteOK, WWR,             │
    countries)             Arbeitnow, Jobicy,               │
          │                Himalayas, Jooble PK/IN,         │
          │                The Muse, ...)                   │
          │                      │                          │
          └────────────┬─────────┘                          │
                       ▼                                    │
             raw.jobs  (JSONB + source tag)                 │
                       │                                    │
             transformer.py  (skills extraction)            │
                       │                                    │
             staging.stg_jobs / stg_job_skills              │
                       │                                    │
             dbt  →  marts.*  →  FastAPI  →  React SPA ◄────┘
```

Key design decisions:

- **One contract, many sources.** Every bot outputs `NormalizedJob` (defined in `etl/connectors/base.py`) — same fields as `staging.stg_jobs`. The orchestrator wraps it in an envelope `{"_source", "_normalized", "_raw"}` and stores it in `raw.jobs.raw_data`. The transformer sees `_normalized` and passes it straight through. **Adding a source never touches the transformer, dbt, API, or frontend.**
- **Namespaced IDs.** Non-Adzuna jobs get `job_platform_id = "<source>:<external_id>"` (e.g. `remoteok:98765`). The existing `UNIQUE (job_platform_id, country_code)` constraint therefore keeps guaranteeing idempotency — re-running a bot never creates duplicates.
- **Role classification.** Boards like RemoteOK return *everything*. `RoleMatcher` (`etl/connectors/utils.py`) maps each job title against curated regex patterns for your 15 roles (most-specific-first, e.g. "Full Stack" tested before "Backend"). Jobs that don't clearly match a tracked role are **dropped** — this keeps `mart_skill_demand` clean. Titles are the primary signal; source tags are only a fallback and are matched one-by-one (never joined, which would let phrases span tag boundaries).
- **Geography buckets.** Local postings map to their country (`pk`, `in`); worldwide-remote roles go into a new `remote` pseudo-country. Both appear automatically in the dashboard's country filter (the filter is driven by `SELECT DISTINCT country_code FROM stg_jobs`).
- **Freshness.** dbt's `int_job_skills_enriched` only keeps jobs posted in the last **60 days**. Every connector parses the source's real posting date; if a source omits it, the orchestrator stamps ingestion time so the job isn't silently dropped.

---

## 3. The Sources

| Source | Type | Key needed | Coverage | PK/IN relevance |
|--------|------|-----------|----------|-----------------|
| **RemoteOK** | JSON API | No | Remote tech jobs worldwide | Remote roles open to PK/IN talent |
| **We Work Remotely** | RSS feeds | No | Remote programming/devops/full-stack | Remote roles open to PK/IN talent |
| **Arbeitnow** | JSON API | No | EU-centric; we keep remote-only | Remote roles |
| **Jobicy** | JSON API | No | Remote jobs, `anywhere` + `apac` regions | APAC-friendly remote roles |
| **Himalayas** | JSON API | No | Remote jobs w/ location restrictions | Detects PK/IN-eligible restrictions |
| **Jooble** ⭐ | REST API (POST) | **Free key** | Aggregates local boards worldwide | **Local Pakistan + India postings** — the on-the-ground data Adzuna lacks (Adzuna has no PK endpoint) |
| **The Muse** | JSON API | Optional free key | US/global + India + remote | India + remote listings |
| **USAJobs** | REST API | Free key | US federal government | None (off by default; enable for US gov coverage) |
| **Adzuna** (existing) | JSON API | Already set up | 17 countries incl. India | India |

⭐ **Jooble is the single most important key to get** for your Pakistan/India goal. It legally aggregates postings from hundreds of local boards (including inventory that originates on LinkedIn/Indeed/Rozee) and hands it to you through a clean, permitted API.

---

## 4. Legal & Compliance — Read This

You asked for bots that can beat "the advanced security of job platforms." Here is the honest engineering answer:

**LinkedIn, Indeed, Glassdoor, and Rozee.pk prohibit scraping in their Terms of Service and actively enforce it** (IP bans, fingerprinting, legal action — LinkedIn has litigated scraping repeatedly, e.g. *hiQ Labs*, which hiQ ultimately lost on the breach-of-contract claim). Building anti-bot evasion — rotating residential proxies, spoofing browser fingerprints, solving CAPTCHAs — would:

1. put the platform at legal risk (ToS breach, and in some jurisdictions computer-misuse exposure),
2. get your server IPs / Supabase project blocklisted,
3. break every few weeks as defenses change — the opposite of the "robust, automatic" system you want.

**So this project deliberately does not include evasion tooling.** Robustness here comes from *reliability engineering* (retries, backoff, idempotent writes, per-source isolation), not from fighting defenses.

### How you still get that data, legitimately

| You want | Compliant route |
|----------|-----------------|
| LinkedIn jobs | Most corporate LinkedIn postings are cross-posted to company ATS pages and aggregators. **Jooble and Adzuna already resell much of this inventory legally.** LinkedIn's own Talent APIs are partner-gated. |
| Indeed jobs | Indeed Publisher/API program is partner-gated; the same postings flow into Jooble/Adzuna. |
| Rozee.pk (Pakistan) | No public API. **Jooble's Pakistan search covers much of the same local inventory.** If you want a direct relationship, email Rozee about a data partnership — aggregators do this all the time. |
| Any small board with no API | Use `generic_scraper.py` **only after checking that board's ToS and robots.txt permit it**. The template obeys robots.txt automatically and fails closed (no robots.txt → no scraping). |
| Macro labor-market stats | Government APIs — USAJobs connector included; BLS/Eurostat publish aggregate statistics (not job postings) and can enrich dashboards later. |

The included bots identify themselves honestly (`SkillHuntBot/1.0` User-Agent with a link back to your site), respect rate limits, back off on HTTP 429, and link back to the original posting (`redirect_url`) — which also satisfies RemoteOK's attribution requirement.

---

## 5. Setup (Manual Steps)

Everything below is a one-time setup. Total time: ~20 minutes.

### Step 1 — Run the database migration ✅ required

Open the **Supabase dashboard → SQL Editor**, paste the contents of
[`database/migrations/001_multi_source_ingestion.sql`](database/migrations/001_multi_source_ingestion.sql), and run it.
(Or from a terminal: `psql "$SUPABASE_URL" -f database/migrations/001_multi_source_ingestion.sql`.)

It is idempotent (safe to run twice). It adds:
- `source` column to `raw.jobs` and `staging.stg_jobs` (existing rows become `'adzuna'`)
- `pk` (Pakistan) and `remote` (Remote/Worldwide) to `dim_countries`
- PKR to the currency function

Verify:
```sql
SELECT source, COUNT(*) FROM raw.jobs GROUP BY source;   -- shows 'adzuna' rows
SELECT * FROM staging.dim_countries WHERE country_code IN ('pk','remote');
```

### Step 2 — Install new Python dependencies ✅ required

```bash
cd etl
pip install -r requirements.txt        # adds feedparser, beautifulsoup4, lxml
```

### Step 3 — Get the free API keys 🔑 (recommended)

The five remote-boards bots work with **zero keys**. These unlock the rest:

**Jooble (local Pakistan + India — the important one):**
1. Go to https://jooble.org/api/about
2. Fill the short form (name, email, your site URL). Keys usually arrive by email within a day.
3. Add to `etl/.env`: `JOOBLE_API_KEY=your-key-here`

**The Muse (optional — raises rate limit):**
1. Go to https://www.themuse.com/developers/api/v2 and register.
2. Add to `etl/.env`: `THEMUSE_API_KEY=your-key-here`

**USAJobs (optional — US federal jobs, off by default):**
1. Register at https://developer.usajobs.gov/ (the User-Agent is your email).
2. Add both `USAJOBS_API_KEY` and `USAJOBS_USER_AGENT` to `etl/.env`, and set `"enabled": true` for `usajobs` in `etl/config/sources_config.json`.

A bot whose key is missing **skips itself with a log line** — nothing breaks.
Use [`etl/.env.example`](etl/.env.example) as the template for your `etl/.env`.

### Step 4 — Add GitHub Actions secrets ✅ required for automation

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|--------|-------|
| `JOOBLE_API_KEY` | your Jooble key |
| `THEMUSE_API_KEY` | your Muse key (optional) |
| `USAJOBS_API_KEY` / `USAJOBS_USER_AGENT` | only if you enabled USAJobs |

(The existing `SUPABASE_*` and `ADZUNA_*` secrets stay as they are.)

### Step 5 — First run 🚀

```bash
cd etl

# 1. Safe preview — fetches from every source, writes NOTHING to the DB:
python ingest_sources.py --test --dry-run

# 2. Real ingestion (all enabled sources → raw.jobs):
python ingest_sources.py

# 3. Transform (skills extraction) exactly as you always have:
python transformer.py --batch-size 500 --fast-only

# 4. Rebuild marts (or let the next CI run do it):
cd ../dbt_project && dbt run --full-refresh && dbt test
```

Then open the dashboard — **Pakistan 🇵🇰 and Remote/Worldwide 🌐 appear in the country filter automatically** once they have jobs.

### Step 6 — Redeploy backend/frontend

The `stats.py` and `helpers.js` edits (country names/flags) ship with your normal deploy: push to `main` → Render + Vercel auto-deploy.

---

## 6. Usage

### CLI reference — `etl/ingest_sources.py`

| Command | What it does |
|---------|--------------|
| `python ingest_sources.py` | Run **all enabled** bots, insert into `raw.jobs` |
| `python ingest_sources.py --source jooble` | Run one bot (forces it on even if `enabled: false`) |
| `python ingest_sources.py --test` | Tiny smoke-test run (few items per source) |
| `python ingest_sources.py --dry-run` | Fetch + log samples, **no DB writes** |
| `python ingest_sources.py --source remoteok --test --dry-run` | Fastest possible single-source check |

Every run logs to `etl/ingestion.log` and prints a per-source summary:

```
INGESTION COMPLETE — batch 4839e940-...
  remoteok         88 fetched / 71 new
  weworkremotely   49 fetched / 49 new
  jooble           412 fetched / 380 new
  TOTAL            720 fetched / 655 new
```

### Configuration — `etl/config/sources_config.json`

- Toggle any bot with `"enabled": true/false`.
- Roles are inherited from `extraction_config.json` (single source of truth).
- Per-source knobs: `max_pages`, `max_jobs`, `delay_seconds`, `locations` (Jooble), `geos` (Jobicy), `feeds` (WWR).
- Want more Pakistan coverage? Jooble's `"locations"` accepts cities too: `["Pakistan", "Karachi", "Lahore", "India", "Bangalore"]`.

### Checking results

```bash
cd etl && python check_progress.py          # raw vs staged counts
```
```sql
-- jobs per source / country
SELECT source, country_code, COUNT(*) FROM staging.stg_jobs
GROUP BY source, country_code ORDER BY count DESC;
```

---

## 7. Automation Schedule

The existing workflow (`.github/workflows/etl_pipeline.yml`) already runs **every two weeks** — the 1st and 15th at 03:00 UTC. The multi-source ingestion step now runs inside it, right after Adzuna extraction:

```
extract job:   extractor.py --days 60 --pages 3    (Adzuna)
               ingest_sources.py                    (all bots)   ← new
transform job: transformer.py --batch-size 500 --fast-only
dbt job:       dbt run --full-refresh && dbt test
archive job:   SELECT archive_skill_demand()
```

Manual trigger: repo → **Actions → ETL Pipeline → Run workflow** (with optional test mode).
Nothing else to schedule — your two-week cadence is already wired.

---

## 8. Robustness Features

Because "robust" should mean *keeps working unattended*, the bots have:

| Feature | Where | Detail |
|---------|-------|--------|
| Automatic retries + exponential backoff | `base.build_session()` | 4 retries on HTTP 429/500/502/503/504, honors `Retry-After` |
| Rate limiting | every connector | configurable `delay_seconds` between requests (default 2s) |
| Real User-Agent | `base.py` | identifies the bot honestly; also required by RemoteOK |
| Timeouts | all requests | 30s — a hung source can't stall the run |
| Per-source isolation | `ingest_sources.py` | one source crashing is logged and skipped; the rest still run |
| Graceful key handling | `is_available()` | missing key → skip with instructions, not a crash |
| Idempotent writes | `ON CONFLICT DO NOTHING` | re-runs never duplicate jobs |
| Batch tagging | `extraction_batch_id` | every run traceable in the DB |
| Date backfill | orchestrator | missing posting date → stamped now, so dbt's 60-day window can't silently eat jobs |
| Quality gates | orchestrator + `RoleMatcher` | jobs without title/URL dropped; titles that don't match a tracked role dropped |
| HTML stripped at ingestion | `utils.html_to_text()` | skill regexes run on clean text, not markup |
| Dry-run mode | `--dry-run` | test any change with zero DB risk |

---

## 9. Adding a New Source

Three small steps (no changes to transformer/dbt/API/frontend, ever):

1. **Write the connector** — `etl/connectors/mysource.py`:

```python
from .base import BaseConnector, NormalizedJob
from .utils import html_to_text, to_iso, detect_country_code

class MySourceConnector(BaseConnector):
    name = "mysource"

    def fetch(self):
        data = self._get_json("https://api.mysource.com/jobs")
        self._sleep()
        for item in data.get("jobs", []):
            role = self._match_role(item["title"])
            if not role:
                continue
            yield NormalizedJob(
                source=self.name,
                external_id=str(item["id"]),
                search_role=role,
                country_code=detect_country_code(item.get("location", "")),
                title=item["title"],
                company_name=item.get("company", ""),
                description=html_to_text(item.get("description", "")),
                redirect_url=item["url"],
                job_posted_at=to_iso(item.get("posted_at")),
                raw=item,
            )
```

2. **Register it** — add to `CONNECTOR_REGISTRY` in `etl/connectors/__init__.py`.
3. **Configure it** — add a block under `"sources"` in `etl/config/sources_config.json` with `"enabled": true`.

Test with `python ingest_sources.py --source mysource --test --dry-run`.

For an HTML board with no API (that permits scraping), skip step 1 and use the
`generic_scraper` connector with CSS selectors — see the `_example_local_scraper`
block in `sources_config.json` and the policy notes in `generic_scraper.py`.

---

## 10. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `jooble: JOOBLE_API_KEY not set — skipping` | Expected until you add the key (§5 step 3). |
| `weworkremotely: feedparser not installed` | `pip install -r etl/requirements.txt`. |
| RemoteOK returns HTTP 403 | It rejects generic clients; the built-in session sends a proper User-Agent. If it persists, RemoteOK may be rate-limiting — increase `delay_seconds`. |
| Jobicy HTTP 400 | Invalid `geo` slug. Valid values are Jobicy's predefined regions (`apac`, `usa`, `europe`, ...). `anywhere` means *omit* the param (the connector handles this). |
| `column "source" does not exist` | You haven't run the migration (§5 step 1). |
| New jobs don't show in the dashboard | Run the transformer, then dbt (`dbt run --full-refresh`). Also note dbt only keeps jobs posted within 60 days. |
| A source suddenly yields 0 jobs | Check `etl/ingestion.log`. APIs change; run `--source X --test --dry-run` to inspect. Other sources are unaffected. |
| Country filter shows `pk` with no pretty name | Redeploy backend/frontend (the name/flag maps were updated in this change). |
| Duplicate-looking jobs across sources | The same real-world job can exist on two boards with different IDs. Cross-source content dedup is a future enhancement (see FAQ). |

---

## 11. FAQ

**Q: Why is there no LinkedIn/Indeed/Rozee connector?**
See §4. Direct scraping of those sites breaks their ToS and any bot would be an arms race you lose. Jooble/Adzuna legally carry much of the same inventory — that's the route this system takes.

**Q: How fresh is the data?**
Bots run every two weeks with the CI pipeline; each pulls jobs with their original posting dates, and dbt keeps a rolling 60-day window. You can also trigger a run any time from the Actions tab or your terminal.

**Q: Does this cost anything?**
No. Every wired source has a free tier, and the bots' volumes stay well inside them. GitHub Actions minutes remain minimal (a few extra minutes per bi-weekly run).

**Q: What about jobs in Urdu/Hindi?**
The role matcher and skill taxonomy are English-based. PK/IN tech postings are overwhelmingly in English, so coverage is good; non-English postings are simply skipped.

**Q: The same job appears from two sources — is that a problem?**
Mildly inflates counts, but demand *percentages* (the dashboard's primary metric) are barely affected since duplication is roughly uniform within a role. A content-hash dedup (same title+company+country within a window) is the natural next enhancement if it becomes noticeable.

**Q: Can I run the bots more often than every two weeks?**
Yes — they're idempotent, so run them daily if you like: edit the cron in `etl_pipeline.yml` (e.g. `0 3 */3 * *` for every 3 days). Keep `delay_seconds` ≥ 2 to stay polite.

---

**Last Updated:** July 2026
