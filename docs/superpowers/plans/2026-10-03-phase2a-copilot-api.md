# Phase 2a: Copilot API (profile, match score, feed, tracker, alerts) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the web copilot its backend: a job profile per user (seeded from their resume), an explainable match score against the Phase 1 job feed, the feed and job-page endpoints, an application tracker, account deletion, South Asia market stats, and a weekly email digest.

**Architecture:**
- One **shared, pure matcher** `etl/matching.py` (like `etl/skill_patterns.py`): skill weights, the 60/20/20 score, the eligibility filter and the explanation strings ("Missing dbt (in 41% of these jobs; learning it opens 1,240 more)"). The API imports it via `sys.path`; the digest job runs it in the ETL.
- The API keeps an in-process **feed snapshot** (`app/feed_store.py`): `staging_marts.mart_job_feed` + per-role skill weights computed from the feed itself, refreshed hourly. Scores are computed per request from the snapshot and cached per user per day in memory.
- New user tables (migration 015) with owner-only RLS; the API reaches them over its service connection, always filtered by the verified JWT user id.
- An **AI gateway** `backend/app/llm/` (spec §10.1): `complete(task, inputs, schema, pii)`; personal data → Groq, public text → Gemini; versioned prompt files; JSON validated with one repair retry; in-memory cache. Every caller has a non-AI fallback, so missing keys never break a feature.

**Tech Stack:** FastAPI, asyncpg, pytest + pytest-asyncio (Postgres container / `TEST_DATABASE_URL`), httpx, Groq + Gemini REST APIs, Resend.

**Spec:** `docs/superpowers/specs/2026-09-30-jobwise-product-roadmap-design.md` §7 (Phase 2), §10.1 (AI gateway), §10.3 (trust), D4, D8, D9.

## Global Constraints

