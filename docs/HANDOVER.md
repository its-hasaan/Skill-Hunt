# Handover: next Claude chat

**Goal of the next chat(s):** finish Phase 1b, then build all of Phase 1c, **without needing the owner**. Read this file, then `docs/PROGRESS.md` §1, then `CLAUDE.md`.

## 1. What to do, in order

**A. Finish Phase 1b** (plan: `docs/superpowers/plans/2026-10-01-phase1b-company-job-boards.md`)
1. **Transformer: batched writes and reconnect.** In `etl/transformer.py`:
   - Insert `stg_jobs` with `execute_values … RETURNING job_id, raw_job_id`, then bulk-insert the skills (PIPELINE_REVIEW.md Part 2 #12).
   - On `psycopg2.OperationalError`, reconnect and continue with the next batch.
   - Test first, against the Postgres container.
   - Then process the remaining backlog (about 1,792 jobs).
2. **Common Crawl retries.** `ops/discover_companies.http_fetch(url, attempts=3, get=..., sleep=...)` should back off on 503/504. Tests:
   - 504 → 503 → 200 returns the body after 2 waits.
   - All 504s returns `None`.
   Then re-run discovery: `--max-pages 3 --validate-limit 300`.
3. **Close out 1b:** self-review `git diff 1989171..HEAD` against the plan's Review Focus, then mark 1b done in PROGRESS.md and CLAUDE.md.

**B. Phase 1c: duplicate removal, eligibility tagging, feed mart** (spec §6.2–6.3)
1. Write the plan with the writing-plans skill: `docs/superpowers/plans/<date>-phase1c-dedup-eligibility-feed.md`.
2. Build it, test first:
   - **Duplicate removal:** a fingerprint (normalised company + title + location) and `canonical_job_id`. Prefer the company's own board listing, then career page, then boards/Jooble, then Adzuna.
   - **`staging.job_enrichment`**, keyed by job and content hash:
     - `remote_scope`, `eligible_pk`, `eligible_in`, confidence, and the sentence it's based on
     - seniority, `min_years`, timezone overlap, salary in USD
     - which method decided it (`rules` or `llm`)
   - **Rules first:** location fields ("Remote – US", "Anywhere", "EMEA", "Remote, Bangalore") and phrases ("must be based in", "US work authorization", "EST overlap").
   - **AI fallback (Gemini Flash, 20 jobs per call, JSON output)**, only for jobs the rules leave unclear, and **only if `GEMINI_API_KEY` is set**.
     - Without the key, unclear jobs stay `unclear` and the pipeline still succeeds.
     - Never block on the key.
   - **`mart_job_feed`** (dbt): open (`closed_at IS NULL`), canonical, enriched jobs, indexed by role and eligibility.
   - **Run daily in CI** as a step after transform, `continue-on-error` on the AI part.
3. **Exit check:**
   - At least 5,000 open, deduplicated, tagged remote jobs (if fewer, grow the board list with discovery).
   - On a 50-job hand-checked sample, eligibility must be at least 90% correct.
   - Record the result in PROGRESS.md.

## 2. Working rules (no owner needed)

- **Process:** writing-plans → executing-plans → TDD (failing test first) → verification before claiming done.
- **Git:** commit and push to `main` after each tested step.
  - Messages 5–8 words, **no Claude co-author or attribution**.
  - Stage only your own files. Leave the owner's uncommitted `frontend/src/{index.css,pages/Dashboard.jsx}`, `data/`, `tools/`, `PIPELINE_REVIEW.md` and `PLATFORM_OVERVIEW.md` alone.
- **Quality:**
  - Small focused modules with pure, testable mapping and logic.
  - Every new migration goes through `python -m ops.migrate up`, wrapped in BEGIN/COMMIT and idempotent.
  - Long database work uses the session pooler (5432).
  - Never print secrets.
  - Write code that contains backslashes with the Write/Edit tools, not shell heredocs.
- **Production actions you may take without asking:**
  - applying new migrations
  - running ingest, transform, dbt, discovery and validation
  - backfills that are reversible or below a stated threshold (for example, reextract drops ≤ 25%)
- **Always verify on real data** after a feature (a dry run first, then a real run). Two silent bugs were caught this way.
- **Only stop and ask the owner for:** permanently deleting user or personal data, anything touching payments or auth secrets, or a plan so broken that every path is a guess.
- **Track progress continuously:** update PROGRESS.md §1 and the phase section after every task. Before the chat ends, leave nothing half-done or failing on `main`.
- **Long jobs:** run in the background with a 2-hour timeout and `flush=True` progress output.

## 3. Owner's manual steps (optional for 1b/1c; needed to go live)

None of these block coding. Each one turns on something that's already built:
1. **GitHub secret `SUPABASE_URL`** → set it to the exact value in `etl/.env`. This turns the daily CI pipeline on.
2. **Resend** (free): add the secrets `RESEND_API_KEY` and `ALERT_EMAIL` → failure emails.
3. **Actions → ETL Pipeline → Run workflow with `adzuna = true`** once (after step 1) → fresh dashboard data.
4. **Cloudflare:** run `cd infra/keepwarm && npx wrangler login && npx wrangler deploy`, then tell Claude to delete `keep_warm.yml`. Only after that, make the repo private.
5. **Gemini API key** (free, aistudio.google.com) → add `GEMINI_API_KEY` to `etl/.env` and as a GitHub secret. This enables the AI fallback for eligibility; without it, unclear jobs stay "unclear".
6. Send the Adzuna email (`docs/ops/adzuna-licence-request.md`). Pick the final product name and domain before Phase 2.
