# 🎯 Job Script

> **Data-Driven Job Market Intelligence Platform**  
> Uncover skill trends, salary insights, and career opportunities through advanced analytics and NER-powered skill extraction.

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2-61DAFB.svg)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791.svg)](https://www.postgresql.org/)
[![dbt](https://img.shields.io/badge/dbt-postgres-FF694B.svg)](https://www.getdbt.com/)

[Live Frontend](https://jobscript.vercel.app) • [Backend API](https://skill-hunt.onrender.com) • [API Docs](https://skill-hunt.onrender.com/docs)

📖 Deep dives: [Implementation Guide](IMPLEMENTATION.md) • [Scraping Bots / Multi-Source Ingestion](SCRAPING_BOTS.md) • [Auth Setup](AUTH_SETUP.md)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Technology Stack](#-technology-stack)
- [Architecture](#-architecture)
- [Getting Started](#-getting-started)
- [Usage](#-usage)
- [API Documentation](#-api-documentation)
- [Data Pipeline](#-data-pipeline)
- [Deployment](#-deployment)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

**Job Script** is a job market analysis platform that turns real job postings into actionable career intelligence for professionals, recruiters, and analysts. It combines a modern data-stack ELT pipeline with NER-powered skill extraction to transform raw job data into insights on skill demand, salary premiums, hiring companies, and career transitions.

### 🎯 Mission

To democratize access to job market intelligence, enabling individuals to make informed career decisions and organizations to optimize their talent acquisition strategies through data-driven insights.

### 👥 Target Audience

- **Job Seekers**: Discover in-demand skills, salary benchmarks, and career transition opportunities
- **Career Coaches**: Provide data-backed guidance on skill development and career pivots
- **Recruiters**: Identify emerging skill trends and competitive salary ranges
- **Data Analysts**: Explore job market dynamics across roles, skills, and geographies
- **Educators**: Align curriculum with industry demands and emerging technologies

### 🌍 Coverage

Job Script aggregates job postings from the **Adzuna API plus a fleet of multi-source ingestion bots** (RemoteOK, We Work Remotely, Arbeitnow, Jobicy, Himalayas, Jooble, The Muse — see [SCRAPING_BOTS.md](SCRAPING_BOTS.md)), analyzing **15 job roles** spanning Data, AI/ML, Software Development, DevOps/Cloud, and Cybersecurity.

**Job Roles Tracked:** Data Engineer, Analytics Engineer, Data Scientist, Data Analyst, Business Intelligence Developer, Machine Learning Engineer, AI Engineer, Computer Vision Engineer, Backend Developer, Frontend Developer, Full Stack Developer, Mobile Developer, DevOps Engineer, Cloud Architect, Cyber Security Engineer.

**Countries:** 🇬🇧 UK • 🇺🇸 US • 🇦🇺 Australia • 🇦🇹 Austria • 🇧🇪 Belgium • 🇧🇷 Brazil • 🇨🇦 Canada • 🇩🇪 Germany • 🇫🇷 France • 🇮🇳 India • 🇮🇹 Italy • 🇲🇽 Mexico • 🇳🇱 Netherlands • 🇳🇿 New Zealand • 🇵🇰 Pakistan • 🇵🇱 Poland • 🇸🇬 Singapore • 🇿🇦 South Africa • 🌐 Remote/Worldwide (plus 🇷🇺 Russia in the country dimension). Pakistan and the Remote bucket come from the multi-source bots — built specifically so talent in Pakistan/India can use the platform for both local and worldwide-remote roles.

---

## ✨ Key Features

### 📊 **Intelligent Dashboard**
- High-level job market metrics (total jobs, skills tracked, countries, roles, companies)
- Top skills bar chart and skills-by-category breakdown
- Interactive data visualizations with Recharts
- Responsive design with light/dark theme support

### 🔍 **Skills Analysis**
- **Skill Demand Tracking**: Monitor demand for specific skills across roles and countries
- **Demand Over Time**: Track up to 5 skills at once on a line chart — % of postings mentioning each skill by month, so you can see a skill trending up or down (backed by `staging.stg_jobs` posting dates, independent of the archive snapshot cadence)
- **Co-occurrence Analysis**: Discover skill combinations that appear together in job postings (with Jaccard similarity)
- **Skill Connections**: Explore paired skills for a selected skill
- **Geographic Distribution**: Compare skill popularity across different countries

### 💰 **Salary Intelligence**
- **Skill-Based Salary Analysis**: Understand compensation for jobs requiring specific skills vs. the market average
- **Premium Skills Identification**: Identify skills that command the highest salary premiums
- **Top-Paying Skills**: Rank skills by average salary
- **Salary Range**: Min/max/avg salary and market average by role & country

### 🏢 **Company Intelligence**
- **Hiring Leaderboards**: Identify top hiring companies by role and location
- **Contract Type Analysis**: Distribution of full-time / part-time / contract positions
- **Company Search**: Look up specific employers

### 🚀 **Career Pathfinding**
- **Role Similarity Engine**: Find related roles based on overlapping skill sets
- **Career Transition Analysis**: Identify potential career pivots with difficulty ratings derived from skill overlap
- **Skill Gap Identification**: Discover shared skills and skills to learn between two roles
- **Similarity Matrix**: Full role-to-role similarity matrix (heatmap-ready)

### 🗺️ **Global Market Insights**
- Cross-country skill demand comparison for a selected skill
- Job-count-by-country comparison
- Country-level comparison tables

### 📄 **Resume Analyzer**
- **Upload & Parse**: Drag-and-drop upload for PDF, DOCX/DOC, TXT, and (optionally, via OCR) image resumes
- **Skill Extraction**: Extracts skills from resume text using the same taxonomy as the ETL fast path
- **Gap Analysis**: Compares your resume against the demand for a target role — shows skills you have, skills to learn, and a demand-weighted match percentage
- **Role Match**: Scores your resume against every tracked role and ranks the best-fitting roles

### 👤 **Accounts & Personalization** (Supabase Auth)
- **Sign in with email/password or "Continue with Google"** (OAuth) — sessions persist across reloads
- **Personal dashboard defaults**: your preferred role & country are applied automatically on every visit
- **Saved searches**: bookmark any role + country combo from the top bar and re-apply it in one click
- **Resume history**: analyses run while signed in are saved to your account and browsable on the Account page
- Setup guide: [AUTH_SETUP.md](AUTH_SETUP.md)

### 🤖 **Multi-Source Ingestion Bots**
- **7 connector bots** beyond Adzuna: RemoteOK, We Work Remotely (RSS), Arbeitnow, Jobicy, Himalayas (no keys needed), plus Jooble (local 🇵🇰 Pakistan + 🇮🇳 India postings) and The Muse (free keys)
- **Robust by design**: retries with exponential backoff, rate limiting, per-source isolation, idempotent writes, role classification, dry-run mode
- **ToS-compliant**: honest User-Agent, attribution links, robots.txt-aware scraper template — no anti-bot evasion
- Runs automatically every two weeks with the ETL pipeline — full guide: [SCRAPING_BOTS.md](SCRAPING_BOTS.md)

---

## 🛠️ Technology Stack

### **Backend**
- **[FastAPI](https://fastapi.tiangolo.com/)** – High-performance async Python web framework
- **[PostgreSQL](https://www.postgresql.org/)** – Relational database (Supabase hosted)
- **[asyncpg](https://github.com/MagicStack/asyncpg)** – Async PostgreSQL driver (connection pooling)
- **[Pydantic](https://docs.pydantic.dev/)** – Request/response validation and settings
- **[Uvicorn](https://www.uvicorn.org/)** – ASGI server
- **PyPDF2 / python-docx / Pillow** – Resume file parsing (PDF, Word, images)
- **[Supabase Storage](https://supabase.com/storage)** – Resume file storage (optional)
- **[Supabase Auth](https://supabase.com/auth) + PyJWT** – User authentication (JWT verification for personalized endpoints)

### **Frontend**
- **[React 18](https://react.dev/)** – Component-based UI library
- **[Vite](https://vitejs.dev/)** – Frontend build tool and dev server
- **[React Router](https://reactrouter.com/)** – Client-side routing
- **[TanStack React Query](https://tanstack.com/query/)** – Data fetching and caching
- **[Recharts](https://recharts.org/)** – Primary charting library
- **[D3.js](https://d3js.org/)** – Force-directed network graph & similarity heatmap components
- **[Tailwind CSS](https://tailwindcss.com/)** – Utility-first CSS (class-based dark mode)
- **[Lucide React](https://lucide.dev/)** – Icon set
- **[Axios](https://axios-http.com/)** – HTTP client (attaches the Supabase session token automatically)
- **[supabase-js](https://supabase.com/docs/reference/javascript)** – Auth client (email/password + Google OAuth, session persistence)

### **Data Pipeline**
- **[Adzuna API](https://www.adzuna.com/)** – Primary job posting data source (17 countries)
- **Multi-source ingestion bots** (`etl/ingest_sources.py` + `etl/connectors/`) – RemoteOK, We Work Remotely, Arbeitnow, Jobicy, Himalayas, Jooble (local Pakistan/India), The Muse, USAJobs — normalized into one contract and landed in `raw.jobs` with a `source` tag ([SCRAPING_BOTS.md](SCRAPING_BOTS.md))
- **Hybrid Skill Extraction System**:
  - **Fast Path**: Regex/taxonomy pattern matching (majority of skills, instant, free)
  - **Slow Path**: **GLiNER** NER model (`urchade/gliner_medium-v2.1`) for local, free skill discovery
  - **Discovery Manager**: Tracks new discoveries and auto-promotes frequently-seen skills into the taxonomy
- **[psycopg2](https://www.psycopg.org/)** – PostgreSQL driver for the ETL scripts
- **[dbt (dbt-postgres)](https://www.getdbt.com/)** – SQL transformation into analytical marts

### **DevOps & Deployment**
- **[GitHub Actions](https://github.com/features/actions)** – Scheduled ETL orchestration + keep-warm ping
- **[Render](https://render.com/)** – Backend hosting (Python buildpack, no Docker)
- **[Vercel](https://vercel.com/)** – Frontend hosting + `/api` proxy to the backend
- **Scheduled ETL**: Automated data refresh on the 1st and 15th of each month

### **Languages & Tooling**
- **Python 3.11**, **Node.js 18+**, **Git**

---

## 🏗️ Architecture

Job Script follows a **Modern Data Stack (MDS)** approach with an **ELT (Extract, Load, Transform)** pipeline pattern.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         JOB SCRIPT ARCHITECTURE                       │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐   ┌────────────────────────────────────────────┐
│  Adzuna API  │   │ Multi-source bots: RemoteOK · WWR · Jobicy │
│ (17 nations) │   │ Arbeitnow · Himalayas · Jooble 🇵🇰🇮🇳 · Muse │
└──────┬───────┘   └──────────────────────┬─────────────────────┘
       │  (1) EXTRACT                     │
       ▼                                  ▼
┌──────────────────┐          ┌─────────────────────┐
│  extractor.py    │          │  ingest_sources.py  │ ← normalize + classify
└──────┬───────────┘          └──────────┬──────────┘
       │  (2) LOAD (raw JSONB, tagged with `source`)
       ▼
┌────────────────────────────────────────────────────────────────┐
│              PostgreSQL Database (Supabase)                      │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐      │
│  │  raw.jobs   │ → │ staging.*    │ → │   marts.*        │      │
│  │  (JSONB)    │   │ (Normalized) │   │ (Aggregations)   │      │
│  └─────────────┘   └──────────────┘   └──────────────────┘      │
└────────────────────────────────────────────────────────────────┘
       │                        │                       ▲
       │ (3) SKILL EXTRACT      │ (4) TRANSFORM         │
       ▼                        ▼                       │
┌──────────────────────┐  ┌───────────────┐            │
│ transformer.py       │  │  dbt models   │────────────┘
│ - Fast Path (regex)  │  │  - SQL marts  │
│ - Slow Path (GLiNER) │  │  - Analytics  │
│ - Discovery Manager  │  └───────────────┘
└──────────────────────┘
                               │  (5) SERVE
                               ▼
                        ┌──────────────┐
                        │  FastAPI     │ ← REST API (/api/v1, CORS-enabled)
                        │  Backend     │   + Resume Analyzer + /user endpoints
                        └──────┬───────┘   (verifies Supabase Auth JWTs)
                               │  (6) CONSUME
                               ▼
                        ┌──────────────┐   ┌────────────────┐
                        │   React SPA  │ ← │ Supabase Auth  │
                        │              │   │ (email+Google) │
                        └──────┬───────┘   └────────────────┘
                               │  (7) VISUALIZE
                               ▼
                        ┌──────────────┐
                        │   End User   │
                        └──────────────┘
```

### Data Flow Explained

1. **Extract**: `extractor.py` queries the Adzuna API across configured roles × countries, and `ingest_sources.py` runs the multi-source connector bots (remote boards + Jooble for local Pakistan/India postings), normalizing every source into one shared contract.
2. **Load**: Raw JSON is stored in `raw.jobs` (immutable landing zone, JSONB), tagged with its `source`.
3. **Skill Extraction**: `transformer.py` flattens raw jobs into `staging.stg_jobs` and extracts skills into `staging.stg_job_skills` using the hybrid extractor:
   - **Fast Path**: regex matching against the skills taxonomy (instant, free).
   - **Slow Path**: the **GLiNER** NER model discovers skills not yet in the taxonomy (local, free, sampled). *Note: the scheduled CI pipeline runs in `--fast-only` mode, so GLiNER runs only during local/manual discovery runs.*
4. **Transform**: dbt builds analytical marts (demand, salary, co-occurrence, company leaderboard, role similarity, skills-by-country).
5. **Serve**: FastAPI exposes REST endpoints that query the dbt marts (and, for the resume feature, the staging tables).
6. **Consume**: The React app fetches data via the API using React Query. Signed-in users (Supabase Auth: email/password or Google) get personalized features — the session token is attached to API calls automatically.
7. **Visualize**: Interactive charts, tables, and network/heatmap components — plus a personal Account page (saved searches, resume history, dashboard defaults).

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11** ([Download](https://www.python.org/downloads/))
- **Node.js 18+** ([Download](https://nodejs.org/))
- **PostgreSQL 15+** or a **Supabase account** ([Sign up](https://supabase.com/))
- **Git** ([Download](https://git-scm.com/))

### Installation

#### 1️⃣ Clone the Repository

```bash
git clone https://github.com/yourusername/job-script.git
cd job-script
```

#### 2️⃣ Set Up the Database

```bash
cd database
# Run schema creation against your Supabase/Postgres instance
psql "$SUPABASE_URL" -f schema.sql
# For the Resume Analyzer's upload metadata table:
psql "$SUPABASE_URL" -f Resume_upload.sql
# (Or paste the SQL into the Supabase SQL editor)
```

#### 3️⃣ Set Up the Backend

```bash
cd ../backend

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

**Backend environment variables** (via environment or a `.env` file):
```env
# Database (required) - Postgres connection string
SUPABASE_URL=postgresql://user:password@host:port/database

# CORS (comma-separated origins)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Optional - Resume file storage (Supabase Storage)
SUPABASE_PROJECT_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>

# Application
DEBUG=true
CACHE_TTL_SECONDS=3600
API_PREFIX=/api/v1
```

#### 4️⃣ Set Up the Frontend

```bash
cd ../frontend
npm install

# Create .env (see .env.example)
echo "VITE_API_URL=http://localhost:8000/api/v1" > .env
```

#### 5️⃣ Configure & Run dbt

```bash
cd ../dbt_project
cp profiles.yml.example profiles.yml   # then edit with your DB credentials
# (dbt reads DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME env vars)

dbt deps
dbt run --target prod
dbt test
```

#### 6️⃣ Run the ETL Pipeline (Optional – for fresh data)

```bash
cd ../etl
pip install -r requirements.txt
# GLiNER discovery is optional: pip install gliner

# Set ADZUNA_APP_ID, ADZUNA_APP_KEY, SUPABASE_URL in your environment/.env

# Extract (test mode = 1 role, 1 country)
python extractor.py --test

# Extract a real window (used by CI): last 60 days, 3 pages/search
python extractor.py --days 60 --pages 3 --delay 1.5

# Extract skills (fast/taxonomy only, no GLiNER)
python transformer.py --batch-size 500 --fast-only

# Rebuild marts
cd ../dbt_project && dbt run --full-refresh
```

### Running the Application

**Backend**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health

**Frontend**
```bash
cd frontend
npm run dev
```
- App: http://localhost:5173 (Vite proxies `/api` → `http://localhost:8000`)

---

## 📖 Usage

1. **Dashboard** (`/`) – High-level market stats, top skills, and skills-by-category charts. Use the sidebar **Role** and **Country** filters to scope every page. **Click any skill in the "Skill Demand Breakdown" table** to drill into the actual job postings for it.
2. **Skills Analysis** (`/skills`) – "Top Skills" and "Skill Connections" tabs; view demand charts, category breakdown, and co-occurring skills with Jaccard similarity. Each skill's job count links to its postings.
3. **Job Postings** (`/jobs`) – Drill-down screen listing the real postings that mention a chosen skill (title, company, location, salary, apply link). The role's top skills are highlighted in each description, with the clicked skill highlighted in a distinct colour.
4. **Salary** (`/salary`) – Highest salary premiums, top-paying skills, full salary comparison table, and insight cards.
5. **Companies** (`/companies`) – Top hiring companies, contract-type distribution, and company details.
6. **Career Paths** (`/career`) – Pick a current role to see similar roles, transition difficulty, and skill gaps.
7. **Global** (`/global`) – Compare a skill's demand and job counts across countries.
8. **Resume Analyzer** (`/resume`) – Upload a resume, then run **Gap Analysis** (against a target role) or **Role Match** (ranked best-fit roles).

---

## 📚 API Documentation

All data endpoints are served under the base path **`/api/v1`**.

### Base URL
- Local: `http://localhost:8000/api/v1`
- Production: `https://skill-hunt.onrender.com/api/v1`

### Authentication

Analytics endpoints are open. **Personalized endpoints (`/user/*`) require a Supabase Auth session token** (`Authorization: Bearer <access_token>`), and the resume endpoints accept one optionally — analyses run while signed in are linked to the account. The frontend attaches the token automatically; the backend verifies it locally with `SUPABASE_JWT_SECRET` (or remotely via the Supabase Auth API). Setup: [AUTH_SETUP.md](AUTH_SETUP.md).

### Root & Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API metadata (name, version, links) |
| GET | `/health` | Health check (runs `SELECT 1`; reports DB status) |
| GET | `/api/v1` | API version + endpoint map |

#### **Skills** (`/api/v1/skills`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/skills/demand` | Skill demand by role (optional country) |
| GET | `/skills/demand/all` | All skills demand |
| GET | `/skills/trend` | **Demand over time** — % of postings mentioning each skill, by month posted, for up to 5 skills (`skills`, optional `role`/`country`, `months`) |
| GET | `/skills/cooccurrence` | Skill co-occurrence pairs |
| GET | `/skills/network` | Skill network graph data (D3 nodes/links) |
| GET | `/skills/by-country` | Compare a skill across countries |
| GET | `/skills/jobs` | **Real job postings mentioning a skill** (drill-down) — returns each posting + the role's top skills to highlight |
| GET | `/skills/categories` | List skill categories |
| GET | `/skills/list` | List skills (optional category filter) |

#### **Salary** (`/api/v1/salary`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/salary/by-skill` | Salary stats by skill vs. market |
| GET | `/salary/top-paying-skills` | Highest average-salary skills |
| GET | `/salary/premium-skills` | Skills with the highest salary premium |
| GET | `/salary/range` | Min/max/avg + market-avg salary |

#### **Companies** (`/api/v1/companies`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/companies/leaderboard` | Top hiring companies |
| GET | `/companies/contract-types` | Contract-type distribution |
| GET | `/companies/search` | Search companies by name |

#### **Career** (`/api/v1/career`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/career/role-similarity` | All role similarities |
| GET | `/career/transitions/{current_role}` | Transitions for a role |
| GET | `/career/similarity-matrix` | Role similarity matrix (heatmap) |
| GET | `/career/skill-gap` | Skill gap between two roles (`from_role`, `to_role`) |

#### **Stats** (`/api/v1/stats`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats/summary` | Dashboard summary statistics |
| GET | `/stats/filters` | Available filter options |
| GET | `/stats/roles` | Available roles |
| GET | `/stats/countries` | Available countries |

#### **Resume** (`/api/v1/resume`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/resume/extract-skills` | Extract skills from an uploaded resume file |
| POST | `/resume/analyze` | Gap analysis vs. a `target_role` (multipart: file + form fields; linked to your account when signed in) |
| POST | `/resume/match-roles` | Rank best-fitting roles for the resume (linked to your account when signed in) |
| GET | `/resume/supported-roles` | Roles available for matching |

#### **User** (`/api/v1/user`) — 🔐 requires sign-in

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/user/me` | Current user's profile + dashboard defaults |
| PUT | `/user/me` | Update display name / default role / default country |
| GET | `/user/saved-searches` | List saved searches |
| POST | `/user/saved-searches` | Save a search (name, role, country) |
| DELETE | `/user/saved-searches/{id}` | Delete a saved search |
| GET | `/user/resume-history` | Past resume analyses for this account |
| DELETE | `/user/resume-history/{id}` | Delete one of your analyses |

### Example API Calls

#### Get Skill Demand
```bash
curl "http://localhost:8000/api/v1/skills/demand?role=Data%20Engineer&limit=10"
```

**Response** (`SkillDemandResponse`):
```json
{
  "role": "Data Engineer",
  "country": null,
  "total_count": 10,
  "data": [
    {
      "skill_name": "Python",
      "skill_category": "Programming Language",
      "search_role": "Data Engineer",
      "country_code": null,
      "job_count": 980,
      "demand_percentage": 78.5,
      "avg_salary_min": 55000,
      "avg_salary_max": 85000,
      "avg_salary_midpoint": 70000,
      "rank_in_role_country": null,
      "rank_in_role_global": 1
    }
  ]
}
```

#### Get Skill Demand Trend
```bash
curl "http://localhost:8000/api/v1/skills/trend?skills=Python,SQL,AWS&role=Data%20Engineer&months=6"
```

**Response** (`SkillTrendResponse`) — one point per month per skill, as a share of that month's postings (comparable across months even when extraction volume varies; raw counts aren't):
```json
{
  "role": "Data Engineer",
  "country": null,
  "months": 6,
  "interval": "month",
  "periods": [
    { "period": "2025-11-01", "total_jobs": 72 },
    { "period": "2025-12-01", "total_jobs": 460 }
  ],
  "series": [
    {
      "skill_name": "Python",
      "points": [
        { "period": "2025-11-01", "job_count": 7, "demand_percentage": 9.72 },
        { "period": "2025-12-01", "job_count": 81, "demand_percentage": 17.61 }
      ]
    }
  ]
}
```

#### Analyze a Resume (Gap Analysis)
```bash
curl -X POST "http://localhost:8000/api/v1/resume/analyze" \
  -F "file=@resume.pdf" \
  -F "target_role=Data Engineer" \
  -F "country=gb"
```

For full interactive docs, visit: `/docs`.

---

## 🔄 Data Pipeline

### Schedule

The ETL pipeline runs automatically via GitHub Actions (`.github/workflows/etl_pipeline.yml`) on a **cron of `0 3 1,15 * *`** — the **1st and 15th of each month at 03:00 UTC** — and can also be triggered manually via `workflow_dispatch`. A separate `keep_warm.yml` workflow pings the backend `/health` endpoint every 5 minutes to keep the Render service warm.

### Pipeline Stages (GitHub Actions jobs)

#### 1. **Extract** (`etl/extractor.py` + `etl/ingest_sources.py`)
- **Adzuna** (`extractor.py`): queries the Adzuna API across the configured roles × countries. Extraction config (`etl/config/extraction_config.json`): 15 roles, 17 countries, 50 results/page, 2 pages/search default. CI overrides with `--days 60 --pages 3 --delay 1.5`.
- **Multi-source bots** (`ingest_sources.py` — runs in the same CI job): RemoteOK, We Work Remotely, Arbeitnow, Jobicy, Himalayas (keyless) + Jooble (local 🇵🇰/🇮🇳) and The Muse (free keys). Each connector normalizes its source into one shared contract, classifies titles into the 15 tracked roles, and strips HTML. Config: `etl/config/sources_config.json`. Full guide: [SCRAPING_BOTS.md](SCRAPING_BOTS.md).
- Both store raw JSON in `raw.jobs` (tagged with `source`); deduplicates on `(job_platform_id, country_code)` via `ON CONFLICT DO NOTHING` — non-Adzuna IDs are namespaced `<source>:<id>`.
- Rate-limit aware (HTTP 429 backoff, per-source delays, automatic retries).

#### 2. **Transform & Extract Skills** (`etl/transformer.py`)
- Flattens `raw.jobs` → `staging.stg_jobs`, then extracts skills → `staging.stg_job_skills`.
- **Hybrid extraction system**:
  - **Fast Path**: pre-compiled regex against the taxonomy (~430 skills, aliases, special-cased tokens like `C++`/`C#`/`.NET`). Instant and free.
  - **Slow Path (GLiNER)**: `urchade/gliner_medium-v2.1` NER model discovers skills not in the taxonomy. Runs locally, no API cost, sampled (~10%). **Disabled in CI** (`--fast-only`).
  - **Discovery Manager**: tracks unverified discoveries; auto-promotes a skill to the taxonomy JSON (and `dim_skills`) once it reaches ≥3 occurrences with ≥0.75 average confidence.

#### 3. **Fetch Currency Rates** (`etl/fetch_currency_rates.py`)
- Fetches live currency→USD exchange rates from [frankfurter.dev](https://frankfurter.dev) (ECB rates, free, no key) for whatever currencies are actually present in the data, and upserts into `staging.currency_rates`. Self-healing: an unreachable API or uncovered currency leaves the previous cached rate untouched rather than guessing.
- ⚠️ **One-time setup**: run [`database/migrations/004_currency_rates.sql`](database/migrations/004_currency_rates.sql) once (Supabase SQL Editor) to create the table, then `python etl/fetch_currency_rates.py` to populate it. Without this, single-currency salary figures (native or USD) still work, but cross-country comparisons will fall back to whatever rates are already cached (or `NULL` before the first fetch).
- **Why this exists**: every mart groups salary by `(role, country)` — currency-safe within a row — but the API blends rows *across* countries for the "All Countries" view. Without conversion, that blend averaged raw native-currency numbers as if they were the same unit (e.g. an Indian salary in the millions of INR averaged against a US salary in the tens of thousands of USD), inflating some skills' reported average salary into the hundreds of thousands of dollars. See IMPLEMENTATION.md §6.7 for the full root-cause writeup.

#### 4. **Transform** (`dbt_project/`)
- **Intermediate** (`models/intermediate/`, materialized as a `view` in `staging`):
  - `int_job_skills_enriched.sql` — joins skills × jobs × skill dimension, computes salary midpoint (native + USD-normalized via `currency_rates`), filters to jobs posted in the last 60 days.
- **Marts** (`models/marts/`, materialized as `table` in `marts`):
  - `mart_skill_demand.sql` — top skills per role/country with demand % and ranks, native + USD salary averages
  - `mart_salary_by_skill.sql` — salary stats & premium vs. market (min 5 jobs), native + USD
  - `mart_skills_by_country.sql` — skill demand compared across countries
  - `mart_skill_cooccurrence.sql` — skill pairs with Jaccard + conditional probabilities
  - `mart_company_leaderboard.sql` — top hiring companies with contract breakdown, native + USD salary averages
  - `mart_role_similarity.sql` — role skill overlap (Jaccard, overlap, dice)

#### 5. **Archive & Notify**
- `archive` job (scheduled runs only) calls the `archive_skill_demand()` Postgres function to snapshot demand into `archive.skill_demand_history`.
- ⚠️ **One-time fix required**: this function originally read from an always-empty placeholder table, so the archive was silently never populated. Run [`database/migrations/003_fix_archive_snapshots.sql`](database/migrations/003_fix_archive_snapshots.sql) once (Supabase SQL Editor) to repoint it at the real mart and take the first snapshot — it's idempotent and safe alongside migrations 001/002/004 if you're setting those up too. Not required for the `/skills/trend` chart, which reads live posting data instead; it only matters if you want the historical archive itself to start accumulating.
- `notify` job reports the status of all jobs.

#### 6. **Serve**
- FastAPI queries the marts (and the staging tables for the resume feature). Marts are pre-computed by dbt, so responses are served directly. (`CACHE_TTL_SECONDS` is configured for future response caching but is not yet applied.)

### Running ETL Manually

**One-command full refresh** (snapshot → Adzuna extract → multi-source ingest → transform → fetch currency rates → dbt rebuild → snapshot). This is the recommended way to bring the dashboard fully up to date across all sources:

```bash
cd etl
python refresh_all.py                 # full refresh (derives dbt creds from SUPABASE_URL)
python refresh_all.py --dry-run       # print the plan, run nothing
python refresh_all.py --skip-adzuna   # only multi-source + transform + fx + dbt
```

This runs the same *stages*, in the same order, as the scheduled CI pipeline (`.github/workflows/etl_pipeline.yml`) — but it is a separate script, not a wrapper around it. CI runs each stage as its own GitHub Actions job with its own checkout/secrets; keep both in sync by hand if the pipeline shape changes.

Or run the individual stages:

```bash
cd etl
python extractor.py --days 60 --pages 3 --delay 1.5   # extract (Adzuna)
python ingest_sources.py                                # extract (multi-source bots)
python transformer.py --batch-size 500 --fast-only     # extract skills (taxonomy only)
python fetch_currency_rates.py                          # live FX rates for salary normalization
cd ../dbt_project && dbt run --profiles-dir . --target dev --full-refresh   # rebuild staging_marts.*

# Test / preview modes
python extractor.py --test
python ingest_sources.py --test --dry-run               # fetch samples, write nothing
python fetch_currency_rates.py --dry-run                # fetch + print, no DB write
```

> **Note:** the marts the API reads are `staging_marts.*`, produced by dbt's **`dev`** target (schema `staging` + the models' `marts` config → `staging_marts`). `refresh_all.py` handles this — and routes the long-running transform through Supabase's **session** pooler (port 5432) so the connection isn't dropped mid-run. Order matters: fresh data must land *before* the dbt rebuild (marts only keep postings from the last 60 days), and fresh FX rates must land before the rebuild too (salary conversion happens at dbt build time).

> **Re-verifying a fix and the numbers look stale?** Check for an orphaned `uvicorn`/`vite` process from an earlier session still bound to the port — Python doesn't hot-reload without `--reload`, so an old process keeps serving old query logic forever, even after the code and database are both correct. `Get-NetTCPConnection -LocalPort 8000 -State Listen` (PowerShell) or `lsof -i :8000` (Unix) to check.

---

## 🚢 Deployment

### Backend (Render) — `render.yaml`

- **Root directory**: `backend`
- **Build**: `pip install -r backend/requirements.txt` (Python buildpack, no Docker)
- **Start**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path**: `/health`
- **Environment variables**: `SUPABASE_URL` (set manually), `CORS_ORIGINS`, `DEBUG`, `CACHE_TTL_SECONDS`, plus for auth: `SUPABASE_JWT_SECRET` (recommended) or `SUPABASE_PROJECT_URL` + `SUPABASE_ANON_KEY` (see [AUTH_SETUP.md](AUTH_SETUP.md))
- Auto-deploys on push.

### Frontend (Vercel) — `vercel.json`

- Static build of `frontend/` (`@vercel/static-build`, `distDir: dist`).
- Routes: `/api/*` is proxied to the Render backend (`https://skill-hunt.onrender.com/api/*`); all other routes serve the SPA.
- `VITE_API_URL` set via Vercel env (`@vite_api_url`); auth additionally needs `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` (Vercel project env vars — see [AUTH_SETUP.md](AUTH_SETUP.md)). SPA client-side routing is handled by `frontend/vercel.json`.

### Database (Supabase)

- Managed PostgreSQL with connection pooling (PgBouncer; the API disables the asyncpg statement cache for transaction-mode pooling).
- Optional Supabase Storage bucket (`resumes`) for uploaded resume files.
- **Supabase Auth** for user accounts (email/password + Google OAuth) — user tables (`user_profiles`, `saved_searches`) live in `public` with Row-Level Security; migrations in `database/migrations/`.

---

## 🤝 Contributing

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Commit**: `git commit -m 'feat: add amazing feature'`
5. **Push**: `git push origin feature/amazing-feature`
6. **Open a Pull Request**

### Code Style
- **Python**: PEP 8, Black formatter
- **JavaScript/React**: ESLint (config in `frontend`)
- **SQL/dbt**: CTEs, lowercase keywords, 2-space indentation

---

## 📄 License

Released under the **MIT License**. (No `LICENSE` file is currently committed — add one before public distribution.)

---

## 🙏 Acknowledgments

- **Adzuna** for the job posting API
- **Supabase** for managed PostgreSQL & storage
- **dbt Labs** for the transformation framework
- **GLiNER** (`urchade/gliner_medium-v2.1`) for local NER-based skill discovery
- **FastAPI** and the **React** ecosystem

---

## 🗺️ Roadmap

- [x] User authentication and personalized dashboards (Supabase Auth + Google OAuth, saved searches, resume history) ✅
- [x] Expanded data sources beyond Adzuna (multi-source ingestion bots — RemoteOK, WWR, Jooble PK/IN, and more) ✅
- [x] Resume skill gap analysis & role matching ✅
- [x] Skill demand trend over time (`/skills/trend`, multi-series line chart) ✅
- [x] CVD-validated, theme-aware chart palette with fixed category colors across the app ✅
- [x] Cross-country currency normalization for salary comparisons (live FX rates, dynamic — see IMPLEMENTATION.md §6.7) ✅
- [ ] Native-currency salary display per country (today all figures are shown in USD everywhere, by design — see §6.7)
- [ ] Email alerts for saved searches (the `saved_searches` table is the subscription list)
- [ ] API rate limiting (per-user, using the verified identity)
- [ ] Response-level caching (`CACHE_TTL_SECONDS` is already wired for it)
- [ ] Automated test suite (backend + frontend)
- [ ] Cross-source job deduplication (content hash on title+company+country)
- [ ] Machine-learning-based salary prediction
- [ ] Export reports (PDF, CSV)

---

<div align="center">

**Built with ❤️ — Job Script**

⭐ Star the repo if you find it useful!

</div>
