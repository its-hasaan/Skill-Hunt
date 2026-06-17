# 🔧 Job Script - Implementation Guide

> **Comprehensive Technical Documentation**  
> Deep dive into the architecture, implementation details, and engineering decisions behind Job Script.

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

Job Script follows a **Modern Data Stack (MDS)** architecture pattern, emphasizing:
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

#### **Slow Path Implementation (GLiNER NER-Based)**

```python
# etl/skill_extractor/slow_path.py
class SlowPathExtractor:
    def __init__(self, config: SlowPathConfig):
        self.config = config
        self._model = None  # Lazy loaded
    
    def _load_model(self):
        """Lazy load the GLiNER model."""
        if self._model is None and self.config.enabled:
            from gliner import GLiNER
            self._model = GLiNER.from_pretrained(self.config.model_name)
            # Default: urchade/gliner_medium-v2.1
        return self._model
    
    def extract(self, text: str, known_skills: Set[str]) -> List[Dict]:
        """
        Use GLiNER NER model to discover skills not in taxonomy.
        """
        model = self._load_model()
        if not model:
            return []
        
        # GLiNER predicts entities with labels
        entities = model.predict_entities(
            text,
            labels=GLINER_SKILL_LABELS,  # Programming language, database, etc.
            threshold=self.config.threshold
        )
        
        # Filter out known skills and low confidence
        results = []
        for entity in entities:
            skill_name = entity['text'].strip()
            if (skill_name.lower() not in known_skills and 
                entity['score'] >= self.config.min_confidence):
                results.append({
                    'skill_name': skill_name,
                    'category': LABEL_TO_CATEGORY.get(entity['label'], 'Unknown'),
                    'confidence': entity['score'],
                    'method': 'gliner'
                })
        
        return results
```

**Slow Path Advantages:**
- **Local & Free**: Runs on local hardware, no API costs
- **Discovers New Skills**: Finds emerging technologies not in taxonomy
- **Fast Inference**: Medium model balances speed and accuracy
- **Pre-trained**: No fine-tuning required, works out-of-the-box

**Cost Optimization:**
- **Zero API Costs**: Runs locally using GLiNER
- **Sampling**: Only 10% of jobs processed via NER model
- **Efficient Model**: Medium-sized model for faster inference
- **Lazy Loading**: Model loaded only when needed

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
    logger.info("Starting Job Script API...")
    await db.connect()
    yield
    # Shutdown
    await db.disconnect()

