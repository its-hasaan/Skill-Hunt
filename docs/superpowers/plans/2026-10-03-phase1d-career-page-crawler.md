# Phase 1d: Career-Page Crawler — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read jobs straight from company career pages that publish `schema.org/JobPosting` JSON-LD, and grow the company job-board registry whenever a career page turns out to embed Greenhouse, Lever, Ashby, SmartRecruiters or Workable.

**Architecture:**
- A new `ops.career_sites` registry (domain, careers URL, status, crawl bookkeeping) is filled from a hand-picked seed file.
- Pure, fixture-tested helpers in `etl/careers/`: robots.txt policy, ATS-embed detection, job-link discovery, JSON-LD extraction and mapping into the existing ATS field shape.
- `CareerPageConnector` reuses `AtsConnector` (thread pool across sites, role + location filters, `seen_boards`), with one site as one "board". It runs inside the normal daily ingest as source `careerpage`.

**Tech Stack:** Python 3.11, requests, `urllib.robotparser`, `html.parser` (stdlib), psycopg2, pytest.

**Spec:** `docs/superpowers/specs/2026-09-30-jobwise-product-roadmap-design.md` §6.1 (company career-page crawler), §11 (non-goals: no headless browser, no evasion).

## Global Constraints

- robots.txt is **required**: if it can't be read (network error, 5xx, challenge page), the site is skipped this run. A 404 means no rules (everything allowed). Every page fetch is checked against it for user agent `JobwiseBot`.
- User agent `JobwiseBot/1.0 (+https://github.com/its-hasaan; job-market research)`, ≥ 2 s between requests to the same site, ≤ `page_budget` pages per site per run (default 25), 4 sites in parallel, conditional GET (ETag / Last-Modified) on the careers page.
- An embedded hiring-system board wins: the site gets `status='ats'`, the board is added to `ops.companies` (`discovered_via='careerpage'`) and no pages are scraped (the ATS connector reads it after validation).
- JavaScript-only pages are skipped (no JSON-LD and no links → `status='empty'`). No headless browser.
- Jobs keep the existing filters: tracked role by title, remote anywhere or located in Pakistan/India. `job_platform_id = careerpage:<domain>:<id>`, id = JobPosting `identifier.value` or the first 16 hex chars of sha1(url).
- Closing: a site counts as fully fetched (`seen_boards`) only when its crawl stayed under the page budget; otherwise its jobs age out after 14 days like other feeds.
- `careerpage` ranks 2 in duplicate removal (already wired in `enrich.fingerprint.SOURCE_PRIORITY` and `ops.dedup`).
- Git: commit + push per task when tests pass; 5–8 word messages; no Claude attribution.

## Review Focus

1. **robots.txt disallows the careers path** (`Disallow: /careers`). Expected: nothing under it is fetched; site status `blocked`. Test: Task 1 `test_robots_blocks_disallowed_paths`.
2. **robots.txt is a Cloudflare challenge or times out.** Expected: site skipped (no page fetched), `fail_count` + 1. Test: Task 3 `test_unreadable_robots_skips_site`.
3. **JSON-LD wrapped in `@graph`, a list, or with HTML-escaped description.** Expected: every JobPosting found; plain-text description. Test: Task 1 `test_extract_jobpostings_shapes`.
4. **`jobLocationType: TELECOMMUTE` with `applicantLocationRequirements: [{"name": "India"}]`.** Expected: remote, locations include India → bucket `in`. Test: Task 1 `test_map_jobposting_remote_with_applicant_countries`.
5. **Careers page embeds `boards.greenhouse.io/embed/job_board?for=acme`.** Expected: `ops.companies` gets (greenhouse, acme); no job pages fetched. Test: Task 3 `test_embedded_board_is_registered_not_scraped`.

---

## File Structure

| File | Responsibility |
|---|---|
| `database/migrations/014_career_sites.sql` | `ops.career_sites` |
| `etl/careers/__init__.py` | Package marker |
| `etl/careers/robots.py` | `RobotsPolicy.from_response(status, text)`, `.allowed(url)` |
| `etl/careers/html_links.py` | `extract_links(html, base_url) -> list[str]`, `ats_boards(html, base_url) -> dict[str, set[str]]`, `job_links(links, domain, limit) -> list[str]` |
| `etl/careers/jsonld.py` | `extract_jobpostings(html) -> list[dict]`, `map_jobposting(item, page_url) -> dict | None` |
| `etl/connectors/careerpage.py` | `CareerPageConnector(AtsConnector)`: sites as boards, polite per-site crawl |
| `etl/ops/career_sites.py` | Registry access (`sites_to_crawl`, `record_crawl`) + CLI `seed` / `status` |
| `etl/config/career_sites_seed.json` | Hand-picked career pages (remote-first employers, Pakistan/India tech companies) |
| `etl/config/sources_config.json`, `etl/connectors/__init__.py` | Register + enable `careerpage` |
| `etl/tests/test_careers.py`, `etl/tests/test_careerpage_connector.py`, `etl/tests/fixtures/careers/*.html` | Tests |

---

### Task 1: Pure helpers (robots, links, JSON-LD)

