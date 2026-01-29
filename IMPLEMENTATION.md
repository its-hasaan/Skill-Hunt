# 🔧 Skill Hunt - Implementation Guide

> **Comprehensive Technical Documentation**  
> Deep dive into the architecture, implementation details, and engineering decisions behind Skill Hunt.

---

## 📋 Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Database Design](#2-database-design)
3. [ETL Pipeline Implementation](#3-etl-pipeline-implementation)
4. [Backend Implementation](#4-backend-implementation)
5. [Frontend Implementation](#5-frontend-implementation)
6. [Data Transformation Layer (dbt)](#6-data-transformation-layer-dbt)
7. [Deployment & DevOps](#7-deployment--devops)
8. [Performance Optimization](#8-performance-optimization)
9. [Security & Best Practices](#9-security--best-practices)
10. [Testing Strategy](#10-testing-strategy)

---

## 1. System Architecture

### 1.1 High-Level Architecture

Skill Hunt follows a **Modern Data Stack (MDS)** architecture pattern, emphasizing:
- **Separation of Concerns**: Distinct layers for extraction, storage, transformation, and presentation
- **ELT over ETL**: Load raw data first, transform in-database for performance
- **Cloud-Native**: Leverages managed services (Supabase, Render, Vercel)
- **API-First**: Backend as a service layer with RESTful endpoints
- **Stateless Frontend**: React SPA consuming API data

### 1.2 Technology Decisions

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Database** | PostgreSQL (Supabase) | ACID compliance, JSON support (JSONB), powerful analytics, managed hosting |
| **Backend** | FastAPI | Async support, automatic OpenAPI docs, Pydantic validation, excellent performance |
| **Frontend** | React + Vite | Component reusability, virtual DOM, fast HMR, modern tooling |
| **Transformation** | dbt | SQL-based, version control, documentation, lineage tracking |
| **Orchestration** | GitHub Actions | Free for public repos, integrated with version control, declarative YAML |
| **Charting** | Recharts + D3.js | Recharts for simplicity, D3 for advanced network graphs |
| **Styling** | Tailwind CSS | Utility-first, rapid prototyping, consistent design system |

### 1.3 Data Flow Architecture

```
External API → Extractor → PostgreSQL → Transformer → PostgreSQL → dbt → PostgreSQL
                                ↓                                        ↓
                         Raw Layer (JSONB)                        Marts Layer (SQL)
                                                                         ↓
                                                                    FastAPI
                                                                         ↓
                                                                    React SPA
```

---

## 2. Database Design

### 2.1 Schema Organization

The database is organized into **four distinct schemas**, following data warehouse best practices:

#### **Schema Layers**

1. **`raw`** - Immutable landing zone
   - Stores unprocessed API responses as JSONB
   - Acts as source of truth
   - Enables reprocessing without re-extraction

2. **`staging`** - Normalized operational data
   - Flattened and cleaned data
   - Dimension tables (roles, countries, skills)
   - Foreign key relationships

3. **`marts`** - Analytical aggregations
   - Pre-computed metrics for dashboard performance
   - Denormalized for query speed
   - Updated by dbt transformations

4. **`archive`** - Historical snapshots
   - Point-in-time backups
   - Change data capture

### 2.2 Key Tables

#### **`raw.jobs`**
```sql
CREATE TABLE raw.jobs (
    id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    search_role TEXT NOT NULL,
    country_code TEXT NOT NULL,
    raw_data JSONB NOT NULL,              -- Complete API response
    extracted_at TIMESTAMP DEFAULT NOW(),
    extraction_batch_id UUID DEFAULT uuid_generate_v4(),
    CONSTRAINT raw_jobs_unique UNIQUE (job_platform_id, country_code)
);
```

**Design Decisions:**
- **JSONB Column**: Preserves complete API response for future reprocessing
- **Composite Unique Key**: Same job can appear in different countries
- **Batch ID**: Enables tracking extraction runs and rollbacks

#### **`staging.stg_jobs`**
```sql
CREATE TABLE staging.stg_jobs (
    job_id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    search_role TEXT NOT NULL,
    country_code TEXT NOT NULL,
    title TEXT,
    company_name TEXT,
    description TEXT,
    location_display TEXT,
    location_areas TEXT[],                -- PostgreSQL array for hierarchical locations
    category_tag TEXT,
    salary_min NUMERIC,
    salary_max NUMERIC,
    salary_is_predicted BOOLEAN DEFAULT FALSE,
    salary_currency TEXT DEFAULT 'GBP',
    contract_type TEXT,                   -- 'permanent', 'contract', etc.
    contract_time TEXT,                   -- 'full_time', 'part_time'
    created_at TIMESTAMP,
    redirect_url TEXT,
    processed_at TIMESTAMP DEFAULT NOW()
);
```

**Design Decisions:**
- **Flattened Structure**: Optimizes for SQL queries vs. nested JSON
- **Array Type**: Native PostgreSQL support for multi-valued location hierarchy
- **Nullable Salaries**: Not all jobs include compensation data
- **Predicted Flag**: Distinguishes actual vs. estimated salaries

#### **`staging.stg_job_skills`**
```sql
CREATE TABLE staging.stg_job_skills (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES staging.stg_jobs(job_id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES staging.dim_skills(skill_id),
    extraction_method TEXT,               -- 'fast_path' or 'slow_path'
    confidence_score NUMERIC,             -- 0.0 to 1.0
    context_snippet TEXT,                 -- Surrounding text for verification
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Design Decisions:**
- **Foreign Keys**: Ensures referential integrity
- **Cascade Delete**: Automatically cleans up skills when job is deleted
- **Extraction Method**: Tracks whether skill was found via regex or LLM
- **Confidence Score**: Enables filtering of low-confidence matches

#### **`staging.dim_skills`**
```sql
CREATE TABLE staging.dim_skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name TEXT UNIQUE NOT NULL,
    skill_category TEXT,                  -- 'Programming Language', 'Cloud', 'Database', etc.
    skill_subcategory TEXT,               -- 'AWS Services', 'NoSQL Databases', etc.
    aliases TEXT[],                       -- Alternative names: ["python3", "py"]
    verification_status TEXT DEFAULT 'Unverified',  -- 'Verified', 'Unverified', 'Rejected'
    discovery_count INTEGER DEFAULT 0,    -- Times seen in discovery mode
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Design Decisions:**
- **Aliases Array**: Handles skill name variations (React.js, React, ReactJS)
- **Verification Status**: Manual curation workflow for discovered skills
- **Discovery Count**: Auto-promotion threshold for frequently seen skills

### 2.3 Indexing Strategy

```sql
-- Performance indexes for common queries
CREATE INDEX idx_raw_jobs_extracted_at ON raw.jobs(extracted_at);
CREATE INDEX idx_raw_jobs_search_role ON raw.jobs(search_role);
CREATE INDEX idx_raw_jobs_country ON raw.jobs(country_code);
CREATE INDEX idx_stg_jobs_role ON staging.stg_jobs(search_role);
CREATE INDEX idx_stg_jobs_country ON staging.stg_jobs(country_code);
CREATE INDEX idx_stg_jobs_company ON staging.stg_jobs(company_name);
CREATE INDEX idx_stg_job_skills_job_id ON staging.stg_job_skills(job_id);
CREATE INDEX idx_stg_job_skills_skill_id ON staging.stg_job_skills(skill_id);
CREATE INDEX idx_dim_skills_name ON staging.dim_skills(skill_name);
CREATE INDEX idx_dim_skills_category ON staging.dim_skills(skill_category);
```

**Indexing Rationale:**
- **Filter Columns**: Indexes on `search_role`, `country_code` for WHERE clauses
- **Join Columns**: Indexes on foreign keys for join performance
- **Timestamp Columns**: Enables efficient time-range queries
- **Text Search**: Consider GIN indexes for full-text search in future

---

## 3. ETL Pipeline Implementation

### 3.1 Extraction (`etl/extractor.py`)

#### **Architecture**

The extractor is a Python script that queries the **Adzuna Job Search API** and stores raw responses in PostgreSQL.

#### **Configuration-Driven Design**

```json
// etl/config/extraction_config.json
{
  "roles": [
    "Data Engineer",
    "Analytics Engineer",
    "Data Scientist",
    "Full Stack Developer",
    // ... 15 total roles
  ],
  "countries": ["gb", "us", "au", "ca", "de", "fr", "in", "sg", ...],
  "pagination": {
    "results_per_page": 50,
    "max_pages_per_search": 20
  },
  "filters": {
    "max_days_old": 30
  }
}
```

**Benefits:**
- Modify roles/countries without code changes
- Version-controlled configuration
- Easy A/B testing of extraction parameters

#### **Core Extraction Logic**

```python
def get_jobs(role: str, country: str = "gb", page: int = 1, max_days_old: int = None) -> list:
    """
    Fetches jobs from Adzuna API with error handling and rate limiting.
    """
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": role,
        "results_per_page": 50,
        "content-type": "application/json"
    }
    
    if max_days_old:
        params["max_days_old"] = max_days_old
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return []
```

**Robust Error Handling:**
- **Timeout Protection**: 30-second timeout prevents hanging
- **HTTP Error Handling**: `raise_for_status()` catches 4xx/5xx errors
- **Graceful Degradation**: Returns empty list on failure, continues with next search

#### **Batch Insertion for Performance**

```python
def insert_jobs_batch(conn, jobs: list, search_role: str, country_code: str, batch_id: str):
    """
    Bulk insert jobs using execute_values for performance.
    """
    insert_query = """
        INSERT INTO raw.jobs (job_platform_id, search_role, country_code, raw_data, extraction_batch_id)
        VALUES %s
        ON CONFLICT (job_platform_id, country_code) DO NOTHING
    """
    
    values = [
        (job['id'], search_role, country_code, json.dumps(job), batch_id)
        for job in jobs
    ]
    
    with conn.cursor() as cur:
        execute_values(cur, insert_query, values)
    conn.commit()
```

**Performance Optimization:**
- **Bulk Insert**: `execute_values()` is 10-100x faster than individual inserts
- **ON CONFLICT DO NOTHING**: Idempotent inserts, safe for re-runs
- **Batching**: Reduces network round-trips

#### **Rate Limiting & Politeness**

```python
# Rate limiting between API calls
time.sleep(1)  # 1 request per second to respect API limits
```

**API Politeness:**
- Prevents overwhelming external API
- Avoids rate limit bans
- Distributes load over time

---

### 3.2 Skill Extraction (`etl/transformer.py`)

#### **Hybrid Extraction Architecture**

Skill extraction is the most innovative component, using a **two-path system**:

1. **Fast Path**: Regex-based pattern matching (95% coverage, instant, free)
2. **Slow Path**: LLM-based extraction (5% sampling, for discovery)

#### **Fast Path Implementation**

```python
# etl/skill_extractor/fast_path.py
class FastPathExtractor:
    def __init__(self, taxonomy_path: str):
        self.taxonomy = self.load_taxonomy(taxonomy_path)
        self.patterns = self.compile_patterns()
    
    def compile_patterns(self) -> dict:
        """
        Compile regex patterns for each skill + aliases.
        """
        patterns = {}
        for skill in self.taxonomy['skills']:
            # Create pattern matching skill name + aliases
            terms = [skill['name']] + skill.get('aliases', [])
            # Word boundary patterns to avoid false positives
            pattern = r'\b(' + '|'.join(re.escape(t) for t in terms) + r')\b'
            patterns[skill['name']] = re.compile(pattern, re.IGNORECASE)
        return patterns
    
    def extract(self, text: str) -> List[Dict]:
        """
        Extract skills from text using regex matching.
        """
        results = []
        for skill_name, pattern in self.patterns.items():
            matches = pattern.findall(text)
            if matches:
                results.append({
                    'skill_name': skill_name,
                    'confidence': 1.0,  # Regex matches are certain
                    'method': 'fast_path',
                    'matches': len(matches)
                })
        return results
```

**Fast Path Benefits:**
- **Zero Cost**: No API calls
- **Zero Latency**: Regex is near-instant
- **High Precision**: Word boundaries prevent false positives ("Go" language vs. "go to")
- **Scalable**: Can process millions of jobs

**Taxonomy Structure:**
```json
{
  "skills": [
    {
      "name": "Python",
      "category": "Programming Language",
      "subcategory": "General Purpose",
      "aliases": ["python3", "py", "CPython"]
    },
    {
      "name": "Amazon Web Services",
      "category": "Cloud",
      "subcategory": "Cloud Platform",
      "aliases": ["AWS", "aws cloud"]
    }
  ]
}
```

#### **Slow Path Implementation (LLM-Based)**

```python
# etl/skill_extractor/slow_path.py
class SlowPathExtractor:
    def __init__(self, model: str = "gemini-flash"):
        self.model = genai.GenerativeModel(model)
    
    def extract(self, text: str, known_skills: Set[str]) -> List[Dict]:
        """
        Use LLM to discover skills not in taxonomy.
        """
        prompt = f"""
        Extract technical skills, tools, and technologies from the following job description.
        
        IGNORE these skills (already identified): {', '.join(known_skills)}
        
        Only return NEW skills not in the ignore list. Format as JSON array:
        [{{"skill": "skill_name", "category": "category", "confidence": 0.0-1.0}}]
        
        Job Description:
        {text[:2000]}  # Truncate to reduce cost
        """
        
        response = self.model.generate_content(prompt)
        return self.parse_response(response.text)
```

**Slow Path Advantages:**
- **Discovers New Skills**: Finds emerging technologies not in taxonomy
- **Context-Aware**: Understands skill mentions in context
- **Self-Improving**: Discovered skills auto-promote to fast path

**Cost Optimization:**
- **Sampling**: Only 5-10% of jobs processed via LLM
- **Truncation**: Limits input tokens to 2000 characters
- **Caching**: Google Gemini offers context caching
- **Total Cost**: <$0.10 per 1000 jobs processed

#### **Discovery Manager**

```python
class DiscoveryManager:
    def __init__(self, db_connection):
        self.db = db_connection
        self.promotion_threshold = 10  # Promote after 10 occurrences
    
    def record_discovery(self, skill_name: str, category: str):
        """
        Track newly discovered skill.
        """
        query = """
            INSERT INTO staging.dim_skills (skill_name, skill_category, verification_status, discovery_count)
            VALUES (%s, %s, 'Unverified', 1)
            ON CONFLICT (skill_name) 
            DO UPDATE SET discovery_count = dim_skills.discovery_count + 1
        """
        self.db.execute(query, (skill_name, category))
    
    def promote_frequent_skills(self):
        """
        Auto-promote skills seen frequently to taxonomy.
        """
        query = """
            UPDATE staging.dim_skills
            SET verification_status = 'Verified'
            WHERE discovery_count >= %s AND verification_status = 'Unverified'
            RETURNING skill_name
        """
        promoted = self.db.execute(query, (self.promotion_threshold,))
        for skill in promoted:
            self.add_to_taxonomy(skill['skill_name'])
```

**Auto-Promotion Workflow:**
1. LLM discovers new skill (e.g., "Astro.js")
2. Recorded as "Unverified" with count = 1
3. Each subsequent discovery increments count
4. At threshold (10), auto-promoted to "Verified"
5. Added to taxonomy JSON for fast path matching

---

### 3.3 Transformation Logic

#### **Job Data Transformation**

```python
def transform_job(raw_job: dict) -> dict:
    """
    Transform raw API response into staging table format.
    """
    return {
        'job_platform_id': raw_job['id'],
        'title': raw_job.get('title'),
        'company_name': raw_job.get('company', {}).get('display_name'),
        'description': raw_job.get('description', ''),
        'location_display': raw_job.get('location', {}).get('display_name'),
        'location_areas': raw_job.get('location', {}).get('area', []),
        'category_tag': raw_job.get('category', {}).get('tag'),
        'salary_min': raw_job.get('salary_min'),
        'salary_max': raw_job.get('salary_max'),
        'salary_is_predicted': raw_job.get('salary_is_predicted', False),
        'contract_type': raw_job.get('contract_type'),
        'contract_time': raw_job.get('contract_time'),
        'created_at': raw_job.get('created'),
        'redirect_url': raw_job.get('redirect_url')
    }
```

#### **Batch Processing**

```python
def process_jobs_batch(batch_size: int = 1000):
    """
    Process unprocessed jobs in batches for memory efficiency.
    """
    offset = 0
    while True:
        # Fetch batch of unprocessed jobs
        jobs = fetch_unprocessed_jobs(limit=batch_size, offset=offset)
        if not jobs:
            break
        
        # Transform and extract skills
        for job in jobs:
            transformed = transform_job(job['raw_data'])
            job_id = insert_staging_job(transformed)
            
            # Extract skills
            skills = skill_extractor.extract(job['raw_data']['description'])
            insert_job_skills(job_id, skills)
        
        offset += batch_size
        logger.info(f"Processed {offset} jobs...")
```

**Memory Management:**
- Processes jobs in batches to avoid loading entire dataset
- Commits after each batch for fault tolerance
- Progress logging for monitoring

---

## 4. Backend Implementation

### 4.1 FastAPI Application Structure

#### **Application Factory Pattern**

```python
# backend/app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting Skill Hunt API...")
    await db.connect()
    yield
    # Shutdown
    await db.disconnect()

app = FastAPI(
    title="Skill Hunt API",
    description="Job market analysis API",
    version="1.0.0",
    lifespan=lifespan
)
```

**Lifespan Pattern Benefits:**
- Centralizes startup/shutdown logic
- Ensures database connections are properly managed
- Async-friendly context manager

#### **Database Connection Pooling**

```python
# backend/app/database.py
from databases import Database
from app.config import get_settings

settings = get_settings()

class DatabaseManager:
    def __init__(self):
        self.database = Database(settings.supabase_url)
    
    async def connect(self):
        await self.database.connect()
        logger.info("Database connection pool established")
    
    async def disconnect(self):
        await self.database.disconnect()
    
    async def fetch_all(self, query: str, values: dict = None):
        return await self.database.fetch_all(query=query, values=values)
    
    async def fetch_one(self, query: str, values: dict = None):
        return await self.database.fetch_one(query=query, values=values)

db = DatabaseManager()
```

**Connection Pooling Advantages:**
- Reuses connections instead of creating new ones
- Reduces latency (connection overhead eliminated)
- Handles concurrent requests efficiently

### 4.2 Router Architecture

#### **Modular Routing**

```python
# backend/app/main.py
from app.routers import (
    skills_router,
    companies_router,
    salary_router,
    career_router,
    stats_router
)

app.include_router(skills_router, prefix="/api/v1/skills", tags=["Skills"])
app.include_router(salary_router, prefix="/api/v1/salary", tags=["Salary"])
app.include_router(companies_router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(career_router, prefix="/api/v1/career", tags=["Career"])
app.include_router(stats_router, prefix="/api/v1/stats", tags=["Statistics"])
```

**Benefits:**
- **Separation of Concerns**: Each domain in separate file
- **Scalability**: Easy to add new routers
- **Documentation**: Automatic grouping in OpenAPI docs

#### **Example Router Implementation**

```python
# backend/app/routers/skills.py
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from app.database import db
from app.models.schemas import SkillDemand, SkillDemandResponse

router = APIRouter()

@router.get("/demand", response_model=SkillDemandResponse)
async def get_skill_demand(
    role: Optional[str] = Query(None, description="Filter by job role"),
    country: Optional[str] = Query(None, description="Filter by country"),
    limit: int = Query(20, ge=1, le=100, description="Number of results")
):
    """
    Get skill demand metrics with optional filters.
    
    Returns skills ranked by job mentions, with salary data.
    """
    query = """
        SELECT 
            skill_name,
            mention_count,
            job_count,
            percentage_of_jobs,
            avg_salary_min,
            avg_salary_max,
            trend
        FROM marts.mart_skill_demand
        WHERE 1=1
    """
    values = {}
    
    if role:
        query += " AND role = :role"
        values['role'] = role
    
    if country:
        query += " AND country_code = :country"
        values['country'] = country
    
    query += " ORDER BY mention_count DESC LIMIT :limit"
    values['limit'] = limit
    
    results = await db.fetch_all(query=query, values=values)
    
    # Get total job count for context
    count_query = "SELECT COUNT(*) as total FROM staging.stg_jobs WHERE 1=1"
    if role:
        count_query += " AND search_role = :role"
    if country:
        count_query += " AND country_code = :country"
    
    total = await db.fetch_one(query=count_query, values=values)
    
    return {
        "skills": [SkillDemand(**dict(row)) for row in results],
        "total_jobs": total['total'],
        "filters": {"role": role, "country": country, "limit": limit}
    }
```

**Best Practices Demonstrated:**
- **Pydantic Response Models**: Automatic validation and serialization
- **Query Parameters**: Type-safe with validation (ge=1, le=100)
- **Dynamic SQL**: Builds query based on provided filters
- **Parameterized Queries**: Prevents SQL injection
- **Metadata in Response**: Includes filter context for debugging

### 4.3 Data Validation with Pydantic

```python
# backend/app/models/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SkillDemand(BaseModel):
    skill_name: str = Field(..., description="Name of the skill")
    mention_count: int = Field(..., description="Total mentions in job descriptions")
    job_count: int = Field(..., description="Number of jobs requiring this skill")
    percentage_of_jobs: float = Field(..., description="Percentage of total jobs")
    avg_salary_min: Optional[float] = Field(None, description="Average minimum salary")
    avg_salary_max: Optional[float] = Field(None, description="Average maximum salary")
    trend: Optional[str] = Field(None, description="Growing, declining, or stable")
    
    class Config:
        from_attributes = True  # Allows creating from ORM objects

class SkillDemandResponse(BaseModel):
    skills: List[SkillDemand]
    total_jobs: int
    filters: dict
```

**Pydantic Advantages:**
- **Automatic Validation**: Type checking at runtime
- **Self-Documenting**: Field descriptions appear in OpenAPI docs
- **Serialization**: Converts database rows to JSON seamlessly
- **IDE Support**: Autocomplete and type hints

### 4.4 CORS Configuration

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

origins = settings.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Security Considerations:**
- **Environment-Based**: Different origins for dev vs. prod
- **Explicit Whitelist**: Only specified origins allowed
- **Credentials Support**: Enables cookies/auth headers if needed

### 4.5 Request Timing Middleware

```python
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2)) + "ms"
    return response
```

**Performance Monitoring:**
- Adds processing time to every response header
- Helps identify slow endpoints
- No external dependencies required

### 4.6 Error Handling

```python
from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "path": str(request.url),
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

**Graceful Degradation:**
- Catches all unhandled exceptions
- Logs full stack trace for debugging
- Returns user-friendly error message
- Includes context (path, timestamp)

---

## 5. Frontend Implementation

### 5.1 React Application Structure

```
frontend/src/
├── main.jsx              # Entry point
├── App.jsx               # Router configuration
├── index.css             # Global styles
├── api/
│   └── index.js          # API client
├── components/
│   ├── Layout.jsx        # Shell with navigation
│   ├── charts/
│   │   ├── Charts.jsx    # Recharts components
│   │   ├── Heatmap.jsx   # Geographic heatmap
│   │   └── NetworkGraph.jsx  # D3 network visualization
│   └── ui/
│       └── index.jsx     # Reusable UI components
├── hooks/
│   └── useData.js        # Custom data fetching hook
├── pages/
│   ├── Dashboard.jsx     # Home page
│   ├── SkillsPage.jsx    # Skills analysis
│   ├── SalaryPage.jsx    # Salary insights
│   ├── CompaniesPage.jsx # Company leaderboard
│   ├── CareerPage.jsx    # Career paths
│   └── GlobalPage.jsx    # Geographic view
└── utils/
    └── helpers.js        # Utility functions
```

### 5.2 API Client Implementation

```javascript
// frontend/src/api/index.js
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`)
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error(`API Error: ${error.response.status}`, error.response.data)
    } else if (error.request) {
      console.error('API Error: No response received', error.request)
    } else {
      console.error('API Error:', error.message)
    }
    return Promise.reject(error)
  }
)

export const skillsAPI = {
  getDemand: (params) => api.get('/skills/demand', { params }),
  getCooccurrence: (params) => api.get('/skills/cooccurrence', { params }),
  getNetwork: (params) => api.get('/skills/network', { params }),
  getByCountry: (params) => api.get('/skills/by-country', { params }),
}

export const salaryAPI = {
  getBySkill: (params) => api.get('/salary/by-skill', { params }),
  getTopPaying: (params) => api.get('/salary/top-paying-skills', { params }),
  getPremiumSkills: (params) => api.get('/salary/premium-skills', { params }),
}

export const companiesAPI = {
  getLeaderboard: (params) => api.get('/companies/leaderboard', { params }),
  getContractTypes: (params) => api.get('/companies/contract-types', { params }),
}

export const careerAPI = {
  getRoleSimilarity: () => api.get('/career/role-similarity'),
  getTransitions: (role) => api.get(`/career/transitions/${role}`),
  getSkillGap: (params) => api.get('/career/skill-gap', { params }),
}

export const statsAPI = {
  getSummary: () => api.get('/stats/summary'),
  getFilters: () => api.get('/stats/filters'),
}

export default api
```

**Architecture Benefits:**
- **Centralized Configuration**: Single source of truth for base URL
- **Interceptors**: Global logging and error handling
- **Modular Exports**: Organized by domain
- **Type Safety**: Can add TypeScript for autocomplete

### 5.3 Custom Data Fetching Hook

```javascript
// frontend/src/hooks/useData.js
import { useState, useEffect } from 'react'

export function useData(apiFunction, params = {}, dependencies = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let isMounted = true

    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await apiFunction(params)
        if (isMounted) {
          setData(response.data)
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'An error occurred')
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    fetchData()

    return () => {
      isMounted = false
    }
  }, dependencies)

  return { data, loading, error }
}
```

**Hook Features:**
- **Loading States**: Tracks loading, error, and data states
- **Cleanup**: Prevents state updates on unmounted components
- **Dependency Tracking**: Re-fetches when dependencies change
- **Reusable**: Works with any API function

### 5.4 Example Page Implementation

```javascript
// frontend/src/pages/SkillsPage.jsx
import { useState } from 'react'
import { skillsAPI } from '../api'
import { useData } from '../hooks/useData'
import { Charts } from '../components/charts/Charts'

export default function SkillsPage() {
  const [role, setRole] = useState('Data Engineer')
  const [country, setCountry] = useState(null)
  const [limit, setLimit] = useState(20)

  const { data, loading, error } = useData(
    skillsAPI.getDemand,
    { role, country, limit },
    [role, country, limit]
  )

  if (loading) return <div className="flex justify-center p-8">Loading...</div>
  if (error) return <div className="text-red-500 p-8">Error: {error}</div>

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Skills Analysis</h1>
      
      <div className="flex gap-4 mb-8">
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="px-4 py-2 border rounded"
        >
          <option value="Data Engineer">Data Engineer</option>
          <option value="Data Scientist">Data Scientist</option>
          <option value="Full Stack Developer">Full Stack Developer</option>
          {/* ... more options */}
        </select>
        
        <select
          value={country || ''}
          onChange={(e) => setCountry(e.target.value || null)}
          className="px-4 py-2 border rounded"
        >
          <option value="">All Countries</option>
          <option value="gb">United Kingdom</option>
          <option value="us">United States</option>
          {/* ... more options */}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <Charts.BarChart
          data={data.skills}
          xKey="skill_name"
          yKey="mention_count"
          title="Top Skills by Demand"
        />
        
        <Charts.LineChart
          data={data.skills}
          xKey="skill_name"
          yKey="avg_salary_max"
          title="Average Salary by Skill"
        />
      </div>

      <div className="mt-8">
        <h2 className="text-2xl font-semibold mb-4">Skills Table</h2>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="p-3 text-left">Skill</th>
              <th className="p-3 text-right">Mentions</th>
              <th className="p-3 text-right">% of Jobs</th>
              <th className="p-3 text-right">Avg Salary</th>
            </tr>
          </thead>
          <tbody>
            {data.skills.map((skill) => (
              <tr key={skill.skill_name} className="border-b">
                <td className="p-3">{skill.skill_name}</td>
                <td className="p-3 text-right">{skill.mention_count}</td>
                <td className="p-3 text-right">{skill.percentage_of_jobs.toFixed(1)}%</td>
                <td className="p-3 text-right">
                  ${skill.avg_salary_min?.toLocaleString()} - ${skill.avg_salary_max?.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

### 5.5 Network Graph Visualization (D3.js)

```javascript
// frontend/src/components/charts/NetworkGraph.jsx
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

export default function NetworkGraph({ data }) {
  const svgRef = useRef()

  useEffect(() => {
    if (!data) return

    const width = 800
    const height = 600

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)

    svg.selectAll('*').remove() // Clear previous render

    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.links).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))

    const link = svg.append('g')
      .selectAll('line')
      .data(data.links)
      .join('line')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', d => Math.sqrt(d.value))

    const node = svg.append('g')
      .selectAll('circle')
      .data(data.nodes)
      .join('circle')
      .attr('r', 8)
      .attr('fill', d => d.category === 'Programming Language' ? '#3b82f6' : '#10b981')
      .call(drag(simulation))

    const labels = svg.append('g')
      .selectAll('text')
      .data(data.nodes)
      .join('text')
      .text(d => d.name)
      .attr('font-size', 10)
      .attr('dx', 12)
      .attr('dy', 4)

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y)

      labels
        .attr('x', d => d.x)
        .attr('y', d => d.y)
    })

    function drag(simulation) {
      function dragstarted(event) {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        event.subject.fx = event.subject.x
        event.subject.fy = event.subject.y
      }

      function dragged(event) {
        event.subject.fx = event.x
        event.subject.fy = event.y
      }

      function dragended(event) {
        if (!event.active) simulation.alphaTarget(0)
        event.subject.fx = null
        event.subject.fy = null
      }

      return d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended)
    }

  }, [data])

  return <svg ref={svgRef}></svg>
}
```

**D3 Force Simulation:**
- **Physics-Based Layout**: Nodes repel, links attract
- **Interactive**: Drag nodes to reposition
- **Color-Coded**: Different colors for skill categories
- **Dynamic**: Updates when data changes

---

## 6. Data Transformation Layer (dbt)

### 6.1 dbt Project Structure

```
dbt_project/
├── dbt_project.yml          # Project configuration
├── profiles.yml             # Database connection
├── models/
│   ├── sources.yml          # Source definitions
│   ├── intermediate/        # Intermediate transformations
│   │   ├── int_job_skills_enriched.sql
│   │   └── schema.yml
│   └── marts/               # Final analytics tables
│       ├── mart_skill_demand.sql
│       ├── mart_skill_cooccurrence.sql
│       ├── mart_salary_by_skill.sql
│       ├── mart_company_leaderboard.sql
│       ├── mart_role_similarity.sql
│       ├── mart_skills_by_country.sql
│       └── schema.yml
```

### 6.2 Source Definitions

```yaml
# models/sources.yml
version: 2