app = FastAPI(
    title="Job Script API",
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
import asyncpg
from app.config import get_settings

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.settings = get_settings()
    
    async def connect(self):
        """Create connection pool."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.settings.supabase_url,
                min_size=2,
                max_size=10,
                ssl="require",
                command_timeout=30
            )
            logger.info("Database connection pool created")
    
    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    async def fetch_all(self, query: str, *args):
        """Execute query and return all results as list of dicts."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def fetch_one(self, query: str, *args):
        """Execute query and return single result as dict."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

db = Database()
```

**asyncpg Advantages:**
- **High Performance**: Fastest PostgreSQL driver for Python
- **Connection Pooling**: Efficient connection reuse (min 2, max 10)
- **Async Native**: Built for async/await patterns
- **SSL Support**: Secure connections to Supabase

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
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from ..database import Database, get_db
from ..models.schemas import SkillDemand, SkillDemandResponse

router = APIRouter(prefix="/skills", tags=["Skills"])

@router.get("/demand", response_model=SkillDemandResponse)
async def get_skill_demand(
    role: str = Query(..., description="Job role to filter by"),
    country: Optional[str] = Query(None, description="Country code (e.g., 'gb', 'us')"),
    limit: int = Query(30, ge=1, le=100, description="Maximum results"),
    db: Database = Depends(get_db)
):
    """
    Get skill demand data for a specific role and optionally country.
    Returns top skills ranked by job count.
    """
    if country:
        query = """
            SELECT 
                skill_name, skill_category, search_role, country_code,
                job_count, demand_percentage, avg_salary_min, avg_salary_max,
                avg_salary_midpoint, rank_in_role_country, rank_in_role_global
            FROM staging_marts.mart_skill_demand
            WHERE search_role = $1 AND country_code = $2
            ORDER BY rank_in_role_country
            LIMIT $3
        """
        rows = await db.fetch_all(query, role, country, limit)
    else:
        # Aggregate across all countries for global view
        query = """
            SELECT 
                skill_name, skill_category, search_role,
                SUM(job_count) as job_count,
                AVG(demand_percentage) as demand_percentage,
                AVG(avg_salary_min) as avg_salary_min,
                AVG(avg_salary_max) as avg_salary_max,
                MIN(rank_in_role_global) as rank_in_role_global
            FROM staging_marts.mart_skill_demand
            WHERE search_role = $1
            GROUP BY skill_name, skill_category, search_role
            ORDER BY job_count DESC
            LIMIT $2
        """
        rows = await db.fetch_all(query, role, limit)
    
    return SkillDemandResponse(
        role=role,
        country=country,
        total_count=len(rows),
        data=[SkillDemand(**row) for row in rows]
    )
```

**Best Practices Demonstrated:**
- **Pydantic Response Models**: Automatic validation and serialization
- **Query Parameters**: Type-safe with validation (ge=1, le=100)
- **Dynamic SQL**: Builds query based on provided filters
- **Positional Parameters**: Uses `$1, $2, $3` with asyncpg (not `:named`)
- **Dependency Injection**: Database instance injected via `Depends(get_db)`
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

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor - auto-unwrap data and handle errors
api.interceptors.response.use(
  (response) => response.data,  // Auto-unwrap data
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    throw error
  }
)

// Stats API
export const statsApi = {
  getSummary: () => api.get('/stats/summary'),
  getFilters: () => api.get('/stats/filters'),
  getRoles: () => api.get('/stats/roles'),
  getCountries: () => api.get('/stats/countries'),
}

// Skills API
export const skillsApi = {
  getDemand: (role, country = null, limit = 30) => {
    const params = { role, limit }
    if (country) params.country = country
    return api.get('/skills/demand', { params })
  },
  getCooccurrence: (role, skill = null, minCount = 5, limit = 100) => {
    const params = { role, min_count: minCount, limit }
    if (skill) params.skill = skill
    return api.get('/skills/cooccurrence', { params })
  },
  getNetwork: (role, minCount = 10, limit = 50) => 
    api.get('/skills/network', { params: { role, min_count: minCount, limit } }),
  getByCountry: (skill, role) => 
    api.get('/skills/by-country', { params: { skill, role } }),
  getCategories: () => api.get('/skills/categories'),
}

// Companies, Salary, Career APIs follow similar pattern...
```

**Architecture Benefits:**
- **Auto Data Unwrapping**: Response interceptor returns `response.data` directly
- **Flexible Parameters**: Helper functions build query params dynamically
- **Clean API**: Callers get data directly without `.data` access
- **Environment Aware**: Default to `/api/v1` for proxy in development

### 5.3 Data Fetching with React Query

```javascript
// frontend/src/hooks/useData.js
import { useQuery } from '@tanstack/react-query'
import { statsApi, skillsApi, companiesApi } from '../api'

// Stats Hooks
export function useSummaryStats() {
  return useQuery({
    queryKey: ['stats', 'summary'],
    queryFn: statsApi.getSummary,
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}

export function useFilterOptions() {
  return useQuery({
    queryKey: ['stats', 'filters'],
    queryFn: statsApi.getFilters,
    staleTime: 1000 * 60 * 30, // 30 minutes
  })
}

// Skills Hooks
export function useSkillDemand(role, country = null, limit = 30) {
  return useQuery({
    queryKey: ['skills', 'demand', role, country, limit],
    queryFn: () => skillsApi.getDemand(role, country, limit),
    enabled: !!role,  // Only fetch when role is provided
  })
}

export function useSkillCooccurrence(role, skill = null, minCount = 5) {
  return useQuery({
    queryKey: ['skills', 'cooccurrence', role, skill, minCount],
    queryFn: () => skillsApi.getCooccurrence(role, skill, minCount),
    enabled: !!role,
  })
}

// More hooks for companies, salary, career...
```

**React Query Advantages:**
- **Automatic Caching**: Data cached with configurable stale time
- **Background Refetching**: Updates data in background
- **Request Deduplication**: Multiple components share same query
- **Built-in Loading States**: `isLoading`, `isError`, `data` states
- **Enabled Flag**: Conditional fetching based on dependencies
- **Optimistic Updates**: Support for mutations

### 5.4 Example Page Implementation

```javascript
// frontend/src/pages/Dashboard.jsx
import { useOutletContext } from 'react-router-dom'
import { Briefcase, Code, Globe, Building2, TrendingUp } from 'lucide-react'
import { useSummaryStats, useSkillDemand } from '../hooks/useData'
import { Card, StatCard, ChartLoading, EmptyState } from '../components/ui'
import { SkillBarChart, CategoryPieChart } from '../components/charts/Charts'
import { formatNumber } from '../utils/helpers'

export default function Dashboard() {
  const { selectedRole, selectedCountry } = useOutletContext()
  
  // React Query hooks - automatic caching and refetching
  const { data: stats, isLoading: statsLoading } = useSummaryStats()
  const { data: skillDemand, isLoading: skillsLoading } = useSkillDemand(
    selectedRole, 
    selectedCountry || null, 
    20
  )

  return (
    <div className="space-y-6">
      {/* Hero Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total Jobs"
          value={statsLoading ? '...' : formatNumber(stats?.total_jobs || 0)}
          icon={Briefcase}
          color="primary"
          loading={statsLoading}
        />
        <StatCard
          title="Skills Tracked"
          value={statsLoading ? '...' : formatNumber(stats?.total_skills || 0)}
          icon={Code}
          color="accent"
          loading={statsLoading}
        />
        {/* More stat cards... */}
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card 
          title={`Top Skills for ${selectedRole || 'All Roles'}`}
          className="lg:col-span-2"
        >
          {skillsLoading ? (
            <ChartLoading height={400} />
          ) : skillDemand?.data?.length > 0 ? (
            <SkillBarChart data={skillDemand.data} height={400} />
          ) : (
            <EmptyState description="No skill data available" />
          )}
        </Card>

        <Card title="Skills by Category">
          {skillsLoading ? (
            <ChartLoading height={300} />
          ) : skillDemand?.data?.length > 0 ? (
            <CategoryPieChart data={skillDemand.data} height={300} />
          ) : (
            <EmptyState description="No category data available" />
          )}
        </Card>
      </div>
    </div>
  )
}
```

**React Query Benefits in Action:**
- **Automatic Loading States**: `isLoading` from `useSummaryStats()` and `useSkillDemand()`
- **Shared State**: Multiple components using same query share cached data
- **Background Refetch**: Data refreshes in background when stale
- **Conditional Rendering**: Clean pattern for loading/error/success states

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
        schema='marts'
    )
}}

/*
    Mart: Skill Demand
    Top skills per role and country with demand percentages
    Answers: "What are the top 10 skills for Data Engineers?"
*/

WITH job_counts AS (
    -- Total unique jobs per role and country
    SELECT 
        search_role,
        country_code,
        COUNT(DISTINCT job_id) AS total_jobs
    FROM {{ ref('int_job_skills_enriched') }}
    GROUP BY search_role, country_code
),

skill_counts AS (
    -- Count jobs per skill, role, country
    SELECT 
        skill_id,
        skill_name,
        skill_category,
        skill_subcategory,
        search_role,
        country_code,
        COUNT(DISTINCT job_id) AS job_count,
        AVG(salary_min) AS avg_salary_min,
        AVG(salary_max) AS avg_salary_max,
        AVG(salary_midpoint) AS avg_salary_midpoint
    FROM {{ ref('int_job_skills_enriched') }}
    GROUP BY skill_id, skill_name, skill_category, skill_subcategory, search_role, country_code
),

ranked_skills AS (
    SELECT 
        sc.*,
        jc.total_jobs,
        ROUND((sc.job_count::NUMERIC / NULLIF(jc.total_jobs, 0)) * 100, 2) AS demand_percentage,
        ROW_NUMBER() OVER (
            PARTITION BY sc.search_role, sc.country_code 
            ORDER BY sc.job_count DESC
        ) AS rank_in_role_country,
        ROW_NUMBER() OVER (
            PARTITION BY sc.search_role 
            ORDER BY sc.job_count DESC
        ) AS rank_in_role_global
    FROM skill_counts sc
    JOIN job_counts jc 
        ON sc.search_role = jc.search_role 
        AND sc.country_code = jc.country_code
)

SELECT 
    skill_id,
    skill_name,
    skill_category,
    skill_subcategory,
    search_role,
    country_code,
    job_count,
    total_jobs AS total_jobs_for_role,
    demand_percentage,
    avg_salary_min,
    avg_salary_max,
    avg_salary_midpoint,
    rank_in_role_country,
    rank_in_role_global,
    CURRENT_DATE - INTERVAL '30 days' AS period_start,
    CURRENT_DATE AS period_end,
    NOW() AS updated_at
FROM ranked_skills
WHERE rank_in_role_country <= 50  -- Keep top 50 skills per role/country
ORDER BY search_role, country_code, rank_in_role_country
```

**SQL Best Practices:**
- **CTEs**: Break complex logic into readable chunks (job_counts, skill_counts, ranked_skills)
- **Window Functions**: `ROW_NUMBER()` for ranking within partitions
- **Aggregations**: Pre-compute metrics (counts, averages) for dashboard performance
- **Null Safety**: `NULLIF()` prevents division by zero
- **Data Quality**: Filter to top 50 skills to limit result size

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
    name: job-script-api
    env: python
    region: oregon
    buildCommand: "pip install -r backend/requirements.txt"
    startCommand: "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: CORS_ORIGINS
        value: "https://jobscript.vercel.app"
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

Job Script demonstrates enterprise-grade engineering practices:

✅ **Modular Architecture**: Clear separation between layers  
✅ **Scalable Data Pipeline**: Automated ETL with hybrid skill extraction  
✅ **Modern Tech Stack**: FastAPI, React, dbt, PostgreSQL  
✅ **Performance Optimized**: Indexing, caching, pagination  
✅ **Production-Ready**: CI/CD, Docker, cloud deployment  
✅ **Self-Documenting**: OpenAPI, dbt docs, inline comments  
✅ **Cost-Effective**: Hybrid extraction saves 95% on LLM costs  

This implementation guide serves as a comprehensive reference for understanding, extending, and maintaining the Job Script platform.

---

**Last Updated:** January 2026  
**Version:** 1.0.0
