# Jobwise (formerly Skill Hunt / Job Script)

Long-term context for this repo. Keep it current: update "Roadmap status" and "Pending manual steps" whenever a feature lands.

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
| 1 | Remote job data engine: job-board API connectors, career-page crawler, dedup, job lifecycle, eligibility enrichment, 20 roles | Not started |
| 2 | Web copilot core → free beta | Not started |
| 3 | Extension 2.0 | Not started |
| 4 | AI assistance + Pro + Paddle → paid launch | Not started |
| 5 | Growth (SEO pages, referrals, reports) | Not started |

## Architecture (short)

`sources → etl/ (Python) → Supabase Postgres (raw → staging → staging_marts via dbt) → backend/ (FastAPI on Render) → frontend/ (React+Vite) + skillhunt-extension/ (MV3, gitignored)`

- **ETL:** `etl/extractor.py` (Adzuna), `etl/ingest_sources.py` + `etl/connectors/*` (every source outputs `NormalizedJob`), `etl/transformer.py` (skills via the taxonomy regex), `etl/fetch_currency_rates.py`, `etl/refresh_all.py` (local full refresh). Config lives in `etl/config/*.json`.
- **dbt:** `dbt_project/` builds `staging_marts.mart_*`, which is what the API reads.
- **Backend:** `backend/app/routers/*` (stats, skills, salary, companies, career, resume, user, extension). Auth is Supabase JWT (`app/auth.py`). Rate limiting is in `app/ratelimit.py`.
- **DB schemas:** `raw`, `staging`, `staging_marts`, `archive`, `public` (user tables, RLS), `ops` (pipeline ops, from Phase 0).
- **Pipeline ops (`etl/ops/`):** `dbconfig` (derives everything from `SUPABASE_URL`), `preflight` (credentials check that names the fix), `migrate` (versioned migrations), `ledger` + `run_step` (every step recorded in `ops.pipeline_runs`), `retention` (400-day window; strips raw payloads after processing), `archive`, `notify` (Resend failure email). CLIs: `python -m ops.<name>` from `etl/`. They read `etl/.env` only when run as a CLI, never on import.
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
- **Migrations:** `database/migrations/NNN_name.sql`, each wrapped in `BEGIN; … COMMIT;`, idempotent where possible. Apply with `cd etl && ../venv/Scripts/python -m ops.migrate up` (CI also does it on push once the secret works). Never edit an applied migration; add a new one.

## Gotchas

- Supabase **transaction pooler (6543) drops long connections**. Long ETL steps and the backend pool rewrite the URL to the **session pooler (5432)**.
- dbt must run with **`--target dev`** so the output lands in `staging_marts`. Target `prod` produces a wrong `marts_marts`.
- Adzuna descriptions are cut at **500 characters** (a hard limit). Its API terms restrict commercial analytics; a licence has been requested.
- Marts only count jobs from the **last 60 days** (`COALESCE(job_posted_at, extracted_at)`).
- The **skill-trend chart** (`/skills/trend`) is computed from `staging.stg_jobs`, not from the archive. Retention is 400 days so it keeps a year; shortening it cuts the chart.
- Raw payloads of processed jobs are stripped after 7 days (Adzuna native payloads become `{"_stripped": true}`), so `transformer.py --reprocess` can no longer rebuild those rows from raw.
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