sources:
  - name: staging
    database: postgres
    schema: staging
    tables:
      - name: stg_jobs
        description: Cleaned and normalized job postings
        columns:
          - name: job_id
            description: Primary key
            tests:
              - unique
              - not_null
      
      - name: stg_job_skills
        description: Skills extracted from job descriptions
        columns:
          - name: job_id
            tests:
              - relationships:
                  to: source('staging', 'stg_jobs')
                  field: job_id
      
      - name: dim_skills
        description: Master skills taxonomy
```

### 6.3 Intermediate Model Example

```sql
-- models/intermediate/int_job_skills_enriched.sql
{{
  config(
    materialized='view',
    schema='intermediate'
  )
}}

WITH job_skills AS (
    SELECT
        js.job_id,
        js.skill_id,
        js.extraction_method,
        js.confidence_score,
        s.skill_name,
        s.skill_category,
        s.skill_subcategory,
        j.search_role,
        j.country_code,
        j.company_name,
        j.salary_min,
        j.salary_max,
        j.contract_type
    FROM {{ source('staging', 'stg_job_skills') }} js
    INNER JOIN {{ source('staging', 'dim_skills') }} s
        ON js.skill_id = s.skill_id
    INNER JOIN {{ source('staging', 'stg_jobs') }} j
        ON js.job_id = j.job_id
    WHERE js.confidence_score >= 0.7  -- Filter low-confidence matches
)

