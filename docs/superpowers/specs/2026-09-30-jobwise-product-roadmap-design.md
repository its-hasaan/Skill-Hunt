# Jobwise: Product Roadmap and Design

**Date:** 2026-09-30
**Status:** Draft, awaiting review
**Scope:** Umbrella design that turns the Skill Hunt / Job Script portfolio project into a sellable product. The work is split into six phases. Each phase gets its own implementation plan, and phases 1–5 get a short design pass of their own before planning. Phase 0 is specified here in enough detail to plan straight away.

---

## 1. Goal

Turn the platform into a paid B2C product for **South Asian (Pakistan/India) tech professionals looking for international remote jobs**. It runs on free tiers until it earns revenue.

The product is a **remote job copilot**. It gives each user a daily feed of remote jobs they can *actually apply for from their country*, a match score explained with real market data, AI help with applications, an application tracker, and a browser extension that brings all of this onto job sites. The existing market analytics become the free way people discover the product.

**Why this wins:** The competing job-seeker tools (Jobright, Teal, Huntr, Careerflow, Jobscan, Simplify; $24–50/mo) are US-centric, and none of them bases its advice on real labour-market data. The tools that do have that data (Lightcast and similar) sell only to enterprises. This platform already has the harder part (skill demand, salary premiums, career transitions, Pakistan/India coverage). What's missing is the everyday workflow users pay for.

## 2. Decisions log

| # | Decision | Choice | Reason |
|---|---|---|---|
| D1 | Paying customer | Job seekers (B2C) | Builds on the existing product. B2B (bootcamps/universities) can come later on the same data. |
| D2 | Segment | Remote-first South Asia | They earn in USD, so they can pay; US tools ignore them; the remote-job data can legally be used commercially. Local jobs are a secondary feed. |
| D3 | Adzuna | Ask for a commercial licence; meanwhile build the primary data on sources we're allowed to use | Adzuna's terms allow publishing listings and personal research; other commercial use needs a licence after a 14-day trial. Must be settled before the paid launch (Phase 4). |
| D4 | AI providers | Groq free tier for anything with personal data (resumes); Gemini Flash free tier for public job-posting tasks; one gateway layer in between | Groq is contractually barred from training on customer data, on every tier. Gemini's free tier may use prompts for training, which is fine for public postings but not for resumes. |
| D5 | Product shape | Web copilot first; Extension 2.0 with far more features and zero setup | The user asked for a stronger, easier extension. |
| D6 | Data sources | Public job-board APIs of hiring systems + remote boards + **company career-page crawler** | Full descriptions, direct apply links, commercially usable. |
| D7 | Roles | 20 roles: the 15 current ones + Software Engineer (general), QA/Test Automation, UI/UX Designer, Product Manager, Technical Support/Success | "Software Engineer" is the most common job-board title and is missing today. The other roles widen the audience. |
| D8 | Automation stance | Assisted, never automatic: alerts, one-click save, AI suggestions the user approves, autofill where **the user clicks submit**. No auto-submit bots; no LinkedIn Easy Apply autofill. | Auto-apply tools have poor reviews and cause LinkedIn account bans. |
| D9 | Free/Pro split | Free: analytics, top 15 matches/day, 25 tracked jobs, weekly alerts, extension panel, basic autofill, 3 AI tries. Pro: everything unlimited or fair-use | The free plan has to bring people back daily; Pro charges for AI and time savings. |
| D10 | Pricing | Pro $12/mo standard, $5/mo in lower-income countries (Pakistan, India, Bangladesh, …); 3-month Job Hunt Pass $25 / $12 | Cheaper than $24–40 competitors; a pass fits how long a job search lasts. Tune it with beta data. |
| D11 | Payments | Paddle (may change), behind a provider-agnostic billing interface | Paddle acts as the legal seller, supports per-country prices, and pays out via Payoneer (works in Pakistan). Polar and Lemon Squeezy remain fallbacks. |
| D12 | Hosting | Frontend → Cloudflare Pages; API stays on Render free; Supabase free + a second free project for staging | Vercel's free plan forbids commercial use. Render and Cloudflare free tiers allow it. |
| D13 | Repo visibility | Private | Protects the product. The pipeline must fit 2,000 Actions minutes a month. |
| D14 | Name | **Jobwise** (working name) | A final name/trademark/domain check is still open (see §12). |

