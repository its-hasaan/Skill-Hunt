# Phase 1b: Company Job-Board Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull remote (and Pakistan/India-local) tech jobs every day straight from the public job-board APIs of the hiring systems companies use (Greenhouse, Lever, Ashby, SmartRecruiters). Each job comes with its full description and direct apply link, a lifecycle (first seen / last seen / closed), and a company registry that grows itself.

**Architecture:**
- A new `ops.companies` table lists `(ats, board_token)` boards. Seed and discovery tools fill it, and a validator probes each board before it's used.
- One connector module per hiring system maps that system's JSON into the existing `NormalizedJob`, through pure, fixture-tested functions. A shared `classify_location()` decides remote/hybrid/onsite and the country bucket.
- Ingest switches from "insert if new" to an upsert that records sightings, so jobs a board no longer lists get closed.
- The transformer stores `workplace_type`.

**Tech Stack:** Python 3.11, requests, `concurrent.futures`, psycopg2, pytest (Postgres container), the Common Crawl CDX index.

**Spec:** `docs/superpowers/specs/2026-09-30-jobwise-product-roadmap-design.md` §6.1–6.2 (new sources, job lifecycle). Eligibility, dedup and the feed mart are Phase 1c; the career-page crawler is 1d.

## Global Constraints

- Hiring systems this phase: `greenhouse`, `lever`, `ashby`, `smartrecruiters`. **Workable is deferred** (its public endpoints return 404).
- Keep a job only if `RoleMatcher(title)` finds one of the 20 roles **and** it's remote (anywhere) or located in Pakistan or India. Onsite or hybrid jobs elsewhere are dropped.
- `job_platform_id = "<ats>:<board>:<id>"`. `country_code` = `pk`/`in` when every location is in that country, otherwise `remote`.
- Politeness: a named user agent (existing `build_session`), at most **4 concurrent requests** per hiring-system host, retries already handled by the session, and `ops.companies` remembers failures so dead boards stop being polled.
- A board that errors or times out never closes its jobs. Only a successful full fetch closes the jobs it no longer lists.
- Git: commit and push each task when its tests pass; 5–8 word messages; no Claude attribution.

## Review Focus

1. **A board fetch fails mid-run.** Expected: its open jobs stay open, not mass-closed. Test: Task 1 `test_failed_board_closes_nothing`.
2. **A job reappears after being closed.** Expected: `closed_at` cleared and `last_seen_at` bumped, with no duplicate row. Test: Task 1 `test_reseen_job_reopens`.
3. **"Remote, Bangalore" / "Remote (US)" / "Hybrid – Lahore".** Expected: India-remote → `in`, US-remote → `remote` (eligibility decided later), Lahore hybrid → `pk`, New York onsite → dropped. Test: Task 3 `test_classify_location_cases`.
4. **A 404 / renamed board.** Expected: marked inactive after 3 consecutive failures; no crash. Test: Task 2 `test_validate_marks_dead_boards_inactive`.
5. **HTML entities in Greenhouse `content`** (`&lt;p&gt;`). Expected: plain text with no tags. Test: Task 4 `test_greenhouse_maps_real_sample`.

---

## File Structure

| File | Responsibility |
|---|---|
| `database/migrations/011_job_lifecycle.sql` | `raw.jobs.first_seen_at/last_seen_at/closed_at` (+ backfill, index); `staging.stg_jobs.workplace_type` |
| `database/migrations/012_ats_companies.sql` | `ops.companies` registry |
| `etl/ingest_sources.py` (modify) | Upsert with sightings; close unseen jobs for fully fetched boards |
| `etl/ops/lifecycle.py` (new) | `save_jobs(...) -> (inserted, seen)`, `close_unseen(...)`, `age_out_feed_jobs(...)` |
| `etl/ops/companies.py` (new) | Registry access + `validate`/`seed` CLI |
| `etl/config/ats_seed_companies.json` (new) | Hand-picked starting boards |
| `etl/connectors/location.py` (new) | `classify_location(locations, workplace_hint, remote_flag) -> (workplace_type, country_code) or None` |
| `etl/connectors/ats_base.py` (new) | `AtsConnector(BaseConnector)`: loads boards, thread pool, filters, `seen_boards` |
| `etl/connectors/{greenhouse,lever,ashby,smartrecruiters}.py` (new) | Pure `map_job(board, item) -> dict` + `fetch_board()` |
| `etl/connectors/base.py` (modify) | `NormalizedJob.workplace_type` field |
| `etl/connectors/__init__.py`, `etl/config/sources_config.json` (modify) | Register + enable the 4 sources |
| `etl/transformer.py` (modify) | Persist `workplace_type` |
| `etl/ops/discover_companies.py` (new) | Common Crawl CDX → candidate boards → `ops.companies` |
| `etl/tests/test_lifecycle.py`, `test_companies.py`, `test_location.py`, `test_ats_connectors.py`, `test_discover.py` | Tests (fixtures in `tests/fixtures/ats/`) |
| `.github/workflows/etl_pipeline.yml` (modify) | Weekly discovery + validation step (Mondays) |