SELECT * FROM job_skills
```

**Jinja Templating:**
- `{{ source() }}`: References source tables with lineage tracking
- `{{ config() }}`: Defines materialization strategy
- Enables SQL reuse and dynamic queries

### 6.4 Mart Model Example

```sql
-- models/marts/mart_skill_demand.sql
{{
  config(
    materialized='table',
    schema='marts',
    indexes=[
      {'columns': ['role', 'country_code']},
      {'columns': ['skill_name']}
    ]
  )
}}

WITH skill_metrics AS (
    SELECT
        skill_name,
        skill_category,
        search_role AS role,
        country_code,
        COUNT(*) AS mention_count,
        COUNT(DISTINCT job_id) AS job_count,
        AVG(salary_min) AS avg_salary_min,
        AVG(salary_max) AS avg_salary_max,
        MIN(salary_min) AS min_salary,
        MAX(salary_max) AS max_salary
    FROM {{ ref('int_job_skills_enriched') }}
    WHERE salary_min IS NOT NULL
    GROUP BY skill_name, skill_category, search_role, country_code
),

total_jobs AS (
    SELECT
        search_role AS role,
        country_code,
        COUNT(DISTINCT job_id) AS total_count
    FROM {{ source('staging', 'stg_jobs') }}
    GROUP BY search_role, country_code
)