- Match score = **60% skill fit + 20% seniority fit + 20% preferences**, 0–100. Skill fit = Σ weight of job skills the user has ÷ Σ weight of all the job's skills; weight = share of open feed jobs in that role listing the skill. Eligibility is a **filter**, never a weight: jobs with `eligible_<country> = FALSE` are hidden; `NULL` (unclear) is hidden unless the user turns on "show unclear".
- "Opens N more" = open feed jobs in the user's target roles, eligible for their country, that list the skill.
- Profiles: ≤ 3 target roles from the 20 tracked roles; country `pk` | `in` | other ISO2; timezone as an IANA name; workplace preferences ⊆ {remote, hybrid, onsite}; min salary in USD/year.
- Resume parsing is personal data → **Groq only** (D4). Without `GROQ_API_KEY`, years/titles/education come from deterministic heuristics and the user edits them; nothing fails.
- Tracker statuses: `saved`, `applied`, `interviewing`, `offer`, `rejected`. A user sees and changes only their own rows (API filter + RLS).
- Account deletion removes every row the user owns, their resume files, and the auth user (needs `SUPABASE_SERVICE_KEY` on the API; without it the data rows are still deleted and the response says what's left).
- Digest: weekly (Monday) for everyone in the beta; `alert_frequency = 'off'` opts out. Without `RESEND_API_KEY` or a verified sender (`DIGEST_FROM`), the job logs and exits 0.
- No AI writes URLs; no auto-apply (D8).
- Migrations: `015_*`, BEGIN/COMMIT, idempotent, RLS owner-only like 002. Render's `buildFilter` gains `etl/matching.py`.
- Git: commit + push per task when tests pass; 5–8 word messages; no Claude attribution.

## Review Focus

1. **A user in "other" country (not PK/IN).** Expected: only `remote_scope = 'worldwide'` jobs are treated as eligible; no crash. Test: Task 2 `test_eligibility_filter_other_country`.
2. **A job with no skills extracted.** Expected: skill fit is neutral (0.5), not a division by zero; explanation says skills weren't listed. Test: Task 2 `test_job_without_skills_scores_neutral`.
3. **Two quick PUTs of the profile with 4 target roles / an unknown role.** Expected: 422 with a clear message; nothing stored. Test: Task 4 `test_profile_rejects_bad_roles`.
4. **A user PATCHes another user's application id.** Expected: 404, row untouched. Test: Task 6 `test_cannot_touch_other_users_applications`.
5. **Groq returns invalid JSON twice.** Expected: heuristic profile returned with `source='heuristic'`; request succeeds. Test: Task 3 `test_gateway_falls_back_after_failed_repair`.

---

## File Structure

| File | Responsibility |
|---|---|
| `database/migrations/015_copilot_user_tables.sql` | `public.user_job_profiles`, `public.applications`, `public.job_feedback`, `public.digest_log` + RLS |
| `etl/matching.py` | Shared pure matcher: `skill_weights`, `eligible`, `score_job`, `explain`, `unlock_counts` |
| `backend/app/feed_store.py` | Feed snapshot + weights, hourly refresh, per-user/day score cache |
| `backend/app/llm/__init__.py`, `gateway.py`, `prompts/resume_profile.v1.txt` | AI gateway (Groq/Gemini), JSON validation + repair, cache |
| `backend/app/profile_heuristics.py` | Years / titles / education from resume text without AI |
| `backend/app/routers/copilot.py` | `/profile`, `/profile/from-resume`, `/feed`, `/job/{id}`, `/job/{id}/not-interested`, `/applications`, `/account`, `/market/south-asia` |
| `etl/ops/digest.py` | Weekly digest of new strong matches via Resend |
| `backend/tests/pg.py`, `backend/tests/test_copilot_*.py`, `etl/tests/test_matching.py`, `etl/tests/test_digest.py` | Tests |
| `render.yaml`, `.github/workflows/etl_pipeline.yml` | buildFilter + digest step |

---

### Task 1: User tables (migration 015)

**Produces:** `public.user_job_profiles(user_id uuid PK → auth.users ON DELETE CASCADE, skills text[], years_experience numeric, current_title text, education text, target_roles text[], country text, timezone text, workplace_prefs text[], min_salary_usd integer, show_unclear boolean default false, alert_frequency text default 'weekly', last_feed_visit_at timestamptz, created_at, updated_at)`; `public.applications(id bigserial, user_id uuid, job_id integer NULL, title, company, apply_url, status text CHECK in (saved, applied, interviewing, offer, rejected), notes, applied_at timestamptz, follow_up_at date, created_at, updated_at, UNIQUE (user_id, job_id))`; `public.job_feedback(user_id, job_id, kind text default 'not_interested', created_at, PK (user_id, job_id))`; `public.digest_log(id, user_id, sent_at, job_ids integer[])`. RLS on all four: owner-only (`auth.uid() = user_id`).

- [ ] **Step 1:** `backend/tests/pg.py` fixture (`pg_db`): Postgres via `TEST_DATABASE_URL` or a docker container (same pattern as `etl/tests/conftest.py`), fresh database per test, stub `auth` schema (`auth.users`, `auth.uid()`), migration 015, stub `staging_marts.mart_job_feed` and `staging.stg_jobs` tables.
- [ ] **Step 2: Failing test** `test_copilot_tables.py::test_migration_is_idempotent_and_cascades` (apply twice; deleting the auth user removes profile, applications, feedback).
- [ ] **Step 3:** Write the migration → pass. Apply to production. Commit `"Add copilot user tables"`.

### Task 2: Shared matcher (`etl/matching.py`)

**Produces:** `skill_weights(jobs) -> dict[role, dict[skill, float]]`; `eligible(job, country, show_unclear) -> bool`; `score_job(job, profile, weights) -> dict(score:int, skill_fit, seniority_fit, preference_fit, matched:list, missing:list)`; `explain(result, job, unlocks, role_weights) -> list[str]`; `unlock_counts(jobs, profile) -> dict[skill, int]`.

Seniority fit: with `min_years`: 1 if user ≥ min else max(0, 1 − (min − user)/3). Without: distance between the user's band (intern 0, junior <2, mid 2–5, senior 5–8, lead 8+) and the job's `seniority`, 1 / 0.6 / 0.2 for 0 / 1 / ≥2 bands apart; unknown → 0.7. Preferences (equal thirds): timezone (job `tz_overlap` vs user offset: same region or none → 1; Pakistan/India vs americas → 0.5; europe → 0.8), salary (job max ≥ floor → 1, unknown → 0.7, below → 0), workplace (in prefs → 1 else 0.3).

- [ ] **Step 1: Failing tests** (`etl/tests/test_matching.py`): `test_skill_weights_from_feed`, `test_score_weights_and_bounds`, `test_job_without_skills_scores_neutral`, `test_seniority_fit_cases` (table), `test_preference_fit_cases` (table), `test_eligibility_filter_pk_in`, `test_eligibility_filter_other_country`, `test_unlock_counts_and_explanations` (exact string "Missing dbt (in 41% of Data Engineer jobs; learning it opens 3 more)").
- [ ] **Step 2–4:** fail → implement → pass. Add `etl/matching.py` to `render.yaml` buildFilter. Commit `"Add shared explainable match scoring"`.

### Task 3: AI gateway + resume profile

**Produces:** `app.llm.gateway.complete(task: str, inputs: dict, schema: dict, pii: bool) -> dict` (raises `LLMUnavailable` when the provider key is missing or both attempts fail validation); providers `groq` (`https://api.groq.com/openai/v1/chat/completions`, model `GROQ_MODEL` default `llama-3.3-70b-versatile`, `response_format: json_object`) and `gemini`; prompt `app/llm/prompts/<task>.v<N>.txt`; cache key (task, version, sha256 of inputs). `app.profile_heuristics.profile_from_text(text) -> dict(years_experience, current_title, education, target_roles)`; `draft_profile(text, skills) -> dict(..., source='ai'|'heuristic')`.

- [ ] **Step 1: Failing tests:** `test_gateway_routes_pii_to_groq`, `test_gateway_repairs_once_then_raises`, `test_gateway_caches_by_input_hash`, `test_gateway_without_key_is_unavailable`, `test_gateway_falls_back_after_failed_repair` (draft_profile → heuristic), `test_heuristics_years_from_date_ranges` ("Jan 2019 – Present", "2016 - 2018", overlapping ranges merged), `test_heuristics_titles_and_education`.
- [ ] **Step 2–4:** fail → implement → pass. Commit `"Add AI gateway and resume profile draft"`.

### Task 4: Profile + feed + job endpoints

**Produces:** `GET /api/v1/profile` (404 when none), `PUT /api/v1/profile`, `POST /api/v1/profile/from-resume` (multipart; returns a draft, stores nothing), `GET /api/v1/feed?role=&show_unclear=&limit=&offset=` (scored, eligibility-filtered, minus "not interested", sorted by score then `first_seen_at`; each item has `score`, `breakdown`, `explanations`, `is_new` vs `last_feed_visit_at`; updates `last_feed_visit_at`), `GET /api/v1/job/{job_id}` (feed row + description + match for a logged-in user + `company_open_jobs` for the user's country), `POST /api/v1/job/{job_id}/not-interested`.

- [ ] **Step 1: Failing tests** (`test_copilot_feed.py`, `pg_db` + seeded feed rows, auth dependency overridden): `test_profile_roundtrip`, `test_profile_rejects_bad_roles`, `test_feed_requires_profile`, `test_feed_filters_eligibility_and_not_interested`, `test_feed_sorted_by_score_and_marks_new`, `test_job_page_has_description_and_match`, `test_from_resume_returns_draft_without_storing`.
- [ ] **Step 2–4:** fail → implement (`feed_store.py`, `routers/copilot.py`) → pass. Commit `"Add profile, feed and job endpoints"`.

### Task 5: Tracker endpoints

**Produces:** `GET /api/v1/applications`, `POST /api/v1/applications` (`{job_id}` copies title/company/link from the feed, or `{title, company, apply_url}` for an external job; idempotent per job), `PATCH /api/v1/applications/{id}` (status, notes, applied_at, follow_up_at; moving to `applied` sets `applied_at` when empty), `DELETE /api/v1/applications/{id}`.

- [ ] **Step 1: Failing tests** (`test_copilot_tracker.py`): `test_save_job_is_idempotent`, `test_status_flow_sets_applied_at`, `test_external_application`, `test_cannot_touch_other_users_applications`, `test_rejects_unknown_status`.
- [ ] **Step 2–4:** fail → implement → pass. Commit `"Add application tracker endpoints"`.

### Task 6: Account deletion + South Asia market stats

**Produces:** `DELETE /api/v1/account` (profile, applications, feedback, digest log, saved searches, resume rows + files, then the auth user through `DELETE {project}/auth/v1/admin/users/{id}` with the service key; returns `{"deleted": {...}, "auth_user_deleted": bool}`); `GET /api/v1/market/south-asia` (per role: open remote jobs, share eligible for PK and for IN; top 15 companies by jobs open to PK or IN; median days open of jobs closed in the last 60 days).

- [ ] **Step 1: Failing tests:** `test_account_deletion_removes_everything` (fake auth admin client), `test_account_deletion_without_service_key_reports_it`, `test_south_asia_stats_shape`.
- [ ] **Step 2–4:** fail → implement → pass. Commit `"Add account deletion and South Asia stats"`.

### Task 7: Weekly digest

**Produces:** `etl/ops/digest.py`: `due_users(conn, today) -> list[dict]` (alert_frequency weekly on Mondays / daily every day, not sent in the last 6 days for weekly), `pick_matches(feed, profile, since, limit=10, min_score=60)`, `render_digest(name, matches, app_url) -> (subject, text, html)`, CLI `python -m ops.digest [--dry-run]`; writes `public.digest_log`. CI step after the feed mart (Mondays, `continue-on-error`), env `RESEND_API_KEY`, `DIGEST_FROM`, `APP_URL`.

- [ ] **Step 1: Failing tests** (`etl/tests/test_digest.py`): `test_due_users_weekly_and_opt_out`, `test_pick_matches_new_and_eligible_only`, `test_render_digest_lists_jobs_with_links`, `test_no_sender_is_a_clean_skip`.
- [ ] **Step 2–4:** fail → implement → pass. actionlint clean. Commit `"Add weekly job match digest"`.

## Self-review notes

- Spec §7 backend parts: onboarding (T3, T4), match score + explanations + unlock figure (T2, T4), feed with new-since-last-visit / filters / not-interested (T4), job page incl. evidence, breakdown, salary context, company jobs for your country (T4), tracker (T5), alerts (T7), market section stats (T6), self-service deletion (T6). Frontend, legal pages, PostHog/Sentry, Cloudflare Pages and rename are Phase 2b.
- §10.1 gateway (T3): routing by `pii`, versioned prompts, schema validation + one repair, cache. Quotas and token logging land with Pro (Phase 4).
- Names consistent: `skill_weights`, `eligible`, `score_job`, `explain`, `unlock_counts`, `complete`, `LLMUnavailable`, `draft_profile`.
