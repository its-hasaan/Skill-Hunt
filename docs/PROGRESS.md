# Jobwise — Progress Log

**Purpose:** a running record so any new chat can pick up exactly where the last one stopped. `CLAUDE.md` holds the conventions and a short status; this file holds the detail.

**Update rule (every session):**
1. After each finished task, update §1 (where we are) and the phase's section, and commit the change with the feature.
2. Before ending a session, make sure §1 "Next actions" is accurate.

_Last updated: 2026-10-01 (end of session 1)._

---

## 1. Where we are right now

**Current phase:** Phase 1b (company job-board connectors). Its code is done and pushed; three follow-ups remain (below).

**Next actions, in order:**
1. **Finish the transform backlog.** 1,792 jobs are in `raw.jobs` but not yet in staging. They come from the first company-board ingest; 454 of those jobs (plus 46 Himalayas) were done before the run was stopped.
   - Why it's slow: `transformer.py` writes row by row, about 13 min per 500 jobs now that descriptions are full length.
   - Recommended fix first: implement batched writes (PIPELINE_REVIEW.md Part 2 #12): insert jobs with `execute_values … RETURNING job_id, raw_job_id`, then bulk-insert skills.
   - Then run: `cd etl && SUPABASE_URL=<session pooler 5432 URL> ../venv/Scripts/python transformer.py --batch-size 500 --fast-only`. If it runs as a background task, give it a 2-hour timeout; the default background limit is 60 min.
   - The last run (2026-10-01) died at 09:59 local time with `server closed the connection unexpectedly`, followed by a DNS failure (a local network blip). The transformer has **no reconnect**: one dropped connection ends the whole run. Re-running is safe, because it only picks up jobs not yet in staging. While adding batched writes, also add a reconnect-and-continue on `psycopg2.OperationalError` per batch.
2. **Common Crawl retries.** `ops/discover_companies.crawl` gives up on a host after one failed page. The CDX index often answers 503/504, so the first production run found only Lever boards (27 tokens, 26 new). Add retries with backoff to `http_fetch(url, attempts=3, get=requests.get, sleep=time.sleep)`, test first:
   - 504 → 503 → 200 returns the body after 2 waits.
   - All 504s return `None`.
   Then re-run `python -m ops.discover_companies --max-pages 3 --validate-limit 300`.
3. **Close out Phase 1b:**
   - Final self-review of the 1b diff (`git diff 1989171..HEAD`), against the "Review Focus" in `docs/superpowers/plans/2026-10-01-phase1b-company-job-boards.md`.
   - Then mark Phase 1b done here and in CLAUDE.md.
   - The local, git-ignored ledger `.superpowers/sdd/2026-10-01-phase1b-company-job-boards/progress.md` holds the task-level notes; delete it when 1b is closed.
4. **Phase 1c plan** (write the plan with the writing-plans skill, then execute):
   - Duplicate removal (fingerprint of company + title + location → `canonical_job_id`, with company-board listings preferred).
   - `staging.job_enrichment`: eligibility via rules first, then Gemini Flash for unclear cases. **This needs the owner's free Gemini API key.**
   - Seniority, timezone overlap, USD salary.
   - The `mart_job_feed` dbt model (open, deduplicated, enriched jobs).
   - Spec: §6.2–6.3.
5. **Phase 1d:** the JSON-LD career-page crawler (spec §6.1). It also feeds `ops.companies` when it finds embedded Greenhouse/Lever/Ashby boards.
6. Then **Phase 2** (web copilot → free beta).

**Blocked on the owner** (none of these block coding):
- Fix the `SUPABASE_URL` GitHub secret. Until then, every CI pipeline run fails at preflight, which is by design.
- Resend account, first `adzuna=true` run, Cloudflare Worker deploy, repo private, Adzuna email.
- Free Gemini + Groq keys (Gemini is needed for Phase 1c).
- Final product name and domain.
- Full list in CLAUDE.md → "Pending manual steps".

---

## 2. Roadmap status

| Phase | What | Status |
|---|---|---|
| Planning | Spec + 14 owner decisions: `docs/superpowers/specs/2026-09-30-jobwise-product-roadmap-design.md` | ✅ done |
| 0 | Foundation fixes | ✅ code done — waiting on owner manual steps |
| 1a | Roles & skill quality | ✅ done (live in production) |
| 1b | Company job-board connectors | 🟡 code done — 3 follow-ups (§1 items 1–3) |
| 1c | Duplicate removal + eligibility + feed mart | ⏳ next (needs Gemini key) |
| 1d | Career-page crawler (JSON-LD) | ⏳ |
| 2 | Web copilot → free beta | ⏳ |
| 3 | Extension 2.0 | ⏳ |
| 4 | AI assistance + Pro + Paddle → paid launch | ⏳ |
| 5 | Growth | ⏳ |

Plans live in `docs/superpowers/plans/`, one per phase or sub-phase.

---

## 3. Phase 0: Foundation fixes (plan `2026-09-30-phase0-foundation-fixes.md`)

**Built** (commits `b7eefb6` … `cf72016`). The `etl/ops/` package:

| Module | What it does |
|---|---|
| `dbconfig` | Derives every connection setting from `SUPABASE_URL` |
| `preflight` | Checks credentials and connectivity, and says which secret to fix |
| `migrate` | Versioned migrations, tracked in `ops.schema_migrations` |
| `ledger` + `run_step` | Records every pipeline step in `ops.pipeline_runs`; captured output is redacted of secrets |
| `retention` | 400-day window; strips raw payloads 7 days after processing |
| `marts_guard` | Skips the dbt rebuild when the 60-day window holds fewer than 1,000 jobs |
| `archive` | Calls `archive_skill_demand()` |
| `notify` | Resend failure email |

Also built:
- `.github/workflows/etl_pipeline.yml`: one daily job. Adzuna runs on Mondays; each source is independent; every step is logged; ends with a summary email.
- `migrate.yml` (applies migrations on push) and `tests.yml` (pytest with a Postgres service).
- `infra/keepwarm/`: a Cloudflare Worker cron (built and validated, **not deployed**).
- Resume uploads no longer store dead public URLs.

**Root cause found:** the scheduled ETL failed on every run from January to September 2026 because the `SUPABASE_URL` GitHub secret doesn't work. The same preflight check passes locally with `etl/.env`.

**Production changes made with the owner's approval:**
- Migrations 001–005 recorded as already applied; 006 applied (20 anonymous resume rows plus their 16 files deleted); 007 and 008 applied.

**Owner decisions:**
- Run 006 and delete the files.
- Retention: 400 days plus payload stripping, instead of 120 days, because the skill-trend chart reads `stg_jobs`.

**Deferred minor issues:**
- `tests.yml` runs on every push (about 1.5 CI minutes each).
- Local-run row counts in the step log can be off by the UTC offset.
- The `resumes` bucket has 4 old files with no database row (left in place).

## 4. Phase 1a: Roles & skill quality (plan `2026-10-01-phase1a-roles-and-skills.md`)

**Built** (commits `3aab9f7` … `e990fc7`):
- `etl/skill_patterns.py`: the **one** skill matcher, used by the ETL and the API.
  - Supports case-sensitive terms and `not_followed_by`/`not_preceded_by` guards.
  - A substring pre-check makes it 20× faster.
- The taxonomy curated from 487 to 338 skills by `etl/tools/curate_taxonomy_2026_10.py`.
  - Junk discovered entries and dangerous aliases (`next`, `express`, `image`, `ge`, `less`…) removed.
  - About 80 skills added for the new roles.
  - Lint tests in `etl/tests/test_taxonomy.py`.
- **20 roles** (adds Software Engineer, QA Engineer, UI/UX Designer, Product Manager, Technical Support Engineer). `adzuna_roles` keeps Adzuna at 15.
- For Adzuna and Jooble the title decides the role; titles that match no tracked role get `raw.jobs.skip_reason='role_mismatch'`.
- `ops/reextract.py`: re-applies roles and skills to stored jobs.
- `render.yaml` `buildFilter`: the API redeploys when the taxonomy or matcher changes.

**Production results:**
- 9,999 off-role jobs dropped (reversible: the raw rows remain, marked with `skip_reason`); about 9,900 re-tagged; 59,545 jobs re-extracted; 252 junk skills removed.
- "Go" dropped from 1,240 to 551 jobs, "R" from 1,336 to 310, "Excel" from 360 to 242.
- Live API verified: it recognises Figma, and "go further" no longer counts as Go.
- Migrations 009 (new roles) and 010 (`skip_reason`) applied.

**Deferred minor issues:**
- The AI Engineer title pattern can over-capture titles like "AI Data Engineer".
- The `render.yaml` `buildFilter` only applies if the Render service is blueprint-synced.

## 5. Phase 1b: Company job-board connectors (plan `2026-10-01-phase1b-company-job-boards.md`)

**Built** (commits `1989171` … `6c0c413`):
- **Job lifecycle:** `raw.jobs.first_seen_at/last_seen_at/closed_at` (migration 011) and `ops/lifecycle.py`.
  - Ingest upserts and records each sighting; duplicate keys are collapsed.
  - Jobs missing from a fully fetched company board are closed.
  - Feed sources close after 14 days unseen.
  - `stg_jobs.workplace_type`.
- **Company registry:** `ops.companies` (migration 012) and `ops/companies.py`, with the `seed` and `validate` commands.
  - SmartRecruiters returns 200 with an empty list for unknown companies, so the validator counts those as missing.
- **Location logic:** `connectors/location.classify_location`. Keeps remote jobs anywhere, plus Pakistan/India onsite or hybrid; buckets each as `remote`/`pk`/`in`.
- **Connectors:** `connectors/{greenhouse,lever,ashby,smartrecruiters}.py` on `ats_base.AtsConnector` (4 concurrent requests). Each `map_job` is pure and tested against real samples in `etl/tests/fixtures/ats/`.
- **Discovery:** `ops/discover_companies.py` (Common Crawl CDX), run weekly in CI on Mondays.

**Production results:**
- 99 active boards: Greenhouse 40, Lever 32, Ashby 20, SmartRecruiters 7.
- First run: 77 boards, 15,639 jobs scanned, **2,246 relevant jobs ingested with full descriptions**.
- 454 of those transformed so far (see §1 item 1).
- A real-run check caught a silent bug: Himalayas lists jobs twice, which made the upsert fail and drop the whole batch. Fixed.

**Not done:** Workable (its public endpoints return 404); a Common Crawl retry (§1 item 2).

---

## 6. Production snapshot (2026-10-01)

- **Supabase:** about 241 MB of 500 MB. Migrations 001–012 applied (check with `cd etl && ../venv/Scripts/python -m ops.migrate status`).
  - `staging.stg_jobs` about 60k rows (Adzuna-heavy, data through July 2026 plus the new company-board jobs).
  - The marts are **still the July build**: the marts guard blocks rebuilds until a run with `adzuna=true` lands fresh data.
- **CI:** the Tests workflow is green. The ETL and migration workflows fail at preflight until the owner fixes the `SUPABASE_URL` secret.
- **API (Render)** runs the new taxonomy. The frontend is on Vercel, which will move to Cloudflare Pages in Phase 2.

## 7. Lessons for future sessions (practical)

- **Shell heredocs collapse `\\` to `\`.** Writing regexes or code with backslashes through `python - <<'EOF'` turned `\b` into a backspace byte, twice. Use the Write/Edit tools or a script file for any code with backslashes.
- **Background tasks stop at their timeout** (default 60 min). Set a 2-hour timeout for long backfills and print progress with `flush=True`.
- **Always run a real production check after a feature.** Two silent bugs were found this way: the duplicate-key upsert and the stale Render deploy.
- The Common Crawl CDX `showNumPages` query times out, but paging with `page=N` works (slowly, with occasional 503/504).
- Supabase's transaction pooler (6543) drops long connections, so long jobs use 5432 (`ops.dbconfig.session_pooler_url`).
- ETL tests need Docker Desktop running.