**Interfaces — Produces:** `RobotsPolicy.from_response(status: int | None, text: str) -> RobotsPolicy | None` (None = unreadable); `RobotsPolicy.allowed(url) -> bool`; `extract_links(html, base_url) -> list[str]` (absolute `href`/`src` URLs); `ats_boards(html, base_url) -> dict[str, set[str]]` (via `ops.discover_companies.extract_tokens`, plus the Greenhouse embed `for=` parameter); `job_links(links, domain, limit) -> list[str]` (same domain, path matches `/(jobs?|careers?|positions?|openings?|vacanc(y|ies)|opportunit(y|ies))/[^/]+`, de-duplicated, ≤ limit); `extract_jobpostings(html) -> list[dict]` (every `@type` JobPosting in `application/ld+json`, through lists and `@graph`; bad JSON skipped); `map_jobposting(item, page_url) -> dict | None` in the ATS `map_job` field shape (`id, title, company_name, description, redirect_url, location_display, location_areas, locations, workplace_hint, remote_flag, contract_type, contract_time, salary_min, salary_max, salary_currency, job_posted_at, raw`).

- [ ] **Step 1: Failing tests** (`test_careers.py`, fixtures `careers/jsonld_graph.html`, `careers/jsonld_list.html`, `careers/greenhouse_embed.html`, `careers/links.html`):
  - `test_robots_blocks_disallowed_paths`, `test_robots_404_allows_all`, `test_robots_unreadable_is_none` (status None / 503 / an HTML challenge body).
  - `test_ats_boards_finds_links_and_embeds`.
  - `test_job_links_same_domain_only_and_limited`.
  - `test_extract_jobpostings_shapes` (`@graph`, top-level list, single object, broken JSON block ignored).
  - `test_map_jobposting_remote_with_applicant_countries`, `test_map_jobposting_onsite_address`, `test_map_jobposting_salary_and_dates`.
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass. Commit `"Add career page parsing helpers"`.

### Task 2: Registry (`ops.career_sites`)

**Interfaces — Produces:** table `ops.career_sites(id, domain UNIQUE, careers_url, status, ats, board_token, jobs_found, fail_count, last_crawled_at, etag, last_modified, discovered_via, created_at)`; `seed(conn, path) -> int`; `sites_to_crawl(conn, limit) -> list[dict]` (status in candidate/jsonld/empty, `fail_count < 3`, least recently crawled first); `record_crawl(conn, domain, status, jobs_found=None, etag=None, last_modified=None, ats=None, board_token=None, failed=False)`; CLI `python -m ops.career_sites seed|status`.

- [ ] **Step 1: Failing tests** (`test_careerpage_connector.py` DB part): `test_seed_is_idempotent`, `test_sites_to_crawl_skips_ats_blocked_and_failing`, `test_record_crawl_counts_failures`.
- [ ] **Step 2: Run** → fail. **Step 3:** migration 014 (idempotent, guarded REVOKE as 012), `ops/career_sites.py`, seed file. **Step 4: Run** → pass. Apply 014; `python -m ops.career_sites seed`. Commit `"Add career site registry"`.

### Task 3: Connector

**Interfaces — Consumes:** Task 1 + 2, `AtsConnector`, `ops.companies.upsert_candidates`. **Produces:** `CareerPageConnector` (`name = "careerpage"`), config `{page_budget, delay_seconds, max_sites, concurrency}`; test seams `config["sites"]` (list of dicts) and `config["fetch"]` (callable `(url, headers) -> (status, text, headers)`), `config["record"]`, `config["register_board"]`.

Per site: robots → careers page (conditional GET) → ATS embed? register + `status='ats'` → else JSON-LD on the careers page + up to `page_budget - 1` job pages (each robots-checked, `delay_seconds` apart) → `status='jsonld'` (jobs found) or `'empty'`. A site joins `seen_boards` only when the crawl wasn't cut by the budget.

- [ ] **Step 1: Failing tests:** `test_unreadable_robots_skips_site`, `test_embedded_board_is_registered_not_scraped`, `test_jsonld_jobs_are_filtered_and_namespaced` (tracked remote role kept as `careerpage:<domain>:<id>`, onsite New York job dropped), `test_budget_cut_site_is_not_fully_seen`, `test_not_modified_careers_page_records_and_skips`.
- [ ] **Step 2: Run** → fail. **Step 3: Implement** + registry + `sources_config.json` block (`enabled: true, page_budget: 25, delay_seconds: 2, max_sites: 200, concurrency: 4`). **Step 4: Run** → pass. **Step 5:** production: `python ingest_sources.py --source careerpage --dry-run`, then the real run, transform, enrich; record sites by status, boards registered, jobs kept. Commit `"Add career page crawler connector"`.

### Task 4: Docs

- [ ] PROGRESS.md (Phase 1d section, §1), CLAUDE.md (architecture line, roadmap row). Commit `"Record Phase 1d results"`.

## Self-review notes

- Spec §6.1 steps 1–5 map to: robots required (T1, T3), embedded hiring system first and registry growth (T1 `ats_boards`, T3), JSON-LD from job pages (T1, T3), JS-only skipped (T3 `empty`), named UA + page budget + conditional GET + delay (Global Constraints, T3).
- Names consistent: `RobotsPolicy`, `ats_boards`, `job_links`, `extract_jobpostings`, `map_jobposting`, `sites_to_crawl`, `record_crawl`, `CareerPageConnector`.
