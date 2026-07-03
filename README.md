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

📖 Deep dives: [Implementation Guide](IMPLEMENTATION.md) • [Scraping Bots / Multi-Source Ingestion](SCRAPING_BOTS.md)

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

Job Script aggregates job postings via the **Adzuna API**, analyzing **15 job roles** spanning Data, AI/ML, Software Development, DevOps/Cloud, and Cybersecurity across up to **18 countries** (17 currently active in the extraction config).

**Job Roles Tracked:** Data Engineer, Analytics Engineer, Data Scientist, Data Analyst, Business Intelligence Developer, Machine Learning Engineer, AI Engineer, Computer Vision Engineer, Backend Developer, Frontend Developer, Full Stack Developer, Mobile Developer, DevOps Engineer, Cloud Architect, Cyber Security Engineer.

**Countries:** 🇬🇧 UK • 🇺🇸 US • 🇦🇺 Australia • 🇦🇹 Austria • 🇧🇪 Belgium • 🇧🇷 Brazil • 🇨🇦 Canada • 🇩🇪 Germany • 🇫🇷 France • 🇮🇳 India • 🇮🇹 Italy • 🇲🇽 Mexico • 🇳🇱 Netherlands • 🇳🇿 New Zealand • 🇵🇱 Poland • 🇸🇬 Singapore • 🇿🇦 South Africa (plus 🇷🇺 Russia in the country dimension).

---

## ✨ Key Features

### 📊 **Intelligent Dashboard**
- High-level job market metrics (total jobs, skills tracked, countries, roles, companies)
- Top skills bar chart and skills-by-category breakdown
- Interactive data visualizations with Recharts
- Responsive design with light/dark theme support

### 🔍 **Skills Analysis**
- **Skill Demand Tracking**: Monitor demand for specific skills across roles and countries
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