## 3. Current state (baseline, verified 2026-09-30)

- **The scheduled ETL is broken.** Every run of `.github/workflows/etl_pipeline.yml` since at least March 2026 has failed at "Run extraction (Adzuna)", and multi-source ingestion is skipped whenever that step fails. The newest job in the database is from 2026-07-10 (the last manual `refresh_all.py`), so "current jobs (60 days)" = **0**.
- **Data concentration:** Adzuna provides 68,944 of ~69,500 raw jobs. Adzuna descriptions are cut at 500 characters. Other sources contribute a few hundred jobs.
- **Storage:** 241 MB of the 500 MB Supabase free tier (`raw.jobs` 116 MB, `stg_jobs` 73 MB).
- **Users:** 3 registered. The product is effectively pre-launch, so breaking changes to the data model are acceptable.
- **Privacy gap:** resume uploads get public URLs (`backend/app/storage.py:62`).
- **Keep-warm:** `.github/workflows/keep_warm.yml` pings Render every 5 minutes. Once the repo is private, each run bills as at least one minute (≈ 8,600 min/month), which is over the 2,000-minute limit.
- Reusable assets: the connector framework (`NormalizedJob`, retrying session, `RoleMatcher`), the taxonomy fast-path extractor, `ResumeSkillExtractor`, the extension scraper and panel, auth and personalization tables, rate limiting, and the analytics marts.

## 4. Roadmap

| Phase | Sub-project | Exit criteria (milestone) |
|---|---|---|
| **0** | Foundation fixes | Daily pipeline has run green for 7 days in a row; failures send an alert; DB under 350 MB; resumes private; repo private; Adzuna email sent |
| **1** | Remote job data engine | ≥ 5,000 open, deduplicated, eligibility-tagged remote jobs across 20 roles; hand-checked eligibility sample ≥ 90% correct |
| **2** | Web copilot core | **Public free beta**: onboarding → feed → job page → tracker → email alerts; legal pages live; Cloudflare Pages + domain |
| **3** | Extension 2.0 | Live on the Chrome Web Store: zero-setup connect, panel on 7 site families + JSON-LD pages, save to tracker, autofill on 4 job-board form types |
| **4** | AI assistance + Pro | **Paid launch**: tailoring, cover letters, interview prep, learning roadmap, quotas, Paddle checkout, Free/Pro limits; Adzuna licence question settled |
| **5** | Growth | SEO market pages, referrals, monthly market report; decision on adding B2B |

The phases run in order. Phase 3 depends on the profile, match and tracker APIs from Phase 2. Phase 4's paywall ships together with the features worth paying for.

## 5. Phase 0: Foundation fixes (detailed)