---

### Task 1: Job lifecycle (sightings + closing)

**Interfaces — Produces:** `ops.lifecycle.save_jobs(conn, rows: list[tuple]) -> tuple[int, int]` (inserted, seen), where each row is `(job_platform_id, search_role, country_code, raw_json, batch_id, source)`; `close_unseen(conn, source: str, boards: list[str], since) -> int`; `age_out_feed_jobs(conn, days: int = 14, exclude_sources: set[str]) -> int`.

- [ ] **Step 1: Failing tests** (`etl/tests/test_lifecycle.py`) on `pipeline_db` (add the three lifecycle columns to `fixtures/pipeline_schema.sql`). Cover:
  - `test_new_rows_insert_and_seen_rows_bump_last_seen` — the second save of the same ids returns `(0, n)` and moves `last_seen_at` forward.
  - `test_close_unseen_only_for_fetched_boards` — board A was fetched and is missing job A2, so A2 closes; board B wasn't fetched, so its jobs stay open.
  - `test_failed_board_closes_nothing` — `close_unseen(..., boards=[])` returns 0.
  - `test_reseen_job_reopens` — a closed job saved again gets `closed_at` NULL.
  - `test_age_out_feed_jobs` — a remoteok job unseen for 15 days closes; a greenhouse job (excluded) doesn't.
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Migration 011**:
```sql
BEGIN;
ALTER TABLE raw.jobs ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMP;
ALTER TABLE raw.jobs ADD COLUMN IF NOT EXISTS last_seen_at  TIMESTAMP;
ALTER TABLE raw.jobs ADD COLUMN IF NOT EXISTS closed_at     TIMESTAMP;
UPDATE raw.jobs SET first_seen_at = extracted_at WHERE first_seen_at IS NULL;
UPDATE raw.jobs SET last_seen_at  = extracted_at WHERE last_seen_at IS NULL;
ALTER TABLE raw.jobs ALTER COLUMN first_seen_at SET DEFAULT now();
ALTER TABLE raw.jobs ALTER COLUMN last_seen_at  SET DEFAULT now();
CREATE INDEX IF NOT EXISTS idx_raw_jobs_open ON raw.jobs (source, last_seen_at) WHERE closed_at IS NULL;
ALTER TABLE staging.stg_jobs ADD COLUMN IF NOT EXISTS workplace_type TEXT;
COMMIT;
```
- [ ] **Step 4: `etl/ops/lifecycle.py`**:
  - `save_jobs` runs `INSERT … ON CONFLICT (job_platform_id, country_code) DO UPDATE SET last_seen_at = now(), closed_at = NULL RETURNING (xmax = 0)` through `execute_values(..., fetch=True)`, and counts the `True` values as inserted.
  - `close_unseen` runs `UPDATE raw.jobs SET closed_at = now() WHERE source = %s AND split_part(job_platform_id, ':', 2) = ANY(%s) AND last_seen_at < %s AND closed_at IS NULL`.
  - `age_out_feed_jobs` runs the same update keyed on `last_seen_at < now() - interval`, for sources not in `exclude_sources`.
- [ ] **Step 5: `ingest_sources.py`**: `save_to_database` calls `lifecycle.save_jobs` and logs `new`/`seen`. After a connector that exposes `seen_boards` finishes, call `close_unseen(source, connector.seen_boards, run_started)`, where `run_started` is the DB `now()` captured before the source ran. At the end of `run()`, call `age_out_feed_jobs(conn, 14, ATS_SOURCES)` with `ATS_SOURCES = {"greenhouse", "lever", "ashby", "smartrecruiters"}`.
- [ ] **Step 6:** Run all tests → pass. Apply 011 to production (`python -m ops.migrate up`). Commit `"Track job sightings and close stale jobs"`.

### Task 2: Company registry + seed + validator

**Interfaces — Produces:** table `ops.companies(id, ats, board_token, name, active bool NULL, fail_count int, last_checked_at, last_job_count, discovered_via, created_at, UNIQUE(ats, board_token))`; `ops.companies.active_boards(conn, ats) -> list[str]`; `upsert_candidates(conn, ats, tokens, via) -> int`; `record_check(conn, ats, token, ok: bool, job_count: int | None)` (3 consecutive failures → `active = false`; success → `active = true`, `fail_count = 0`); `validate(conn, probe, ats=None, limit=None) -> dict`, where `probe(ats, token) -> int | None` (job count, or None on 404/error); CLI `python -m ops.companies seed|validate [--ats X] [--limit N]`.