### **Frontend**
- **[React 18](https://react.dev/)** – Component-based UI library
- **[Vite](https://vitejs.dev/)** – Frontend build tool and dev server
- **[React Router](https://reactrouter.com/)** – Client-side routing
- **[TanStack React Query](https://tanstack.com/query/)** – Data fetching and caching
- **[Recharts](https://recharts.org/)** – Primary charting library
- **[D3.js](https://d3js.org/)** – Force-directed network graph & similarity heatmap components
- **[Tailwind CSS](https://tailwindcss.com/)** – Utility-first CSS (class-based dark mode)
- **[Lucide React](https://lucide.dev/)** – Icon set
- **[Axios](https://axios-http.com/)** – HTTP client

### **Data Pipeline**
- **[Adzuna API](https://www.adzuna.com/)** – Job posting data source
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

┌──────────────┐
│  Adzuna API  │  ← External Data Source (multi-country)
└──────┬───────┘
       │  (1) EXTRACT
       ▼
┌──────────────────┐
│  extractor.py    │  ← Python (batched, rate-limited) → raw.jobs
└──────┬───────────┘
       │  (2) LOAD (raw JSONB)
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
                        │  Backend     │   + Resume Analyzer endpoints
                        └──────┬───────┘
                               │  (6) CONSUME
                               ▼
                        ┌──────────────┐
                        │   React SPA  │ ← Vite + React Router + React Query
                        └──────┬───────┘
                               │  (7) VISUALIZE
                               ▼
                        ┌──────────────┐
                        │   End User   │
                        └──────────────┘
```

### Data Flow Explained

1. **Extract**: `extractor.py` queries the Adzuna API across configured roles × countries.
2. **Load**: Raw JSON is stored in `raw.jobs` (immutable landing zone, JSONB).
3. **Skill Extraction**: `transformer.py` flattens raw jobs into `staging.stg_jobs` and extracts skills into `staging.stg_job_skills` using the hybrid extractor:
   - **Fast Path**: regex matching against the skills taxonomy (instant, free).
   - **Slow Path**: the **GLiNER** NER model discovers skills not yet in the taxonomy (local, free, sampled). *Note: the scheduled CI pipeline runs in `--fast-only` mode, so GLiNER runs only during local/manual discovery runs.*
4. **Transform**: dbt builds analytical marts (demand, salary, co-occurrence, company leaderboard, role similarity, skills-by-country).
5. **Serve**: FastAPI exposes REST endpoints that query the dbt marts (and, for the resume feature, the staging tables).
6. **Consume**: The React app fetches data via the API using React Query.
7. **Visualize**: Interactive charts, tables, and network/heatmap components.

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
The API is currently open (no authentication required).

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
| POST | `/resume/analyze` | Gap analysis vs. a `target_role` (multipart: file + form fields) |
| POST | `/resume/match-roles` | Rank best-fitting roles for the resume |
| GET | `/resume/supported-roles` | Roles available for matching |

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

#### 1. **Extract** (`etl/extractor.py`)
- Queries the Adzuna API for job postings across the configured roles × countries.
- Extraction config (`etl/config/extraction_config.json`): 15 roles, 17 countries, 50 results/page, 2 pages/search default. CI overrides with `--days 60 --pages 3 --delay 1.5`.
- Stores raw JSON in `raw.jobs`; deduplicates on `(job_platform_id, country_code)` via `ON CONFLICT DO NOTHING`.
- Rate-limit aware (handles HTTP 429 with backoff).

#### 2. **Transform & Extract Skills** (`etl/transformer.py`)
- Flattens `raw.jobs` → `staging.stg_jobs`, then extracts skills → `staging.stg_job_skills`.
- **Hybrid extraction system**:
  - **Fast Path**: pre-compiled regex against the taxonomy (~430 skills, aliases, special-cased tokens like `C++`/`C#`/`.NET`). Instant and free.
  - **Slow Path (GLiNER)**: `urchade/gliner_medium-v2.1` NER model discovers skills not in the taxonomy. Runs locally, no API cost, sampled (~10%). **Disabled in CI** (`--fast-only`).
  - **Discovery Manager**: tracks unverified discoveries; auto-promotes a skill to the taxonomy JSON (and `dim_skills`) once it reaches ≥3 occurrences with ≥0.75 average confidence.

#### 3. **Transform** (`dbt_project/`)
- **Intermediate** (`models/intermediate/`, materialized as a `view` in `staging`):
  - `int_job_skills_enriched.sql` — joins skills × jobs × skill dimension, computes salary midpoint, filters to jobs posted in the last 60 days.
- **Marts** (`models/marts/`, materialized as `table` in `marts`):
  - `mart_skill_demand.sql` — top skills per role/country with demand % and ranks
  - `mart_salary_by_skill.sql` — salary stats & premium vs. market (min 5 jobs)
  - `mart_skills_by_country.sql` — skill demand compared across countries
  - `mart_skill_cooccurrence.sql` — skill pairs with Jaccard + conditional probabilities
  - `mart_company_leaderboard.sql` — top hiring companies with contract breakdown
  - `mart_role_similarity.sql` — role skill overlap (Jaccard, overlap, dice)

#### 4. **Archive & Notify**
- `archive` job (scheduled runs only) calls the `archive_skill_demand()` Postgres function to snapshot demand into `archive.skill_demand_history`.
- `notify` job reports the status of all jobs.

#### 5. **Serve**
- FastAPI queries the marts (and the staging tables for the resume feature). Marts are pre-computed by dbt, so responses are served directly. (`CACHE_TTL_SECONDS` is configured for future response caching but is not yet applied.)

### Running ETL Manually

```bash
cd etl
python extractor.py --days 60 --pages 3 --delay 1.5   # extract
python transformer.py --batch-size 500 --fast-only     # extract skills (taxonomy only)
cd ../dbt_project && dbt run --full-refresh             # rebuild marts

# Test mode
python extractor.py --test
```

---

## 🚢 Deployment

### Backend (Render) — `render.yaml`

- **Root directory**: `backend`
- **Build**: `pip install -r backend/requirements.txt` (Python buildpack, no Docker)
- **Start**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path**: `/health`
- **Environment variables**: `SUPABASE_URL` (set manually), `CORS_ORIGINS`, `DEBUG`, `CACHE_TTL_SECONDS`
- Auto-deploys on push.

### Frontend (Vercel) — `vercel.json`

- Static build of `frontend/` (`@vercel/static-build`, `distDir: dist`).
- Routes: `/api/*` is proxied to the Render backend (`https://skill-hunt.onrender.com/api/*`); all other routes serve the SPA.
- `VITE_API_URL` set via Vercel env (`@vite_api_url`). SPA client-side routing is handled by `frontend/vercel.json`.

### Database (Supabase)

- Managed PostgreSQL with connection pooling (PgBouncer; the API disables the asyncpg statement cache for transaction-mode pooling).
- Optional Supabase Storage bucket (`resumes`) for uploaded resume files.

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

- [ ] User authentication and personalized dashboards
- [ ] API rate limiting and authentication
- [ ] Response-level caching (`CACHE_TTL_SECONDS` is already wired for it)
- [ ] Automated test suite (backend + frontend)
- [ ] Machine-learning-based salary prediction
- [ ] Expanded data sources beyond Adzuna
- [ ] Export reports (PDF, CSV)
- [x] Resume skill gap analysis & role matching ✅

---

<div align="center">

**Built with ❤️ — Job Script**

⭐ Star the repo if you find it useful!

</div>