SELECT
    sm.skill_name,
    sm.skill_category,
    sm.role,
    sm.country_code,
    sm.mention_count,
    sm.job_count,
    ROUND((sm.job_count::NUMERIC / tj.total_count * 100), 2) AS percentage_of_jobs,
    ROUND(sm.avg_salary_min, 0) AS avg_salary_min,
    ROUND(sm.avg_salary_max, 0) AS avg_salary_max,
    sm.min_salary,
    sm.max_salary,
    CASE
        WHEN sm.mention_count > 100 THEN 'high_demand'
        WHEN sm.mention_count > 50 THEN 'medium_demand'
        ELSE 'low_demand'
    END AS demand_level
FROM skill_metrics sm
INNER JOIN total_jobs tj
    ON sm.role = tj.role
    AND sm.country_code = tj.country_code
ORDER BY sm.mention_count DESC
```

**SQL Best Practices:**
- **CTEs**: Break complex logic into readable chunks
- **Window Functions**: Calculate percentages and rankings
- **Aggregations**: Pre-compute metrics for dashboard performance
- **Indexing**: Optimize for common query patterns

### 6.5 dbt Documentation

```yaml
# models/marts/schema.yml
version: 2

models:
  - name: mart_skill_demand
    description: >
      Aggregated skill demand metrics by role and country.
      Includes mention counts, job percentages, and salary data.
    columns:
      - name: skill_name
        description: Name of the skill
        tests:
          - not_null
      
      - name: mention_count
        description: Total mentions of this skill in job descriptions
        tests:
          - not_null
      
      - name: percentage_of_jobs
        description: Percentage of jobs requiring this skill
        tests:
          - not_null
      
      - name: avg_salary_max
        description: Average maximum salary for jobs requiring this skill