### 5.1 Pipeline reliability
1. **Diagnose the Adzuna CI failure** from the Actions logs (likely candidates: expired or over-quota keys, a connection-string or pooler mismatch in the secrets, or `extractor.py` exit code 2 on zero jobs). Fix the root cause; no retry band-aids.
2. **Decouple sources.** Each source (Adzuna, multi-source ingest) becomes its own step with `continue-on-error`. The transform runs if *any* source inserted rows. A failed source never skips the others.
3. **Schedule:** a daily run for all non-Adzuna sources; Adzuna weekly (stays within 250/day and 2,500/month). dbt and the archive run after every successful transform.
4. **Run ledger:** a new table `ops.pipeline_runs (run_id, step, status, rows_in, rows_out, started_at, finished_at, error)` written by `refresh_all.py` and CI.
5. **Failure alert:** a final CI step emails the owner when any step fails (sent with Resend; the key is stored as a secret).
6. **Throughput:** batched `stg_jobs` / `stg_job_skills` writes (PIPELINE_REVIEW Part 2 #12). Two phases: insert the jobs and get their ids back, then bulk-insert the skills. Target: a daily run under 25 minutes.

### 5.2 Storage budget
- After a successful transform, strip `_raw` from `raw.jobs.raw_data` (keep `_source` and `_normalized` for reprocessing).
- Retention: delete `stg_jobs` rows (and their skills) whose `COALESCE(job_posted_at, extracted_at)` is older than 120 days; monthly trends survive in `archive.skill_demand_history`.
- Run `VACUUM` after pruning. Target under 350 MB, and log the size to the run ledger.

### 5.3 Hygiene and privacy
- Resumes bucket → private; `storage.py` returns signed URLs that expire after 1 hour instead of `get_public_url`.
- Move keep-warm from GitHub Actions to a **Cloudflare Worker cron trigger** (free), which also works as an uptime check. Then delete `keep_warm.yml`.
- Make the repo private; confirm secrets are not in git (`frontend/.env` → `.env.example` + host env vars).
- **Migration runner:** a `ops.schema_migrations` table plus a script that applies the files in `database/migrations/` in order, run from CI. Record migrations 001–005 as the baseline (confirm 005 is applied in production).
- Send the Adzuna licence and publisher enquiry (the owner does this; a draft email is part of the Phase 0 plan).

### 5.4 Testing
- Add a pytest setup (`etl/tests`, `backend/tests`). Phase 0 covers: source isolation (one connector raising doesn't stop the others), the retention SQL (against a fixture), and signed-URL generation.

## 6. Phase 1: Remote job data engine

### 6.1 New sources
- **Job-board API connectors** (one `NormalizedJob` connector each): Greenhouse (`boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`), Lever (`api.lever.co/v0/postings/{company}`), Ashby, Workable and SmartRecruiters public posting endpoints. Each one runs over `etl/config/companies.json` entries of the form `{name, domain, ats, board_token, active}`.
- **Company career-page crawler** (extends `generic_scraper.py`):
  1. Fetch robots.txt (**required**; skip the site if it can't be read), then the careers page and sitemap.
  2. **Look for an embedded hiring system first:** if the page embeds or links to Greenhouse, Lever or Ashby, add or update the `companies.json` entry and hand the company to that connector. *(This is how the company list grows.)*
  3. Otherwise, extract `schema.org/JobPosting` JSON-LD from the job-detail pages.
  4. Pages that only render with JavaScript are skipped in Phase 1 (a headless browser is a later option).
  5. Named `JobwiseBot` user agent, a per-site daily page budget, conditional GETs (ETag / Last-Modified), and a polite delay between requests.
- **Starting company list:** employer names/domains from the current remote-board data plus a hand-picked list, each checked against the job-board APIs. Target: 500–1,000 companies.
- Remote boards (RemoteOK, WWR, Himalayas, Jobicy, Arbeitnow, The Muse) and Jooble stay. Adzuna follows D3.

### 6.2 Data model changes
- `stg_jobs` gains: `apply_url`, `ats`, `company_domain`, `first_seen_at`, `last_seen_at`, `closed_at`, `fingerprint`, `canonical_job_id`, `workplace_type` (remote/hybrid/onsite).
- **Job lifecycle:** a job-board API returns a company's *full* list of open jobs, so a job missing from it is marked closed (`closed_at`). Board and feed sources close a job after 14 days unseen.
- **Removing duplicates:** `fingerprint` = normalised(company) + normalised(title) + normalised(location). Duplicates point to one canonical job, chosen in this order: company's hiring system > career page > Jooble/boards > Adzuna.
- **`staging.job_enrichment`** (keyed by job and content hash, so a job is never re-enriched unless its text changes):
  `remote_scope` (worldwide | regions | countries | hybrid | onsite), `eligible_countries` / `eligible_regions`, `eligible_pk`, `eligible_in`, `eligibility_confidence`, `eligibility_evidence` (the quoted sentence), `seniority` (intern/junior/mid/senior/lead), `min_years`, `tz_overlap_required`, `salary_min_usd` / `salary_max_usd`, `method` (rules|llm), `model`, `enriched_at`.
- **`mart_job_feed`** (dbt table): one row per open canonical job with its enrichment, skills and USD salary, indexed on role, eligibility flags and `first_seen_at`.

### 6.3 Enrichment logic
- **Rules first:** job-board location fields ("Remote – US", "Anywhere", "EMEA"), plus phrase patterns in the description ("must be based in", "authorized to work in the US", "EST overlap", "worldwide").
- **Gemini Flash** only for jobs the rules can't decide. Batches of 20 jobs per call, JSON-schema output, and an evidence sentence required. Free quota ≈ 1,500 calls/day ≈ 30k jobs/day.
- Anything below a confidence threshold is shown as "Eligibility unclear". Missing a job is better than wrongly promising someone they can apply.

### 6.4 Roles and taxonomy
- `RoleMatcher` gets title patterns for the 5 new roles. "Software Engineer (general)" catches generic engineering titles only *after* every specific role has been checked.
- Taxonomy gets ~60+ skills for design, product, QA and support (Figma, user research, roadmapping, Selenium, Cypress, Zendesk, …), run through `clean_taxonomy.py`.
- PIPELINE_REVIEW Part 2 #1 (check `search_role` against the title for Adzuna/Jooble) and #3 (context rules for ambiguous short skills such as Go, R, C) are included here, because feed quality depends on them.

## 7. Phase 2: Web copilot core → free beta

- **Onboarding:** upload a resume → `ResumeSkillExtractor` for skills + Groq (via the gateway, §10.1) for years, titles and education → the user edits the profile → preferences (≤ 3 target roles, country, minimum USD salary, timezone, remote/hybrid). New `public.user_job_profiles` table.
- **Match score (explainable):**
  - *Skill fit, 60%:* Σ weight of job skills the user has ÷ Σ weight of all the job's skills, where weight = that skill's demand % for the role (from `mart_skill_demand`).
  - *Seniority fit, 20%:* user years vs `seniority`/`min_years`.
  - *Preferences, 20%:* timezone overlap, salary floor, workplace type.
  - Eligibility is a **filter** (hidden unless "show anyway"), not a weight.
  - Explanation strings include the "unlock" figure: *"Missing dbt (in 41% of these jobs; learning it opens 1,240 more)."* "Opens N more" = the number of open jobs in the user's target roles, eligible for their country, that list the skill.
  - Scores are computed in the backend for the user's roles against `mart_job_feed`, cached per user per day.
- **Feed** (`/feed`): sorted by score, then freshness; "new since last visit"; filters; "not interested".
- **Job page:** eligibility badge + evidence sentence, match breakdown, highlighted description (reuse the Jobs page), USD salary context, "company has N jobs open to your country", direct apply link. Clicking Apply prompts "Did you apply?", which moves the tracker card.
- **Tracker** (`/tracker`): board columns Saved / Applied / Interviewing / Offer / Rejected; notes, dates, follow-up reminders. New `public.applications` table (RLS, owner-only).
- **Alerts:** a digest of new strong matches (free: weekly; Pro: daily) via Resend, sent by a scheduled job after the daily pipeline.
- **Market section:** the existing analytics pages are grouped under "Market" with a "Remote: open to South Asia" filter and new stats: eligibility share by role, top companies hiring from South Asia, median days a job stays open.
- **Launch requirements:** domain + Cloudflare Pages (API at `api.<domain>` on Render with CORS); privacy policy, terms, refund policy; self-service account and data deletion; PostHog + Sentry; rename the UI to the final brand.

## 8. Phase 3: Extension 2.0

- **Zero-setup connect:** a "Connect extension" button in the web app hands a session token to the extension (`externally_connectable`). The API URL setting moves to an Advanced menu.
- **Where it works:** LinkedIn and Indeed (existing scrapers), Greenhouse, Lever, Ashby, Workable, Wellfound, plus **any page with `JobPosting` JSON-LD** (shared parser with the crawler).
- **Panel:** eligibility badge, match % with breakdown, missing skills with market %, salary context, one-click **Save to tracker**, "Tailor resume for this job" (Pro, Phase 4).
- **Autofill:** on Greenhouse, Lever, Ashby and Workable application forms, fills contact details, links, work authorization, years of experience, salary expectation, the resume file, and saved answers from the profile. It runs only when the user clicks, fills one form at a time, and **the user submits**. LinkedIn Easy Apply is excluded.
- **Popup:** today's top matches, tracker counts, on/off toggle.
- The extension moves into its own private repo; publishing on the Chrome Web Store ($5 one-time fee) is part of this phase.

## 9. Phase 4: AI assistance + Pro → paid launch

- **Resume tailoring:** suggested bullet rewrites and skill reordering for a specific job, based **only on the user's resume**. The AI may not add skills the user doesn't have; those are listed as "learn" instead. Shows keyword coverage before and after, and exports DOCX (python-docx) and PDF.
- **Cover letter** and **answers to application questions** (also used by extension autofill), with the same rule.
- **Interview prep:** likely questions from the job description plus the user's gaps, with outline answers drawn from the user's own experience.
- **Learning roadmap:** gaps ranked by "jobs unlocked", with salary premium, estimated weeks to learn, and **free resources from a hand-picked `learning_resources.json`** (the AI never writes URLs); progress tracking for Pro.
- **Quotas:** a `public.ai_usage` counter per user per day; free = 3 lifetime tries; Pro = fair use (~20/day). The gateway refuses requests over quota before calling a provider.
- **Billing:** a `BillingProvider` interface (`create_checkout`, `verify_webhook`, `parse_event`) with a Paddle adapter; `public.subscriptions` holds the plan and period end; an `entitlements` check guards Pro endpoints. Country-specific prices are set as Paddle country price overrides.
- **Gate:** the Adzuna reply is settled (licensed → keep; declined → Adzuna shown only as attributed listings and left out of paid analytics).

## 10. Cross-cutting design

### 10.1 AI gateway (`backend/app/llm/`)
- A single entry point `complete(task, inputs, schema, pii: bool)`. Tasks with personal data route to Groq; public tasks to Gemini. The model for each task lives in config.
- Prompt templates are versioned in files; outputs are validated against a JSON schema, with one repair retry.
- Results are cached by (task, prompt version, input hash); quota is checked before calling a provider; each call's tokens and latency are logged.
- Switching to a paid provider is a config change.

### 10.2 Free-tier budget

| Service | Use | Limit to watch |
|---|---|---|
| Supabase (×2: prod, staging) | DB, auth, storage | 500 MB DB each; 1 GB storage; 50k MAU |
| Render free | API | 750 instance-hours/month (one service) |
| Cloudflare Pages + Workers | Frontend, keep-warm cron | Free, commercial use allowed |
| GitHub Actions (private) | Daily pipeline, CI | 2,000 min/month |
| Groq free | Tasks with personal data | ~1,000 calls/day on the 70B model |
| Gemini Flash free | Enriching job postings | ~1,500 calls/day |
| Resend free | Alerts and failure email | ~3,000/month (confirm when building) |
| PostHog / Sentry free | Usage analytics / errors | 1M events / 5k errors per month |
| **Unavoidable costs** | Domain, Chrome Web Store | ~$10–15/year; $5 one-time |

When revenue arrives, upgrade in this order: Render Starter (no cold starts) → Groq paid tier → Supabase Pro.

### 10.3 Trust and legal
Privacy policy, terms, refund policy; self-service data deletion; private resume storage; source attribution where required ("Jobs by Adzuna", board links back); the AI note "suggestions are based only on your resume; review before sending"; no training of any model on user data.

### 10.4 Engineering standards
New logic is test-driven (match score, eligibility rules, fingerprinting, parsers, quota and entitlements). Schema changes go only through the migration runner. Staging Supabase gets migrations before production. Errors go to Sentry and pipeline health to the run ledger.

## 11. Non-goals
- Bots that submit applications automatically; LinkedIn Easy Apply autofill.
- Any evasion technique (proxy rotation, fingerprint spoofing, CAPTCHA solving); scraping LinkedIn, Indeed or Rozee.
- Non-tech roles; B2B features; a public data API.
- Paid job data feeds.
- Headless-browser crawling in Phase 1.

## 12. Risks and open items

| Item | Handling |
|---|---|
| **Name conflict:** jobwise.ai (a UK AI job-matching product) exists | Pick the final name and check trademark and domain **before** buying the domain or registering with Chrome Web Store and Paddle (Phase 2 launch requirement) |
| Adzuna declines a licence | Planned for (D3); analytics rely on the other sources |
| Wrong eligibility labels damage trust | Confidence threshold + evidence sentence + "unclear" state + a "report wrong label" button; 90% accuracy on a hand-checked sample is a Phase 1 exit criterion |
| Free AI quotas change | The gateway makes switching providers a config change; per-user quotas limit exposure |
| Supabase 500 MB | Retention and payload stripping (Phase 0); size is logged every run |
| Paddle rejects the seller account | Polar and Lemon Squeezy adapters behind the same interface |
| Job-board APIs change | Each connector is isolated and fails without stopping the run; the run ledger flags a zero-row source |
| Render cold starts | Cloudflare cron keep-warm; Starter plan once revenue arrives |