- [ ] **Step 1: Failing tests** (`test_companies.py`):
  - `test_upsert_candidates_is_idempotent`
  - `test_validate_marks_live_boards_active` (fake probe → 12)
  - `test_validate_marks_dead_boards_inactive` (three failing validations flip it to inactive; one success resets it)
  - `test_active_boards_only_returns_active`
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Migration 012** (the table, an index on `(ats, active)`, and the guarded `REVOKE` from `anon`/`authenticated`, as in 007). Implement `ops/companies.py`. The real `probe` uses each connector's `fetch_board` URL with `limit=1` where supported and returns the job count.
- [ ] **Step 4: Seed file** `etl/config/ats_seed_companies.json`: `{"greenhouse": [...], "lever": [...], "ashby": [...], "smartrecruiters": [...]}`, with well-known remote-friendly tech employers (about 40 per system; unverified tokens are fine, since the validator deactivates dead ones). `seed` inserts them with `discovered_via='seed'`.
- [ ] **Step 5:** Tests pass. Apply 012. Run `python -m ops.companies seed && python -m ops.companies validate` on production and record the active counts per system. Commit `"Add hiring-system company registry"`.

### Task 3: Location classification

**Interfaces — Produces:** `connectors.location.classify_location(locations: list[str], workplace_hint: str | None = None, remote_flag: bool | None = None) -> tuple[str, str] | None` returning `(workplace_type, country_code)` with `workplace_type ∈ {remote, hybrid, onsite}`, or `None` (drop).

- [ ] **Step 1: Failing table test** `test_classify_location_cases`:

| Input | Expected |
|---|---|
| `["Remote, Bangalore"]` | `("remote","in")` |
| `["Remote, United States"]` | `("remote","remote")` |
| `["Remote, Canada; Remote, United Kingdom"]` | `("remote","remote")` |
| `["Anywhere"]` | `("remote","remote")` |
| `["Lahore, Pakistan"]` + hint `hybrid` | `("hybrid","pk")` |
| `["Karachi"]` + hint `onsite` | `("onsite","pk")` |
| `["New York, NY"]` + hint `onsite` | `None` |
| `["New York, NY (HQ)", "Remote (US)"]` + `remote_flag=True` | `("remote","remote")` |
| `["London"]` + hint `hybrid` | `None` |
| `["Remote - India", "Remote - Pakistan"]` | `("remote","remote")` (multi-country stays generic) |

- [ ] **Step 2: Implement** using the existing `connectors.utils.detect_country_code` for Pakistan/India cities and a `REMOTE_RE = r"\b(remote|anywhere|worldwide|distributed|work from home|wfh)\b"`. A job is remote if `remote_flag` is set, or the hint is `remote`, or any location matches `REMOTE_RE`. The country is `pk`/`in` only if *every* location resolves to that one country; otherwise `remote`. A non-remote job is kept only when it's in Pakistan or India.
- [ ] **Step 3:** Tests pass. Commit `"Classify job locations for remote-first feed"`.

### Task 4: Connectors (Greenhouse, Lever, Ashby, SmartRecruiters)

**Interfaces — Consumes:** `classify_location`, `RoleMatcher`, `active_boards`, `record_check`. **Produces:** per module a pure `map_job(board: str, item: dict) -> dict | None` (NormalizedJob kwargs before role and location filtering) and `fetch_board(session, board) -> list[dict] | None`. `AtsConnector.fetch()` yields `NormalizedJob`s and sets `self.seen_boards`. `NormalizedJob.workplace_type: str = ""`.

| System | Endpoint | Mapping notes |
|---|---|---|
| greenhouse | `https://boards-api.greenhouse.io/v1/boards/{b}/jobs?content=true` → `jobs[]` | title; `absolute_url`; locations = `location.name` split on `;` plus `offices[].name`; `content` is HTML-escaped (`html.unescape`, then `html_to_text`); posted = `first_published` or `updated_at` |
| lever | `https://api.lever.co/v0/postings/{b}?mode=json` → `[]` | `text`; `hostedUrl`; `categories.allLocations` or `[location]`; hint = `workplaceType`; country from the ISO `country`; description = `descriptionPlain` + lists + `additionalPlain`; posted = `createdAt` (ms); salary from `salaryRange` when the interval is yearly |
| ashby | `https://api.ashbyhq.com/posting-api/job-board/{b}?includeCompensation=true` → `jobs[]` (skip `isListed == false`) | title; `jobUrl`; locations = `location` + `secondaryLocations[].location`; hint = `workplaceType`; `remote_flag = isRemote`; `descriptionPlain`; `publishedAt`; salary parsed from `compensation.scrapeableCompensationSalarySummary` via `parse_salary_range` |
| smartrecruiters | `https://api.smartrecruiters.com/v1/companies/{b}/postings?limit=100&offset=…` → `content[]`; detail at `ref` | name; locations = `location.fullLocation`; `remote_flag = location.remote`, `hybrid` → hint; the **detail call only for postings that pass the role and location filter**; description = joined `jobAd.sections[*].text`; `postingUrl`; `releasedDate` |

