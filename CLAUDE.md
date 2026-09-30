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
| 0 | Foundation fixes: CI ETL repair, daily schedule, run ledger + failure email, storage retention, private resumes, migration runner, keep-warm on Cloudflare | **In progress** |
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
- **CI:** `.github/workflows/etl_pipeline.yml`.

## Conventions

- **Git:** commit and push small, *tested* increments straight to `main`. Messages are 5–8 words on a single line. **Never add Claude as co-author or collaborator** (no `Co-Authored-By`, no "Generated with" lines). Use a branch only for work that isn't working yet. Stage only the files you touched.
- **Data sources:** use a real user agent, respect robots.txt, back off on 429. No proxy rotation, fingerprint spoofing, CAPTCHA solving, or scraping of LinkedIn/Indeed/Rozee.
- **AI (Phase 1+):** anything with personal data (resumes) → Groq. Public job postings → Gemini. Everything goes through one gateway layer.
- **UI:** premium dark design system (a single blue accent, monochrome surfaces, `border-white/[0.08]` hairlines).
- **Money:** the API serves USD everywhere. Salaries are normalised using `staging.currency_rates`.
- **Tests:** pytest in `etl/tests/` and `backend/tests/`. New logic is written test-first.

## Gotchas

- Supabase **transaction pooler (6543) drops long connections**. Long ETL steps and the backend pool rewrite the URL to the **session pooler (5432)**.
- dbt must run with **`--target dev`** so the output lands in `staging_marts`. Target `prod` produces a wrong `marts_marts`.
- Adzuna descriptions are cut at **500 characters** (a hard limit). Its API terms restrict commercial analytics; a licence has been requested.
- Marts only count jobs from the **last 60 days** (`COALESCE(job_posted_at, extracted_at)`).
- Schema changes live in `database/migrations/NNN_*.sql`.

## Pending manual steps (owner)

- [ ] Make the GitHub repo private. Before doing so, keep-warm must move off GitHub Actions (Phase 0).
- [ ] Send the Adzuna commercial-licence enquiry (draft provided in Phase 0).
- [ ] Create Cloudflare and Resend accounts. Get free Groq and Gemini API keys (Phase 1).
- [ ] Choose the final product name and domain before the Phase 2 beta.
