# Phase 1c: Duplicate Removal, Eligibility Tagging, Feed Mart — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the open jobs in staging into a daily feed of unique jobs, each tagged with whether someone in Pakistan or India can apply from there, plus seniority, minimum years, timezone overlap and USD salary, so Phase 2 can serve and score them.

**Architecture:**
- Pure, table-tested logic lives in a new `etl/enrich/` package: a place gazetteer (`geo`), job fingerprints (`fingerprint`), eligibility rules (`eligibility`), seniority/years/timezone/salary extraction (`attributes`) and a Gemini Flash client for the jobs the rules can't decide (`gemini`).
- Database orchestration lives in `etl/ops/` like every other pipeline step: `ops.dedup` (fingerprints + `canonical_job_id`) and `ops.enrich` (rules pass, optional AI pass) write `staging.stg_jobs` columns and `staging.job_enrichment`.
- dbt builds `staging_marts.mart_job_feed`: one row per open canonical feed job with its enrichment and skills. CI runs dedup → enrich → feed mart after the transform, every day, outside the analytics marts guard.

**Tech Stack:** Python 3.11, psycopg2, requests, pytest (Postgres container), dbt-postgres, Gemini REST API (`generativelanguage.googleapis.com/v1beta`).

**Spec:** `docs/superpowers/specs/2026-09-30-jobwise-product-roadmap-design.md` §6.2 (data model), §6.3 (enrichment logic), §4 (Phase 1 exit criteria), §12 (wrong eligibility labels risk).

## Global Constraints

