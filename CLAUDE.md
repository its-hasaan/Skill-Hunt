# Jobwise (formerly Skill Hunt / Job Script)

Long-term context for this repo. Keep it current: update "Roadmap status" and "Pending manual steps" whenever a feature lands.

## Session protocol (every chat)

1. **Start:** read [docs/HANDOVER.md](docs/HANDOVER.md) (scope + autonomy rules), then [docs/PROGRESS.md](docs/PROGRESS.md). Its §1 "Where we are right now" lists the exact next actions. Then read the current phase's plan in `docs/superpowers/plans/`.
2. **While working:** after each finished task, update `docs/PROGRESS.md` (§1 and the phase section) and the status table below, and commit them together with the feature (git rules under Conventions).
3. **Before stopping:** make sure PROGRESS.md §1 "Next actions" is accurate and nothing is left uncommitted, half-written, or failing on `main`.

## Current focus (keep in sync with docs/PROGRESS.md §1)

Phase 1b follow-ups, then Phase 1c:
1. Transform backlog of 1,792 company-board jobs; implement batched transformer writes first (PIPELINE_REVIEW Part 2 #12).
2. Common Crawl retry/backoff in `ops/discover_companies.http_fetch`.
3. Phase 1b self-review and close-out.
4. Write the Phase 1c plan (duplicate removal + eligibility tagging + `mart_job_feed`; needs the owner's Gemini key).

## Product

A **remote job copilot for South Asian (Pakistan/India) tech professionals** looking for international remote jobs. It gives users a daily feed of remote jobs they are actually eligible for from their country, a match score explained with real market data (skill demand, salary premium), AI help with applications, an application tracker, and a Chrome extension on job sites. The market analytics are the free way people discover the product.

- Working name **Jobwise**. Final name, trademark and domain are still open (jobwise.ai already exists).
- Business model: B2C freemium. Pro costs $12/mo standard, $5/mo in lower-income countries such as Pakistan/India/Bangladesh; there is also a 3-month pass. Payments go through Paddle behind a provider-agnostic billing layer.
- Principles: user-controlled automation only (no auto-submit bots, no LinkedIn Easy Apply autofill); only data sources we may legally use; $0 infrastructure until there is revenue.

**Source of truth for the plan:** [docs/superpowers/specs/2026-09-30-jobwise-product-roadmap-design.md](docs/superpowers/specs/2026-09-30-jobwise-product-roadmap-design.md). Its §2 decisions log records every product decision. **How the current code works:** [PLATFORM_OVERVIEW.md](PLATFORM_OVERVIEW.md).

## Roadmap status

| Phase | Scope | Status |
|---|---|---|
| 0 | Foundation fixes: CI ETL repair, daily schedule, run ledger + failure email, storage retention, private resumes, migration runner, keep-warm on Cloudflare | **Code done; waiting on owner's manual steps below** |
| 1 | Remote job data engine: 1a roles & skill quality → 1b company job-board connectors → 1c dedup + eligibility + feed mart → 1d career-page crawler | **1a done** (20 roles, curated taxonomy 487→338, shared matcher with 20× prefilter, prod backfill: 9,999 off-role jobs dropped, Go/R false positives −56%/−77%); **1b code done, 3 follow-ups open** (company job boards: Greenhouse/Lever/Ashby/SmartRecruiters, job lifecycle, `ops.companies` registry + Common Crawl discovery; 99 active boards, 2,246 jobs ingested); 1c next. Details: docs/PROGRESS.md |
| 2 | Web copilot core → free beta | Not started |
| 3 | Extension 2.0 | Not started |
| 4 | AI assistance + Pro + Paddle → paid launch | Not started |
| 5 | Growth (SEO pages, referrals, reports) | Not started |

## Architecture (short)

`sources → etl/ (Python) → Supabase Postgres (raw → staging → staging_marts via dbt) → backend/ (FastAPI on Render) → frontend/ (React+Vite) + skillhunt-extension/ (MV3, gitignored)`

- **ETL:** `etl/extractor.py` (Adzuna), `etl/ingest_sources.py` + `etl/connectors/*` (every source outputs `NormalizedJob`), `etl/transformer.py` (skills via the taxonomy regex), `etl/fetch_currency_rates.py`, `etl/refresh_all.py` (local full refresh). Config lives in `etl/config/*.json`.
- **Skills:** `etl/skill_patterns.py` is the ONE skill matcher, used by the ETL (`FastPathExtractor`, transformer fallback) and the API (`ResumeSkillExtractor` imports it via `sys.path`). Taxonomy entries can carry `case_sensitive`, `not_followed_by`, `not_preceded_by` for terms that are also English words ("Go", "REST", "Spark"). `etl/tests/test_taxonomy.py` lints the taxonomy (no term owned by two skills, English words only case-sensitive, false-positive sentences don't match).
- **Roles:** 20 roles in `etl/connectors/utils.py` (`_ROLE_PATTERNS`, order matters, `Software Engineer` is the catch-all and must stay last). `extraction_config.json` has `roles` (20) and `adzuna_roles` (15, quota). For keyword-searched sources (Adzuna, Jooble) the TITLE decides the role (`transformer.validated_role`); titles matching no role get `raw.jobs.skip_reason='role_mismatch'`.
- **Company job boards (Phase 1b):** `etl/connectors/{greenhouse,lever,ashby,smartrecruiters}.py` on a shared `ats_base.AtsConnector` (4 concurrent requests, per-thread sessions). Each module's `map_job` is pure and tested against real samples in `etl/tests/fixtures/ats/`. Endpoints live in `connectors/ats_endpoints.py`. Boards come from `ops.companies` (seed `etl/config/ats_seed_companies.json` → `python -m ops.companies seed && python -m ops.companies validate`; Common Crawl → `python -m ops.discover_companies`, weekly in CI). Only tracked roles that are remote or in PK/IN are kept (`connectors/location.classify_location`). Workable is deferred (its public endpoints 404).
- **Job lifecycle:** `raw.jobs.first_seen_at/last_seen_at/closed_at`. Ingest upserts (`ops.lifecycle.save_jobs`, duplicate keys collapsed). Jobs missing from a fully fetched company board are closed; feed/search sources close after 14 days unseen. `stg_jobs.workplace_type` = remote|hybrid|onsite.
- **dbt:** `dbt_project/` builds `staging_marts.mart_*`, which is what the API reads.
- **Backend:** `backend/app/routers/*` (stats, skills, salary, companies, career, resume, user, extension). Auth is Supabase JWT (`app/auth.py`). Rate limiting is in `app/ratelimit.py`.
- **DB schemas:** `raw`, `staging`, `staging_marts`, `archive`, `public` (user tables, RLS), `ops` (pipeline ops, from Phase 0).
- **Pipeline ops (`etl/ops/`):** `dbconfig` (derives everything from `SUPABASE_URL`), `preflight` (credentials check that names the fix), `migrate` (versioned migrations), `ledger` + `run_step` (every step recorded in `ops.pipeline_runs`), `retention` (400-day window; strips raw payloads after processing), `marts_guard` (skips the dbt rebuild when fewer than 1,000 jobs fall in the 60-day window, so a thin run can't empty the dashboard), `archive`, `notify` (Resend failure email; failure output is redacted of secret env values first). CLIs: `python -m ops.<name>` from `etl/`. They read `etl/.env` only when run as a CLI, never on import.
- **CI:** `.github/workflows/etl_pipeline.yml` is **one daily job**: Adzuna on Mondays, other sources daily, preflight first, each source independent, and a summary/alert at the end. `migrate.yml` applies new migrations on push. `tests.yml` runs pytest against a Postgres service.
- **Keep-warm:** Cloudflare Worker in `infra/keepwarm/` (cron every 10 min → `/health`).
- **DB `ops` schema:** `schema_migrations` (runner bookkeeping; 001–005 baselined, 006–008 applied), `pipeline_runs` (step ledger).

## Conventions

- **Git:** commit and push small, *tested* increments straight to `main`. Messages are 5–8 words on a single line. **Never add Claude as co-author or collaborator** (no `Co-Authored-By`, no "Generated with" lines). Use a branch only for work that isn't working yet. Stage only the files you touched.
- **Data sources:** use a real user agent, respect robots.txt, back off on 429. No proxy rotation, fingerprint spoofing, CAPTCHA solving, or scraping of LinkedIn/Indeed/Rozee.
- **AI (Phase 1+):** anything with personal data (resumes) → Groq. Public job postings → Gemini. Everything goes through one gateway layer.
- **UI:** premium dark design system (a single blue accent, monochrome surfaces, `border-white/[0.08]` hairlines).
- **Money:** the API serves USD everywhere. Salaries are normalised using `staging.currency_rates`.
- **Tests:** pytest in `etl/tests/` and `backend/tests/`. New logic is written test-first. ETL database tests need Docker Desktop running locally (they start a throwaway `postgres:16-alpine`); CI uses `TEST_DATABASE_URL`. Run with `cd etl && ../venv/Scripts/python -m pytest` and `cd backend && ./venv/Scripts/python -m pytest`. Never import a module that calls `load_dotenv()` at import time in tests without patching it (see `tests/test_transformer_guard.py`), because `etl/.env` points at production.
- **Taxonomy changes:** never hand-edit `skills_taxonomy.json` for curation. Write a declarative script in `etl/tools/` (see `curate_taxonomy_2026_10.py`), keep `test_taxonomy.py` green, then run `python -m ops.reextract --dry-run` / `--apply` to re-apply roles and skills to stored jobs (it refuses when it would drop more than 25%).
- **Migrations:** `database/migrations/NNN_name.sql`, each wrapped in `BEGIN; … COMMIT;`, idempotent where possible. Apply with `cd etl && ../venv/Scripts/python -m ops.migrate up` (CI also does it on push once the secret works). Never edit an applied migration; add a new one.

## Gotchas

- Supabase **transaction pooler (6543) drops long connections**. Long ETL steps and the backend pool rewrite the URL to the **session pooler (5432)**.
- dbt must run with **`--target dev`** so the output lands in `staging_marts`. Target `prod` produces a wrong `marts_marts`.
- Adzuna descriptions are cut at **500 characters** (a hard limit). Its API terms restrict commercial analytics; a licence has been requested.
- Marts only count jobs from the **last 60 days** (`COALESCE(job_posted_at, extracted_at)`).
- The **skill-trend chart** (`/skills/trend`) is computed from `staging.stg_jobs`, not from the archive. Retention is 400 days so it keeps a year; shortening it cuts the chart.
- Raw payloads of processed jobs are stripped after 7 days (Adzuna native payloads become `{"_stripped": true}`), so `transformer.py --reprocess` can no longer rebuild those rows from raw.
- **Render only redeploys the API when its watched paths change** (`rootDir: backend` + `buildFilter` in `render.yaml`: `backend/**`, `etl/skill_patterns.py`, `etl/config/skills_taxonomy.json`). If the Render service isn't blueprint-synced, set the same Build Filters in the dashboard. Otherwise taxonomy changes never reach the live resume analyzer or extension.
- The CI ETL failed on every run from Jan to Sep 2026 because the `SUPABASE_URL` GitHub secret didn't work. Local preflight with `etl/.env` passes, so the local URL is the right value.

## Pending manual steps (owner)

Phase 0, in this order:
- [ ] **Fix the CI secret:** GitHub → Settings → Secrets and variables → Actions → set `SUPABASE_URL` to the exact value in `etl/.env` (host `aws-1-ap-south-1.pooler.supabase.com`). The old `SUPABASE_HOST/USER/PASSWORD/DB` secrets are unused and can be deleted.
- [ ] **Failure emails:** create a free Resend account → API key → add the secrets `RESEND_API_KEY` and `ALERT_EMAIL` (the email you signed up to Resend with).
- [ ] **First run:** Actions → ETL Pipeline → Run workflow with **adzuna = true** (the first run must include Adzuna, or the marts rebuild on thin data). Check that it goes green.
- [ ] **Keep-warm:** `cd infra/keepwarm && npx wrangler login && npx wrangler deploy` (free Cloudflare account). Then ask Claude to delete `.github/workflows/keep_warm.yml`.
- [ ] **Only after keep-warm moves:** make the GitHub repo private.
- [ ] **Adzuna:** send the email in `docs/ops/adzuna-licence-request.md`.
- [ ] Optional: 4 orphan files in the `resumes` bucket have no database row (pre-existing). Delete them in the Supabase dashboard if they aren't needed.

Later:
- [ ] Get free Groq and Gemini API keys (Phase 1 enrichment).
- [ ] Choose the final product name and domain before the Phase 2 beta.