- [ ] **Step 1: Failing tests** (`test_ats_connectors.py`) using the saved real samples in `tests/fixtures/ats/`:
  - `test_greenhouse_maps_real_sample` (titles, plain-text description with no `<`, location list, URL, ISO date)
  - `test_lever_maps_real_sample` (hint `hybrid`, country GB → dropped by the filter)
  - `test_ashby_maps_real_sample` (`isRemote` True + "Remote (US)" secondary → kept as remote; salary parsed)
  - `test_smartrecruiters_maps_list_and_detail`
  - `test_connector_filters_roles_and_locations` (a fake `fetch_board` returning mixed jobs → only tech + remote/pk/in yielded, ids namespaced `ats:board:id`)
  - `test_connector_tracks_seen_boards_and_skips_failed` (a board returning `None` is excluded from `seen_boards`, and `record_check` gets ok=False)
- [ ] **Step 2: Run** → fail. **Step 3: Implement** `ats_base.py` (a thread pool of `max_workers = config.get("concurrency", 4)` and `max_boards` from config), the four modules, the `NormalizedJob.workplace_type` field, registry entries, `sources_config.json` blocks (`enabled: true`, `concurrency: 4`, `max_boards: 400`), and the transformer's `workplace_type` mapping in `parse_normalized_job` and the stg INSERT.
- [ ] **Step 4:** Run all tests → pass. Then do a **production dry run**: run `python ingest_sources.py --source greenhouse --dry-run` (and once per system) and record fetched/kept counts. Then run the real ingestion for all four, followed by `python transformer.py --batch-size 500 --fast-only`, and record new staging rows per role.
- [ ] **Step 5:** Commit `"Add Greenhouse, Lever, Ashby, SmartRecruiters connectors"`.

### Task 5: Company discovery from Common Crawl

**Interfaces — Produces:** `ops.discover_companies.extract_tokens(urls: list[str]) -> dict[str, set[str]]` (by system); `crawl(index: str, max_pages: int, fetch=…) -> dict[str, set[str]]`; CLI `python -m ops.discover_companies [--index CC-MAIN-…] [--max-pages N]`, which upserts candidates (`discovered_via='commoncrawl'`) and then validates up to `--validate-limit` new candidates.

- [ ] **Step 1: Failing tests** (`test_discover.py`):
  - `extract_tokens` handles `boards.greenhouse.io/{t}/jobs/123`, `job-boards.greenhouse.io/{t}`, `jobs.lever.co/{t}/uuid`, `jobs.ashbyhq.com/{t}/uuid?utm…` and `jobs.smartrecruiters.com/{t}/…`. It ignores `embed`, `api`, `assets` and empty segments, and lowercases Greenhouse/Lever/Ashby tokens (SmartRecruiters ids are case-sensitive and kept as-is).
  - `crawl` stops on the first empty page and sends one request per page through an injected fetcher.
- [ ] **Step 2: Implement.** The CDX query is `https://index.commoncrawl.org/{index}-index?url={host}/*&output=json&fl=url&page={n}`, at 1 request/second. The latest index id comes from `https://index.commoncrawl.org/collinfo.json`. Timeouts and 5xx mean skip that host and continue.
- [ ] **Step 3:** Tests pass. Run on production with `--max-pages 3` per host and record the candidates found and validated. Commit `"Discover company job boards from Common Crawl"`.

### Task 6: CI + docs

- [ ] In `etl_pipeline.yml`, add a Monday-only step after ingest, `continue-on-error`: `python -m ops.run_step --step discover -- python -m ops.discover_companies --max-pages 2 --validate-limit 150`. Add `discover` to the notify results. Run actionlint → clean.
- [ ] CLAUDE.md:
  - the company job-board sources and `ops.companies`
  - lifecycle columns
  - how to add a board (`python -m ops.companies seed` after editing the seed file)
  - the Workable deferral
  - Phase 1b status
- [ ] Update memory. Commit `"Document Phase 1b job-board connectors"`.

## Self-review notes
- Spec §6.1: the four hiring-system connectors (T4; Workable deferred with reason), the company list from seed + Common Crawl (T2, T5), and politeness (constraints).
- Spec §6.2: `first_seen_at`/`last_seen_at`/`closed_at` with the full-snapshot closing rule and the 14-day feed rule (T1); `workplace_type` (T1 + T4).
- Fingerprint dedup, `job_enrichment` and `mart_job_feed` are Phase 1c by design.
- Names are consistent: `seen_boards`, `close_unseen`, `classify_location`, and `map_job`/`fetch_board` per module.
