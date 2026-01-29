# 🎯 Skill Hunt

> **Data-Driven Job Market Intelligence Platform**  
> Uncover skill trends, salary insights, and career opportunities through advanced analytics and AI-powered data extraction.

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2+-61DAFB.svg)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://www.postgresql.org/)
[![dbt](https://img.shields.io/badge/dbt-1.7+-FF694B.svg)](https://www.getdbt.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Live Demo](#) • [Documentation](#) • [API Docs](http://localhost:8000/docs)

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

**Skill Hunt** is an enterprise-grade job market analysis platform that empowers professionals, recruiters, and organizations with actionable intelligence derived from millions of job postings worldwide. By combining cutting-edge data engineering practices with AI-driven skill extraction, Skill Hunt transforms raw job market data into strategic career insights.

### 🎯 Mission

To democratize access to job market intelligence, enabling individuals to make informed career decisions and organizations to optimize their talent acquisition strategies through data-driven insights.

### 👥 Target Audience

- **Job Seekers**: Discover in-demand skills, salary benchmarks, and career transition opportunities
- **Career Coaches**: Provide data-backed guidance on skill development and career pivots
- **Recruiters**: Identify emerging skill trends and competitive salary ranges
- **Data Analysts**: Explore job market dynamics across roles, skills, and geographies
- **Educators**: Align curriculum with industry demands and emerging technologies

### 🌍 Global Coverage

Skill Hunt aggregates job postings from **18 countries** across 6 continents, analyzing **15+ job roles** spanning Data Engineering, AI/ML, Software Development, DevOps, and Cybersecurity.

**Supported Countries:**
- 🇬🇧 United Kingdom
- 🇺🇸 United States
- 🇦🇺 Australia
- 🇨🇦 Canada
- 🇩🇪 Germany
- 🇫🇷 France
- 🇮🇳 India
- 🇸🇬 Singapore
- And 10 more...

---

## ✨ Key Features

### 📊 **Intelligent Dashboard**
- Real-time job market health metrics
- Trending skills and emerging technologies
- Interactive data visualizations with Recharts
- Responsive design optimized for all devices

### 🔍 **Skills Analysis**
- **Skill Demand Tracking**: Monitor demand for specific skills across roles and countries
- **Co-occurrence Analysis**: Discover skill combinations that appear together in job postings
- **Skill Network Visualization**: Interactive D3.js network graphs showing skill relationships
- **Geographic Distribution**: Compare skill popularity across different countries
- **Trend Analysis**: Track skill growth and decline over time

### 💰 **Salary Intelligence**
- **Skill-Based Salary Analysis**: Understand compensation ranges for specific skill sets
- **Premium Skills Identification**: Identify skills that command the highest salary premiums
- **Role Comparison**: Compare salary ranges across different job roles
- **Location-Based Insights**: Analyze geographic salary variations

### 🏢 **Company Intelligence**
- **Hiring Leaderboards**: Identify top hiring companies by role and location
- **Contract Type Analysis**: Understand distribution of permanent vs. contract positions
- **Company Skill Requirements**: Discover specific skills sought by leading employers

### 🚀 **Career Pathfinding**
- **Role Similarity Engine**: Find related roles based on overlapping skill sets
- **Career Transition Analysis**: Identify potential career pivots with minimal retraining
- **Skill Gap Identification**: Discover missing skills needed for career advancement
- **Career Trajectory Mapping**: Visualize career progression pathways

### 🗺️ **Global Market Insights**
- Cross-country skill demand comparison
- Regional technology adoption patterns
- Geographic salary disparities
- Market saturation indicators

---

## 🛠️ Technology Stack

Skill Hunt leverages a modern, production-ready technology stack designed for scalability, maintainability, and performance.

### **Backend**
- **[FastAPI](https://fastapi.tiangolo.com/)** - High-performance async Python web framework
- **[PostgreSQL](https://www.postgresql.org/)** - Robust relational database (Supabase hosted)
- **[dbt (Data Build Tool)](https://www.getdbt.com/)** - SQL-based data transformation framework
- **[Pydantic](https://docs.pydantic.dev/)** - Data validation and settings management
- **[Uvicorn](https://www.uvicorn.org/)** - Lightning-fast ASGI server

### **Frontend**
- **[React 18](https://react.dev/)** - Modern component-based UI library
- **[Vite](https://vitejs.dev/)** - Next-generation frontend build tool
- **[React Router](https://reactrouter.com/)** - Declarative routing for React
- **[Recharts](https://recharts.org/)** - Composable charting library
- **[D3.js](https://d3js.org/)** - Data-driven visualizations and network graphs
- **[Tailwind CSS](https://tailwindcss.com/)** - Utility-first CSS framework
- **[Lucide React](https://lucide.dev/)** - Beautiful, consistent icon set

### **Data Pipeline**
- **[Adzuna API](https://www.adzuna.com/)** - Real-time job posting data source
- **Hybrid Skill Extraction System**:
  - **Fast Path**: Regex-based pattern matching (95% coverage, instant)
  - **Slow Path**: Google Gemini Flash LLM for skill discovery
  - **Discovery Manager**: Automated skill taxonomy enrichment
- **[psycopg2](https://www.psycopg.org/)** - PostgreSQL adapter for Python

### **DevOps & Deployment**
- **[GitHub Actions](https://github.com/features/actions)** - CI/CD automation
- **[Docker](https://www.docker.com/)** - Containerization
- **[Render](https://render.com/)** - Backend hosting
- **[Vercel](https://vercel.com/)** - Frontend hosting
- **Scheduled ETL**: Automated data refresh (twice weekly)

### **Development Tools**
- **Python 3.10+** - Core programming language
- **Node.js 18+** - JavaScript runtime
- **Git** - Version control
- **VS Code** - Recommended IDE

---

## 🏗️ Architecture

Skill Hunt follows a **Modern Data Stack (MDS)** approach with an **ELT (Extract, Load, Transform)** pipeline pattern.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SKILL HUNT ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│  Adzuna API  │  ← External Data Source (18 Countries)
└──────┬───────┘
       │
       │ (1) EXTRACT
       │
       ▼
┌──────────────────┐
│  extractor.py    │  ← Python Script (Batch Extraction)
└──────┬───────────┘
       │
       │ (2) LOAD
       │
       ▼
┌────────────────────────────────────────────────────────────────┐
│              PostgreSQL Database (Supabase)                     │
│                                                                 │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐   │
│  │  raw.jobs   │ → │ staging.*    │ → │   marts.*        │   │
│  │  (JSONB)    │   │ (Normalized) │   │ (Aggregations)   │   │
│  └─────────────┘   └──────────────┘   └──────────────────┘   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
       │                        │                       ▲
       │ (3) SKILL EXTRACT      │ (4) TRANSFORM         │
       │                        │                       │
       ▼                        ▼                       │
┌──────────────────┐    ┌───────────────┐              │
│ transformer.py   │    │  dbt models   │──────────────┘
│ - Fast Path      │    │  - SQL marts  │
│ - Slow Path LLM  │    │  - Analytics  │
│ - Discovery Mgr  │    └───────────────┘
└──────────────────┘
                               │
                               │ (5) SERVE
                               │
                               ▼
                        ┌──────────────┐
                        │  FastAPI     │ ← REST API (CORS-enabled)
                        │  Backend     │
                        └──────┬───────┘
                               │
                               │ (6) CONSUME
                               │
                               ▼
                        ┌──────────────┐
                        │   React      │ ← SPA (Vite + React Router)
                        │   Frontend   │
                        └──────────────┘
                               │
                               │ (7) VISUALIZE
                               │
                               ▼
                        ┌──────────────┐
                        │   End User   │
                        └──────────────┘
```

### Data Flow Explained

1. **Extract**: Python scripts query Adzuna API for job postings (15 roles × 18 countries)
2. **Load**: Raw JSON data stored in `raw.jobs` table (immutable landing zone)
3. **Skill Extraction**: Hybrid system extracts skills from descriptions
   - Fast Path: Regex matching against taxonomy (95% of skills, instant)
   - Slow Path: LLM-based extraction for unknown skills (5%, discovery mode)
4. **Transform**: dbt processes raw data into analytical marts
   - Cleaning, normalization, deduplication
   - Aggregations, joins, window functions
   - Business logic and KPI calculations
5. **Serve**: FastAPI exposes REST endpoints querying dbt marts
6. **Consume**: React app fetches data via API calls
7. **Visualize**: Interactive charts, graphs, and dashboards

---

## 🚀 Getting Started

### Prerequisites

Ensure you have the following installed:

- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **Node.js 18+** ([Download](https://nodejs.org/))
- **PostgreSQL 15+** or **Supabase account** ([Sign up](https://supabase.com/))
- **Git** ([Download](https://git-scm.com/))

### Installation

#### 1️⃣ Clone the Repository

```bash
git clone https://github.com/yourusername/skill-hunt.git
cd skill-hunt
```

#### 2️⃣ Set Up Backend

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env
# Edit .env with your Supabase credentials
```

**Backend `.env` Configuration:**
```env
# Database
SUPABASE_URL=postgresql://user:password@host:port/database

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Application
DEBUG=true
CACHE_TTL_SECONDS=3600
API_PREFIX=/api/v1
```

#### 3️⃣ Set Up Frontend

```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install

# Configure environment
# Create .env file if needed
echo "VITE_API_URL=http://localhost:8000/api/v1" > .env
```

#### 4️⃣ Set Up Database

```bash
# Navigate to database directory
cd ../database

# Run schema creation
psql $SUPABASE_URL -f schema.sql

# Or use Supabase SQL Editor and paste schema.sql content
```

#### 5️⃣ Run dbt Transformations

```bash
# Navigate to dbt project
cd ../dbt_project

# Configure profiles.yml with your database credentials
cp profiles.yml.example profiles.yml
# Edit profiles.yml

# Run dbt models
dbt run --target prod

# (Optional) Generate documentation
dbt docs generate
dbt docs serve
```

#### 6️⃣ Run ETL Pipeline (Optional - for fresh data)

```bash
# Navigate to ETL directory
cd ../etl

# Install ETL dependencies
pip install -r requirements.txt

# Set up environment variables
# Add to .env or export:
# ADZUNA_APP_ID=your_app_id
# ADZUNA_APP_KEY=your_app_key

# Run extraction (test mode)
python extractor.py --test

# Run skill extraction
python transformer.py

# Run dbt transformations
cd ../dbt_project
dbt run --target prod
```

### Running the Application

#### Start Backend Server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Backend will be available at:**
- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

#### Start Frontend Development Server

```bash
cd frontend
npm run dev
```

**Frontend will be available at:** http://localhost:5173

---

## 📖 Usage

### Exploring the Dashboard

1. **Navigate to Dashboard** (http://localhost:5173)
   - View high-level job market statistics
   - See trending skills and top roles
   - Monitor recent data updates

2. **Skills Analysis Page** (`/skills`)
   - Search for specific skills (e.g., "Python", "React", "AWS")
   - Filter by role (e.g., "Data Engineer")
   - Filter by country (e.g., "United Kingdom")
   - View skill demand charts
   - Explore skill co-occurrence networks
   - Analyze geographic distribution

3. **Salary Page** (`/salary`)
   - Compare salaries across skills
   - Identify premium skills
   - Filter by role and experience level
   - View salary distribution charts

4. **Companies Page** (`/companies`)
   - Browse top hiring companies
   - Filter by role and location
   - View contract type distributions
   - Search for specific companies

5. **Career Page** (`/career`)
   - Enter your current role
   - View similar roles with skill overlap
   - Identify skill gaps for target roles
   - Plan career transitions

6. **Global Page** (`/global`)
   - Compare skill demand across countries
   - View geographic heatmaps
   - Analyze regional trends

---

## 📚 API Documentation

The Skill Hunt API provides RESTful endpoints for accessing job market data.

### Base URL
```
http://localhost:8000/api/v1
```

### Authentication
Currently, the API is open (no authentication required for development).

### Endpoints Overview

#### **Skills Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/skills/demand` | Get skill demand by role/country |
| GET | `/skills/demand/all` | Get all skills demand |
| GET | `/skills/cooccurrence` | Get skill co-occurrence data |
| GET | `/skills/network` | Get D3.js network graph data |
| GET | `/skills/by-country` | Compare skill across countries |
| GET | `/skills/categories` | Get skill categories |
| GET | `/skills/list` | Get all available skills |

#### **Salary Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/salary/by-skill` | Get salary data by skill |
| GET | `/salary/top-paying-skills` | Get highest paying skills |
| GET | `/salary/premium-skills` | Get skills with salary premium |

#### **Companies Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/companies/leaderboard` | Get top hiring companies |
| GET | `/companies/contract-types` | Get job type distribution |
| GET | `/companies/search` | Search for companies |

#### **Career Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/career/role-similarity` | Get all role similarities |
| GET | `/career/transitions/{role}` | Get career transitions for a role |
| GET | `/career/skill-gap` | Get skill gap analysis |
| GET | `/career/similarity-matrix` | Get role similarity matrix |

#### **Stats Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats/summary` | Get dashboard statistics |
| GET | `/stats/filters` | Get available filter options |
| GET | `/stats/roles` | Get available roles |
| GET | `/stats/countries` | Get available countries |

### Example API Calls

#### Get Skill Demand
```bash
curl "http://localhost:8000/api/v1/skills/demand?role=Data%20Engineer&limit=10"
```

**Response:**
```json
{
  "skills": [
    {
      "skill_name": "Python",
      "mention_count": 1250,
      "job_count": 980,
      "percentage_of_jobs": 78.5,
      "avg_salary_min": 55000,
      "avg_salary_max": 85000,
      "trend": "growing"
    }
  ],
  "total_jobs": 1248,
  "filters": {
    "role": "Data Engineer",
    "country": null,
    "limit": 10
  }
}
```

#### Get Top Paying Skills
```bash
curl "http://localhost:8000/api/v1/salary/top-paying-skills?limit=5"
```

#### Get Career Transitions
```bash
curl "http://localhost:8000/api/v1/career/transitions/Data%20Engineer"
```

For full API documentation with interactive examples, visit: http://localhost:8000/docs

---

## 🔄 Data Pipeline

### ETL Architecture

Skill Hunt uses a **scheduled automated ETL pipeline** that runs **twice weekly** (Sundays and Wednesdays at 3:00 AM UTC) via GitHub Actions.

### Pipeline Stages

#### 1. **Extraction** (`etl/extractor.py`)
- Queries Adzuna API for job postings
- Covers 15 roles × 18 countries = 270 search combinations
- Stores raw JSON in `raw.jobs` table
- Rate-limited and fault-tolerant
- Deduplicates based on job platform ID

#### 2. **Skill Extraction** (`etl/transformer.py`)
- **Hybrid Extraction System**:
  - **Fast Path**: Regex-based matching (instant, free, 95% coverage)
    - Matches against 500+ skills in taxonomy
    - Handles aliases and variations
    - Zero cost, zero latency
  - **Slow Path**: LLM-based extraction (Google Gemini Flash)
    - Discovers new/emerging skills
    - Processes 5-10% of jobs via sampling
    - Costs <$0.10 per 1000 jobs
  - **Discovery Manager**:
    - Tracks newly discovered skills
    - Auto-promotes frequently seen skills to taxonomy
    - Manual review for skill categorization

#### 3. **Transformation** (`dbt_project/`)
- dbt models process staging data into analytical marts
- **Intermediate Layer** (`models/intermediate/`):
  - `int_job_skills_enriched.sql`: Joins jobs with extracted skills
- **Marts Layer** (`models/marts/`):
  - `mart_skill_demand.sql`: Aggregated skill demand metrics
  - `mart_skill_cooccurrence.sql`: Skill pairing analysis
  - `mart_salary_by_skill.sql`: Salary statistics by skill
  - `mart_company_leaderboard.sql`: Top hiring companies
  - `mart_role_similarity.sql`: Career transition analysis
  - `mart_skills_by_country.sql`: Geographic distribution

#### 4. **Serving**
- FastAPI queries final mart tables
- Results cached with configurable TTL (default: 1 hour)
- CORS-enabled for frontend consumption

### Running ETL Manually

```bash
# Full pipeline
cd etl
python extractor.py           # Extract jobs
python transformer.py         # Extract skills
cd ../dbt_project
dbt run --target prod         # Transform data

# Test mode (1 role, 1 country)
python extractor.py --test
```

### Scheduled Automation

ETL runs automatically via GitHub Actions (`.github/workflows/etl_pipeline.yml`):
- **Schedule**: Cron: `0 3 * * 0,3` (Sundays & Wednesdays, 3 AM UTC)
- **Manual Trigger**: Via `workflow_dispatch` in GitHub Actions tab
- **Notifications**: Logs available in GitHub Actions console

---

## 🚢 Deployment

### Backend Deployment (Render)

1. **Create Web Service on Render**
   - Connect GitHub repository
   - Select `backend/` as root directory

2. **Configure Build Settings**
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables**
   - `SUPABASE_URL`: Your PostgreSQL connection string
   - `CORS_ORIGINS`: Your frontend URL (e.g., `https://skill-hunt.vercel.app`)
   - `DEBUG`: `false`
   - `CACHE_TTL_SECONDS`: `3600`

4. **Deploy**
   - Render auto-deploys on Git push
   - Health checks: `GET /api/v1/stats/summary`

### Frontend Deployment (Vercel)

1. **Import Project to Vercel**
   - Connect GitHub repository
   - Select `frontend/` as root directory

2. **Configure Build Settings** (auto-detected)
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`

3. **Set Environment Variables**
   - `VITE_API_URL`: Your Render backend URL (e.g., `https://skill-hunt-api.onrender.com/api/v1`)

4. **Deploy**
   - Vercel auto-deploys on Git push
   - Edge network CDN for global performance

### Database (Supabase)

- Supabase provides managed PostgreSQL
- Connection pooling (PgBouncer) for performance
- Automatic backups and point-in-time recovery
- Dashboard for SQL queries and monitoring

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Workflow

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Run tests** (if available)
5. **Commit**: `git commit -m 'Add amazing feature'`
6. **Push**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Code Style

- **Python**: Follow PEP 8, use Black formatter
- **JavaScript/React**: ESLint rules configured in `.eslintrc`
- **SQL**: Lowercase keywords, 2-space indentation
- **Documentation**: Update README and inline comments

### Commit Messages

Use conventional commits:
```
feat: Add salary comparison chart
fix: Resolve CORS issue on production
docs: Update API documentation
refactor: Simplify skill extraction logic
```

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Adzuna** for providing job posting data via their API
- **Supabase** for managed PostgreSQL infrastructure
- **dbt Labs** for the incredible data transformation framework
- **FastAPI** community for excellent documentation
- **React** ecosystem for powerful frontend tools

---

## 📞 Contact & Support

- **Email**: support@skillhunt.com
- **GitHub Issues**: [Report a bug](https://github.com/yourusername/skill-hunt/issues)
- **Discussions**: [Ask questions](https://github.com/yourusername/skill-hunt/discussions)

---

## 🗺️ Roadmap

- [ ] Real-time job alerts and notifications
- [ ] User authentication and personalized dashboards
- [ ] Resume skill gap analysis
- [ ] Machine learning-based salary prediction
- [ ] Expanded data sources (LinkedIn, Indeed)
- [ ] Mobile app (React Native)
- [ ] API rate limiting and authentication
- [ ] Advanced filtering and search
- [ ] Export reports (PDF, CSV)

---

<div align="center">

**Built with ❤️ by the Skill Hunt Team**

⭐ Star us on GitHub if you find this project useful!

</div>