- Feed candidates = jobs whose raw row is open (`raw.jobs.closed_at IS NULL`) and that are remote (`workplace_type = 'remote'`) or located in Pakistan/India (`country_code IN ('pk','in')`).
- Canonical preference (spec §6.2): company hiring system (`greenhouse`, `lever`, `ashby`, `smartrecruiters`) > career page (`careerpage`, Phase 1d) > remote boards and Jooble > Adzuna. Ties: latest `last_seen_at`, then lowest `job_id`.
- Eligibility is a tri-state per country: `TRUE` (can apply), `FALSE` (can't), `NULL` (unclear). "Missing a job is better than wrongly promising someone they can apply" (§6.3): the rules return `TRUE` only on explicit evidence.
- Every label carries `eligibility_evidence` (the location string or the quoted sentence it was decided from) and `method` (`rules` | `llm`).
- `staging.job_enrichment` is keyed by `job_id` with a `content_hash`; a job is re-enriched only when its text changes or, for `method='rules'`, when `RULES_VERSION` increases. LLM labels are never overwritten by rules for the same content hash.
- AI fallback runs **only** when `GEMINI_API_KEY` is set. Without it the step prints a notice and exits 0; unclear jobs stay `NULL`. The key is sent as the `x-goog-api-key` header, never in a URL or log. Only public job-posting text goes to Gemini (D4).
- Gemini: batches of 20 jobs per call, JSON output, evidence must appear verbatim in the posting or the label is downgraded to unclear. Model from `GEMINI_MODEL` (default `gemini-2.5-flash`), at most `--max-calls` calls per run (default 150), ≥ 6.5 s between calls (free tier ≈ 10 requests/min).
- `mart_job_feed` does not copy descriptions (storage: the 500 MB free tier); the API reads them from `staging.stg_jobs` by `job_id`.
- Migrations: `database/migrations/013_*.sql`, `BEGIN; … COMMIT;`, idempotent, applied with `python -m ops.migrate up`; the new table gets the guarded `REVOKE` from `anon`/`authenticated` like 007/012.
- Git: commit and push each task when its tests pass; 5–8 word messages; no Claude attribution.

## Review Focus

1. **"Remote" with no place at all and a US-only sentence buried in the description** ("You must be based in the United States"). Expected: `eligible_pk = FALSE` from the sentence, evidence = that sentence. Test: Task 3 `test_description_restriction_beats_bare_remote_location`.
2. **"Remote, IN" / "Indianapolis, IN" / "Remote, CA".** Expected: `IN` is never read as India from a two-letter code (Indiana); `, CA` reads as California (US). Test: Task 1 `test_parse_places_ambiguous_codes`.
3. **The same job on Greenhouse and Himalayas** (company "GitLab" vs board token "gitlab", title "Senior Backend Engineer (Remote)" vs "Senior Backend Engineer"). Expected: one fingerprint; the Greenhouse row is canonical. Test: Task 2 `test_cross_source_duplicate_prefers_company_board`.
4. **Gemini returns evidence that isn't in the posting, malformed JSON, or a 429.** Expected: invented evidence → unclear; malformed batch → those jobs stay rules-labelled and the run continues; 429 → wait and retry, then stop the run cleanly (exit 0). Test: Task 6 `test_llm_evidence_must_be_quoted`, `test_llm_bad_json_keeps_rules_label`, `test_llm_quota_stops_cleanly`.
5. **A job's text changes after it was labelled by the LLM.** Expected: re-enriched by rules (new hash), then eligible for the LLM again; unchanged LLM rows are left alone even when `RULES_VERSION` increases. Test: Task 5 `test_reenrich_only_when_content_or_rules_change`.

---

## File Structure

| File | Responsibility |
|---|---|
| `etl/enrich/__init__.py` | Package marker |
| `etl/enrich/geo.py` | `parse_places(text) -> Places` (countries ISO2 + regions + remote/worldwide words); region membership for `pk`/`in` |
| `etl/enrich/fingerprint.py` | `normalise_company`, `normalise_title`, `fingerprint(company, title, location_text) -> str`, `SOURCE_PRIORITY` |
| `etl/enrich/eligibility.py` | `RULES_VERSION`, `Eligibility` dataclass, `classify(job) -> Eligibility` (location fields + description sentences) |
| `etl/enrich/attributes.py` | `seniority(title, min_years)`, `min_years(text)`, `tz_overlap(text)`, `salary_from_text(text)` |
| `etl/enrich/gemini.py` | `GeminiClient`, `build_prompt(jobs)`, `parse_labels(response_json, jobs) -> dict[int, Eligibility]` |
| `etl/ops/dedup.py` | Fill `stg_jobs.fingerprint` for new rows; assign `canonical_job_id` across open jobs (CLI) |
| `etl/ops/enrich.py` | Select candidates needing enrichment, run rules (+ optional LLM), upsert `staging.job_enrichment` (CLI) |
| `etl/ops/eligibility_sample.py` | Dump a stratified sample of feed jobs to Markdown for the hand check (CLI) |
| `database/migrations/013_dedup_enrichment.sql` | `stg_jobs.fingerprint/canonical_job_id` + indexes; `staging.job_enrichment` |
| `dbt_project/models/marts/mart_job_feed.sql` (+ `sources.yml`, `schema.yml`) | Feed mart with indexes |
| `.github/workflows/etl_pipeline.yml` | Daily dedup → enrich (rules) → enrich (AI, continue-on-error) → feed mart |
| `etl/tests/test_geo.py`, `test_fingerprint.py`, `test_eligibility.py`, `test_attributes.py`, `test_dedup.py`, `test_enrich.py`, `test_gemini.py` | Tests |

Deliberately **not** added from §6.2: `apply_url` (= existing `redirect_url`), `ats` (= `source` for board jobs), `company_domain` (no source supplies it yet; Phase 1d's crawler can add it).

---

### Task 1: Place gazetteer (`enrich/geo.py`)

**Interfaces — Produces:** `Places(countries: frozenset[str], regions: frozenset[str], remote: bool)`; `parse_places(text: str, structured: bool = True) -> Places`; `merge(*places) -> Places`; `membership(places: Places, country: str) -> bool | None` (TRUE: a named country or a region that includes it; FALSE: every place excludes it; NULL: empty, or any "maybe" region). Region codes: `worldwide`, `apac`, `south_asia`, `emea`, `middle_east`, `europe`, `americas`, `north_america`, `latam`, `africa`, `oceania`.

Membership table: `worldwide`, `apac`, `south_asia` include pk and in; `emea` and `middle_east` are "maybe" for pk and exclude in; all other regions exclude both.

- [ ] **Step 1: Failing tests** (`etl/tests/test_geo.py`):
  - `test_parse_places_countries_and_cities`: "Remote - United States" → {us}; "San Francisco, CA" → {us}; "Toronto, ON" → {ca}; "Remote, Bangalore" → {in}, remote; "Lahore, Pakistan" → {pk}; "London, UK" → {gb}; "Remote Spain" → {es}; "Home based - Worldwide" → regions {worldwide}; "Remote, AMER" → {americas}; "EMEA" → {emea}; "Asia" → {apac}.
  - `test_parse_places_ambiguous_codes`: "Indianapolis, IN" → {us} (city) and no `in`; "Remote, IN" → no countries; "Remote, CA" → {us}; "Remote, US" → {us}; description mode (`structured=False`) ignores bare "US"/"IN"/"CA" codes but reads "U.S." and "United States".
  - `test_membership`: {us} → pk False; {worldwide} → True; {apac} → True; {emea} → pk None, in False; {us, in} → in True, pk False; empty → None.
- [ ] **Step 2: Run** `cd etl && ../venv/Scripts/python -m pytest tests/test_geo.py -v` → fail (module missing).
- [ ] **Step 3: Implement** a word-boundary alias table compiled once: country names/demonyms and major tech cities → ISO2 (US states by full name; two-letter state codes only after a comma in structured mode, excluding `IN`); region phrases (`anywhere|worldwide|global(ly)?|international` → worldwide, `apac|asia[- ]pacific|asia` → apac, `south asia` → south_asia, `emea`, `middle east|mena`, `europe|eu|european union` (timezone names such as CET are not places; they live in `attributes`), `americas|amer`, `north america|noram`, `latam|latin america|south america`, `africa`, `oceania|anz`). Case-sensitive short codes (`US`, `USA`, `UK`, `UAE`, `EU`) only in structured mode.
- [ ] **Step 4: Run** → pass. Commit `"Add place gazetteer for eligibility rules"`.

### Task 2: Fingerprints, canonical jobs (`enrich/fingerprint.py`, migration 013, `ops/dedup.py`)

**Interfaces — Consumes:** `parse_places`. **Produces:** `fingerprint(company, title, location_text) -> str` (`"<company>|<title>|<sorted countries+regions or ''>"`); `SOURCE_PRIORITY: dict[str, int]` (board systems 1, `careerpage` 2, default 3, `adzuna` 4); `ops.dedup.fill_fingerprints(conn, recompute=False) -> int`; `ops.dedup.assign_canonical(conn) -> int`; CLI `python -m ops.dedup [--recompute]`.

- [ ] **Step 1: Failing tests.** `test_fingerprint.py`:
  - `normalise_company`: "GitLab Inc." / "gitlab" / "GitLab, Inc" → "gitlab"; "Acme Technologies Ltd" → "acme technologies".
  - `normalise_title`: "Senior Backend Engineer (Remote)" / "Senior Backend Engineer - Remote, US" / "senior backend engineer" → "senior backend engineer"; "Sr. Data Engineer" → "senior data engineer"; seniority words are kept ("Data Engineer" ≠ "Senior Data Engineer").
  - `fingerprint` equal for "Remote - United States" and "United States"; different for "Remote - US" and "Remote - Canada".
  `test_dedup.py` (pipeline_db + migration 013):
  - `test_fill_fingerprints_only_new_rows` (second call returns 0; `--recompute` refills all).
  - `test_cross_source_duplicate_prefers_company_board`: greenhouse + himalayas + adzuna rows with the same fingerprint → all three get the greenhouse `job_id` as `canonical_job_id`.
  - `test_closed_jobs_do_not_win`: the greenhouse row is closed → the himalayas row becomes canonical.
  - `test_unique_jobs_are_their_own_canonical`.
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Migration 013** (applied before Task 5 too):
```sql
BEGIN;
ALTER TABLE staging.stg_jobs ADD COLUMN IF NOT EXISTS fingerprint TEXT;
ALTER TABLE staging.stg_jobs ADD COLUMN IF NOT EXISTS canonical_job_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_stg_jobs_fingerprint ON staging.stg_jobs (fingerprint);
CREATE TABLE IF NOT EXISTS staging.job_enrichment (
    job_id INTEGER PRIMARY KEY REFERENCES staging.stg_jobs(job_id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    rules_version INTEGER NOT NULL,
    remote_scope TEXT NOT NULL,            -- worldwide|regions|countries|hybrid|onsite|unclear
    eligible_countries TEXT[], eligible_regions TEXT[],
    eligible_pk BOOLEAN, eligible_in BOOLEAN, -- NULL = unclear
    eligibility_confidence NUMERIC(3,2),
    eligibility_evidence TEXT,
    seniority TEXT, min_years INTEGER, tz_overlap TEXT,
    salary_min_usd NUMERIC, salary_max_usd NUMERIC,
    method TEXT NOT NULL,                  -- rules|llm
    model TEXT,
    enriched_at TIMESTAMP NOT NULL DEFAULT now()
);
-- guarded REVOKE from anon/authenticated, as in 007/012
COMMIT;
```
  Add the same columns/table to `tests/fixtures/pipeline_schema.sql`'s test setup by running the migration file in the fixture (like 007).
- [ ] **Step 4: Implement** `fingerprint.py` (pure) and `ops/dedup.py`: `fill_fingerprints` reads `job_id, company_name, title, location_display, location_areas` for rows with `fingerprint IS NULL` (all rows with `recompute`), computes in Python, writes back with `execute_values` `UPDATE … FROM (VALUES …)`. `assign_canonical` runs one statement:
```sql
WITH ranked AS (
  SELECT s.job_id,
         first_value(s.job_id) OVER (PARTITION BY s.fingerprint ORDER BY
             CASE WHEN s.source IN ('greenhouse','lever','ashby','smartrecruiters') THEN 1
                  WHEN s.source = 'careerpage' THEN 2 WHEN s.source = 'adzuna' THEN 4 ELSE 3 END,
             r.last_seen_at DESC NULLS LAST, s.job_id) AS canon
  FROM staging.stg_jobs s JOIN raw.jobs r ON r.id = s.raw_job_id
  WHERE r.closed_at IS NULL AND s.fingerprint IS NOT NULL)
UPDATE staging.stg_jobs s SET canonical_job_id = ranked.canon
FROM ranked WHERE s.job_id = ranked.job_id AND s.canonical_job_id IS DISTINCT FROM ranked.canon;
```
  The SQL priority must match `SOURCE_PRIORITY` (a test asserts every key appears in the SQL).
- [ ] **Step 5: Run** → pass. Apply 013 to production. Run `python -m ops.dedup` and record rows fingerprinted and duplicate groups. Commit `"Fingerprint jobs and pick canonical listings"`.

### Task 3: Eligibility rules (`enrich/eligibility.py`)

**Interfaces — Consumes:** `parse_places`, `merge`, `membership`. **Produces:** `RULES_VERSION = 1`; `@dataclass Eligibility(remote_scope, eligible_countries: list[str], eligible_regions: list[str], eligible_pk: bool | None, eligible_in: bool | None, confidence: float, evidence: str, method: str = "rules")`; `classify(job: dict) -> Eligibility` where `job` has `title, description, location_display, location_areas, workplace_type, country_code`.

Decision order (first match wins):
1. `workplace_type` onsite/hybrid (or NULL with `country_code` pk/in, i.e. Adzuna/Jooble local jobs): scope = workplace (default onsite); TRUE only for the job's own country; confidence 0.9; evidence = location.
2. A **restriction sentence** in the description ("must be based/located/reside in X", "authorized/eligible to work in X", "X work authorization", "only open to candidates in X", "remote within X", "candidates based in X"): places = places named in the 80 characters after the trigger; membership decides; scope `countries`/`regions`; confidence 0.85; evidence = the sentence (≤ 300 chars). Several sentences → union of places.
3. A **worldwide sentence** ("work from anywhere", "anywhere in the world", "regardless of location", "hire globally/worldwide", "open to candidates worldwide") and the location fields name no specific country: scope `worldwide`, TRUE/TRUE, 0.8.
4. **Location fields** name countries/regions: membership decides, scope `countries`/`regions`, confidence 0.8 for countries / 0.7 for regions; evidence = the joined locations.
5. Location fields say only worldwide/anywhere/global (not just "Remote"): `worldwide`, TRUE/TRUE, 0.75.
6. Otherwise `unclear`, NULL/NULL, confidence 0.3, evidence "".

- [ ] **Step 1: Failing table test** `test_classify_cases` (≥ 16 rows) covering: "Remote - United States" → pk False/in False; "Remote, Bangalore" → in True/pk False; Himalayas `location_areas=["India","Pakistan"]` → True/True; "Worldwide" → True/True; "EMEA" → pk None/in False; "Asia" → True/True; onsite "Lahore, Pakistan" → pk True/in False; Adzuna in-country (workplace NULL, country `in`) → in True; bare "Remote" + no text → None/None `unclear`; bare "Remote" + "work from anywhere in the world" → True/True; "Worldwide" + "must be authorized to work in the US" → False (sentence beats location); "San Francisco" remote (Ashby `isRemote`) → us → False; "Remote, Canada; Remote, United States" → False; "Remote - India" + "Remote - Pakistan" → True/True; "You'll overlap with EST" alone → unclear (timezone is not a restriction). Plus `test_description_restriction_beats_bare_remote_location` and `test_evidence_is_a_sentence_from_the_text`.
- [ ] **Step 2: Run** → fail. **Step 3: Implement** (sentence split on `(?<=[.!?])\s+|\n+`; patterns compiled once, case-insensitive). **Step 4: Run** → pass.
- [ ] **Step 5:** Dry run on production: classify 500 open feed jobs in memory and print the distribution of (scope, pk, in) plus 20 random evidence strings; adjust patterns for obvious misses (each fix gets a table row). Commit `"Add rule-based eligibility tagging"`.

### Task 4: Seniority, years, timezone, salary (`enrich/attributes.py`)

**Interfaces — Produces:** `min_years(text) -> int | None` (smallest "N(+)? years" between 1 and 15 within 60 characters of "experience"; ranges "3-5 years" → 3); `seniority(title, years) -> str` (`intern|junior|mid|senior|lead`: title words first — intern/internship; junior/jr/entry/graduate/trainee; senior/sr; staff/principal/lead/head/director/architect/manager → lead — then years: <2 junior, 2–4 mid, ≥5 senior; default mid); `tz_overlap(text) -> str | None` (`americas|europe|apac` from "EST/PST/ET/PT/CST/US time zones/North American hours", "CET/GMT/UK/European hours", "IST/SGT/AEST/APAC hours" when near overlap/hours/time zone wording); `salary_from_text(text) -> tuple[float, float, str] | None` (annual ranges like "$120,000 - $150,000", "$120K–$150K", "USD 90,000 to 110,000"; ignores hourly/monthly and amounts < 10,000).

- [ ] **Step 1: Failing table tests** `test_attributes.py` (`test_min_years_cases`, `test_seniority_cases`, `test_tz_overlap_cases`, `test_salary_from_text_cases`), each 6–10 rows including negatives ("founded 10 years ago" → None; "$5 million funding" → None; "per hour" → None).
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass. Commit `"Extract seniority, years, timezone and salary"`.

### Task 5: Enrichment pass (`ops/enrich.py`, rules)

**Interfaces — Consumes:** `classify`, `RULES_VERSION`, `attributes.*`. **Produces:** `candidates(conn, limit=None, llm=False) -> list[dict]` (feed candidates needing enrichment, with `content_hash` computed in SQL as `md5(concat_ws('|', title, location_display, array_to_string(location_areas, ';'), description))`); `enrich_rules(conn, rates: dict[str, float]) -> dict` (counts); `upsert(conn, rows)`; CLI `python -m ops.enrich [--rules] [--llm] [--max-calls N] [--dedup]`.

Selection for the rules pass: open feed candidates with no enrichment row, or a different `content_hash`, or `method='rules' AND rules_version < RULES_VERSION`. Salary USD = structured `salary_min/max ÷ currency_rates.rate_to_usd` when present, else `salary_from_text` (USD only). Upsert `ON CONFLICT (job_id) DO UPDATE`, batches of 500.

- [ ] **Step 1: Failing tests** `test_enrich.py` (pipeline_db + 013, `staging.currency_rates` fixture table):
  - `test_rules_pass_enriches_open_feed_candidates_only` (closed job and Adzuna `gb` job are skipped).
  - `test_reenrich_only_when_content_or_rules_change` (second run → 0; change description → 1; bump `RULES_VERSION` via monkeypatch → rules rows redone, an `llm` row with unchanged hash untouched).
  - `test_salary_converted_to_usd` (INR structured salary ÷ rate; description "$120K - $150K" when no structured salary).
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass.
- [ ] **Step 5:** Production: `python -m ops.enrich --dedup --rules`; record counts by scope and pk/in label. Commit `"Enrich feed jobs with rule-based labels"`.

### Task 6: Gemini fallback (`enrich/gemini.py`, `ops.enrich --llm`)

**Interfaces — Produces:** `GeminiClient(api_key, model, post=requests.post, sleep=time.sleep, min_interval=6.5)`, `.label(jobs: list[dict]) -> dict[int, Eligibility]` (raises `QuotaExhausted` after 3 consecutive 429s); `build_prompt(jobs) -> str` (per job: id, title, company, locations and only the description sentences that mention places, remote, location, based, reside, authoriz, visa, time zone, anywhere, worldwide, country — max 1,500 characters; else the first 600 characters); `parse_labels(text, jobs) -> dict[int, Eligibility]`; `enrich_llm(conn, client, max_calls) -> dict`.

LLM candidates: canonical, open feed jobs whose enrichment row has `method='rules'` and (`eligible_pk IS NULL OR eligible_in IS NULL`), oldest first. Response labels map `yes/no/unclear` → `True/False/None`, confidence 0.8 for yes/no; `method='llm'`, `model` stored. An evidence string that isn't a (whitespace/case-normalised) substring of the job's text → that job's labels become `None`.

- [ ] **Step 1: Failing tests** `test_gemini.py` with a fake `post` returning recorded-shape responses (`{"candidates":[{"content":{"parts":[{"text": "<json>"}]}}]}`):
  - `test_build_prompt_keeps_location_sentences_only`
  - `test_parse_labels_maps_answers`
  - `test_llm_evidence_must_be_quoted`
  - `test_llm_bad_json_keeps_rules_label` (DB: rules row unchanged; run continues to the next batch)
  - `test_llm_quota_stops_cleanly` (three 429s → `QuotaExhausted` → `enrich_llm` returns `{"stopped": "quota", …}`)
  - `test_no_api_key_is_a_clean_skip` (CLI `--llm` without `GEMINI_API_KEY` exits 0 and prints the notice)
  - `test_api_key_goes_in_header_not_url`
- [ ] **Step 2: Run** → fail. **Step 3: Implement** (REST `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`, `generationConfig.responseMimeType = "application/json"` with a `responseSchema`, temperature 0). **Step 4: Run** → pass. Commit `"Add Gemini fallback for unclear eligibility"`.

### Task 7: Feed mart + daily CI

**Interfaces — Consumes:** `staging.job_enrichment`, `stg_jobs.canonical_job_id`, `raw.jobs.closed_at/first_seen_at/last_seen_at`. **Produces:** `staging_marts.mart_job_feed(job_id, title, company_name, search_role, source, workplace_type, country_code, location_display, apply_url, job_posted_at, first_seen_at, last_seen_at, remote_scope, eligible_pk, eligible_in, eligible_countries, eligible_regions, eligibility_confidence, eligibility_evidence, eligibility_method, seniority, min_years, tz_overlap, salary_min_usd, salary_max_usd, skills text[])`, indexed on `search_role`, `(eligible_pk, eligible_in)`, `first_seen_at`.

- [ ] **Step 1:** Add `job_enrichment` to `sources.yml` (staging) and `raw.jobs` lifecycle columns; write `mart_job_feed.sql` (table, `post_hook` indexes); add `schema.yml` tests (`job_id` unique + not_null; `remote_scope` accepted values).
- [ ] **Step 2:** `dbt run --target dev --select mart_job_feed` and `dbt test --select mart_job_feed` on production → pass; record the row count by role and eligibility.
- [ ] **Step 3:** CI (`etl_pipeline.yml`), after transform and before the marts guard:
  - `enrich` step: `python -m ops.run_step --step enrich -- python -m ops.enrich --dedup --rules`
  - `enrich_llm` step, `continue-on-error: true`, env `GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}`: `python -m ops.enrich --llm --max-calls 150`
  - `feed` step (not behind the marts guard): `dbt run --select mart_job_feed`
  - add the three steps to the notify results. Run actionlint → clean.
- [ ] **Step 4:** Commit `"Build daily job feed mart"`.

### Task 8: Volume, hand check, close-out

- [ ] **Step 1: Grow the board registry** to reach ≥ 5,000 open remote jobs: extend `etl/config/ats_seed_companies.json` with more remote-friendly employers per system, `python -m ops.companies seed && python -m ops.companies validate`, then a full `python ingest_sources.py` (all sources: refreshes the remote boards and closes stale feed jobs), `transformer.py --batch-size 500 --fast-only`, `ops.enrich --dedup --rules`, feed mart. Record counts.
- [ ] **Step 2: Hand check.** `python -m ops.eligibility_sample --n 50 --out docs/ops/eligibility-check-2026-10.md` (stratified across labels; prints title, company, locations, label, evidence, and the description's location sentences). Label each job by reading the posting; record per-job verdicts and accuracy (overall, and precision of `eligible_pk = TRUE`) in that file. Below 90% → fix the rules (new table rows in Task 3's test), re-run, re-check.
- [ ] **Step 3:** PROGRESS.md (§1, Phase 1c section, snapshot), CLAUDE.md (architecture: enrichment, feed mart, CI steps; roadmap status), memory. Commit `"Record Phase 1c results"`.

## Self-review notes

- Spec §6.2: fingerprint + canonical (T2), `job_enrichment` with every listed field (T2 migration, T3–T6), `mart_job_feed` with role/eligibility/first-seen indexes (T7). `apply_url`/`ats`/`company_domain` intentionally mapped to existing columns (see File Structure).
- Spec §6.3: rules on location fields and phrases (T1, T3), Gemini for undecided jobs in batches of 20 with JSON output and evidence (T6), confidence + unclear state (T3, T6).
- Spec §4 exit criteria: ≥ 5,000 open deduplicated tagged remote jobs and the ≥ 90% hand check (T8).
- Names are consistent across tasks: `parse_places`, `membership`, `fingerprint`, `classify`, `RULES_VERSION`, `Eligibility`, `enrich_rules`, `enrich_llm`, `GeminiClient.label`, `QuotaExhausted`.