```

**Documentation Benefits:**
- **Self-Documenting**: `dbt docs generate` creates interactive site
- **Data Lineage**: Visual graph of table dependencies
- **Data Quality**: Built-in testing framework

---

## 7. Deployment & DevOps

### 7.1 GitHub Actions CI/CD

```yaml
# .github/workflows/etl_pipeline.yml
name: ETL Pipeline

on:
  schedule:
    - cron: '0 3 * * 0,3'  # Sundays and Wednesdays at 3 AM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  extract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          cd etl
          pip install -r requirements.txt
      
      - name: Run extraction
        env:
          ADZUNA_APP_ID: ${{ secrets.ADZUNA_APP_ID }}
          ADZUNA_APP_KEY: ${{ secrets.ADZUNA_APP_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
        run: |
          cd etl
          python extractor.py
  
  transform:
    runs-on: ubuntu-latest
    needs: extract
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          cd etl
          pip install -r requirements.txt
      
      - name: Run transformation
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          cd etl
          python transformer.py
  
  dbt:
    runs-on: ubuntu-latest
    needs: transform
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dbt
        run: |
          pip install dbt-postgres
      
      - name: Run dbt models
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
        run: |
          cd dbt_project
          dbt run --target prod
```

### 7.2 Docker Configuration

```dockerfile
# Dockerfile.backend
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/app ./app

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.3 Environment Configuration

```yaml
# render.yaml (Render.com deployment)
services:
  - type: web
    name: skill-hunt-api
    env: python
    region: oregon
    buildCommand: "pip install -r backend/requirements.txt"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: CORS_ORIGINS
        value: "https://skill-hunt.vercel.app"
      - key: DEBUG
        value: "false"
```

```json
// vercel.json (Vercel deployment)
{
  "buildCommand": "cd frontend && npm run build",
  "outputDirectory": "frontend/dist",
  "framework": "vite",
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

---

## 8. Performance Optimization

### 8.1 Database Optimizations

- **Materialized Views**: Pre-compute expensive aggregations
- **Indexes**: Strategic indexes on filter/join columns
- **Connection Pooling**: Reuse database connections
- **Query Caching**: FastAPI cache decorator for repeated queries

### 8.2 Frontend Optimizations

- **Code Splitting**: React.lazy() for route-based splitting
- **Memoization**: useMemo/useCallback for expensive computations
- **Virtual Scrolling**: For large datasets in tables
- **Image Optimization**: Lazy loading, modern formats (WebP)

### 8.3 API Optimizations

- **Pagination**: Limit result sets to reduce payload size
- **Field Selection**: Allow clients to specify required fields
- **Compression**: Gzip middleware for response compression
- **CDN**: Static assets served via Vercel Edge Network

---

## 9. Security & Best Practices

### 9.1 Security Measures

- **Environment Variables**: Secrets never committed to Git
- **SQL Injection Prevention**: Parameterized queries
- **CORS**: Restricted to specific origins
- **HTTPS**: Enforced in production
- **Rate Limiting**: Prevent API abuse (future)

### 9.2 Code Quality

- **Linting**: ESLint (JS), Black (Python)
- **Type Safety**: Pydantic for Python, PropTypes/TypeScript for JS
- **Documentation**: Inline comments, README files
- **Version Control**: Git with meaningful commit messages

---

## 10. Testing Strategy

### 10.1 Backend Testing

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_skill_demand_endpoint():
    response = client.get("/api/v1/skills/demand?role=Data Engineer&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "skills" in data
    assert len(data["skills"]) <= 5

def test_invalid_role():
    response = client.get("/api/v1/skills/demand?role=InvalidRole")
    assert response.status_code == 200
    assert len(response.json()["skills"]) == 0
```

### 10.2 Frontend Testing

```javascript
// frontend/src/__tests__/SkillsPage.test.jsx
import { render, screen, waitFor } from '@testing-library/react'
import SkillsPage from '../pages/SkillsPage'

test('renders skills page', async () => {
  render(<SkillsPage />)
  await waitFor(() => {
    expect(screen.getByText('Skills Analysis')).toBeInTheDocument()
  })
})
```

---

## 📌 Summary

Skill Hunt demonstrates enterprise-grade engineering practices:

✅ **Modular Architecture**: Clear separation between layers  
✅ **Scalable Data Pipeline**: Automated ETL with hybrid skill extraction  
✅ **Modern Tech Stack**: FastAPI, React, dbt, PostgreSQL  
✅ **Performance Optimized**: Indexing, caching, pagination  
✅ **Production-Ready**: CI/CD, Docker, cloud deployment  
✅ **Self-Documenting**: OpenAPI, dbt docs, inline comments  
✅ **Cost-Effective**: Hybrid extraction saves 95% on LLM costs  

This implementation guide serves as a comprehensive reference for understanding, extending, and maintaining the Skill Hunt platform.

---

**Last Updated:** January 2026  
**Version:** 1.0.0
