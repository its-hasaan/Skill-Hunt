# Skill Hunt 🎯

A full-stack data engineering project that analyzes job market trends and skill demand across 15 tech roles and 17 countries.

## 🎯 What It Does

- **Extracts** job postings from Adzuna API for 15 tech roles across 17 countries
- **Transforms** raw data and extracts skills using pattern matching
- **Analyzes** skill demand, salary premiums, company hiring trends, and role similarity
- **Visualizes** insights on an interactive React dashboard

## 📊 Analytics Provided

| Metric | Description |
|--------|-------------|
| **Top Skills per Role** | Most demanded skills for each job role |
| **Skill Co-occurrence** | Skills that appear together in job postings |
| **Skills by Country** | How skill demand varies across countries |
| **Salary by Skill** | Salary premium for jobs requiring specific skills |
| **Company Leaderboard** | Top hiring companies by role and country |
| **Role Similarity** | Skill overlap between different roles (career transition guide) |

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Adzuna API    │───>│  ETL Pipeline   │───>│    Supabase     │
│  (Job Postings) │    │  (Python/dbt)   │    │  (PostgreSQL)   │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                       ┌─────────────────┐             │
                       │  FastAPI Backend│<────────────┘
                       │    (Render)     │
                       └────────┬────────┘
                                │
                       ┌────────▼────────┐
                       │  React Frontend │
                       │    (Vercel)     │
                       └─────────────────┘
```

## 🛠️ Tech Stack

### Data Pipeline
- **Extraction**: Python + Adzuna API
- **Transformation**: dbt (Data Build Tool)
- **Storage**: Supabase (PostgreSQL)

### Backend
- **Framework**: FastAPI + Uvicorn
- **Database Client**: asyncpg
- **Validation**: Pydantic
- **Hosting**: Render

### Frontend
- **Framework**: React 18 + Vite
- **Styling**: Tailwind CSS
- **Charts**: Recharts + D3.js
- **Data Fetching**: React Query
- **Hosting**: Vercel

## 📁 Project Structure

```
skill-hunt/
├── .github/workflows/
│   └── etl_pipeline.yml      # GitHub Actions workflow
├── config/
│   ├── extraction_config.json # Roles and countries to extract
│   └── skills_taxonomy.json   # 150+ skills with aliases
├── database/
│   └── schema.sql            # Full database schema
├── dbt_project/
│   ├── models/
│   │   ├── intermediate/     # Enriched job-skill data
│   │   └── marts/            # Business-ready aggregations
│   ├── dbt_project.yml
│   └── profiles.yml
├── extractor.py              # Adzuna API extraction
├── transformer.py            # Skill extraction from descriptions
├── requirements.txt
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Supabase account (free tier works)
- Adzuna API credentials (free at https://developer.adzuna.com/)

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/skill-hunt.git
cd skill-hunt
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Set Up Database

Run the schema in your Supabase SQL Editor:
```sql
-- Copy contents of database/schema.sql
```

### 4. Run Pipeline

```bash
# Extract jobs (test mode - 1 role, 1 country)
python extractor.py --test

# Extract all jobs
python extractor.py

# Transform and extract skills
python transformer.py

# Run dbt models
cd dbt_project
dbt run
```

## ⚙️ GitHub Actions Setup

Add these secrets to your repository:

| Secret | Description |
|--------|-------------|
| `ADZUNA_APP_ID` | Adzuna API App ID |
| `ADZUNA_APP_KEY` | Adzuna API Key |
| `SUPABASE_URL` | Full PostgreSQL connection string |
| `SUPABASE_HOST` | Supabase host (for dbt) |
| `SUPABASE_USER` | Database user |
| `SUPABASE_PASSWORD` | Database password |
| `SUPABASE_DB` | Database name |

The pipeline runs automatically twice a week (Sunday and Wednesday at 3 AM UTC).

## 📈 Database Schema

### Raw Layer
- `raw.jobs` - Raw JSON from Adzuna API

### Staging Layer
- `staging.stg_jobs` - Cleaned job postings
- `staging.stg_job_skills` - Extracted skills per job
- `staging.dim_skills` - Skills taxonomy
- `staging.dim_job_roles` - Target roles
- `staging.dim_countries` - Supported countries

### Marts Layer
- `marts.skill_demand` - Top skills by role/country
- `marts.skill_cooccurrence` - Skills that appear together
- `marts.salary_by_skill` - Salary comparison by skill
- `marts.company_leaderboard` - Top hiring companies
- `marts.role_similarity` - Skill overlap between roles

### Archive Layer
- `archive.skill_demand_history` - Weekly snapshots for trend analysis

## 📋 Tracked Roles

1. Data Engineer
2. Analytics Engineer
3. Data Scientist
4. Data Analyst
5. Business Intelligence Developer
6. Machine Learning Engineer
7. AI Engineer
8. Computer Vision Engineer
9. Backend Developer
10. Frontend Developer
11. Full Stack Developer
12. Mobile Developer
13. DevOps Engineer
14. Cloud Architect
15. Cyber Security Engineer

## 🌍 Supported Countries

UK, US, Australia, Austria, Belgium, Brazil, Canada, Germany, France, India, Italy, Mexico, Netherlands, New Zealand, Poland, Singapore, South Africa

## 📝 License

MIT License - feel free to use for your own portfolio!

## 🤝 Contributing

This is a portfolio project, but suggestions are welcome! Open an issue or PR.
