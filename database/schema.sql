-- ============================================================
-- SKILL HUNT DATABASE SCHEMA
-- Supabase PostgreSQL Schema for Job Market Analysis
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- SCHEMA SETUP
-- ============================================================
-- Raw layer: Landing zone for API data (EL in ELT)
CREATE SCHEMA IF NOT EXISTS raw;

-- Staging layer: Cleaned and normalized data
CREATE SCHEMA IF NOT EXISTS staging;

-- Marts layer: Business-ready aggregations for dashboard
CREATE SCHEMA IF NOT EXISTS marts;

-- Archive layer: Historical snapshots
CREATE SCHEMA IF NOT EXISTS archive;

-- ============================================================
-- REFERENCE/LOOKUP TABLES
-- ============================================================

-- Supported job roles for extraction
CREATE TABLE IF NOT EXISTS staging.dim_job_roles (
    role_id SERIAL PRIMARY KEY,
    role_name TEXT UNIQUE NOT NULL,
    role_category TEXT, -- e.g., 'Data', 'Engineering', 'Security'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert the 15 target roles
INSERT INTO staging.dim_job_roles (role_name, role_category) VALUES
    ('Data Engineer', 'Data'),
    ('Analytics Engineer', 'Data'),
    ('Data Scientist', 'Data'),
    ('Data Analyst', 'Data'),
    ('Business Intelligence Developer', 'Data'),
    ('Machine Learning Engineer', 'AI/ML'),
    ('AI Engineer', 'AI/ML'),
    ('Computer Vision Engineer', 'AI/ML'),
    ('Backend Developer', 'Engineering'),
    ('Frontend Developer', 'Engineering'),
    ('Full Stack Developer', 'Engineering'),
    ('Mobile Developer', 'Engineering'),
    ('DevOps Engineer', 'Operations'),
    ('Cloud Architect', 'Operations'),
    ('Cyber Security Engineer', 'Security')
ON CONFLICT (role_name) DO NOTHING;

-- Supported countries for extraction
CREATE TABLE IF NOT EXISTS staging.dim_countries (
    country_code TEXT PRIMARY KEY, -- ISO code used by Adzuna
    country_name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Adzuna supported countries
INSERT INTO staging.dim_countries (country_code, country_name) VALUES
    ('gb', 'United Kingdom'),
    ('us', 'United States'),
    ('au', 'Australia'),
    ('at', 'Austria'),
    ('be', 'Belgium'),
    ('br', 'Brazil'),
    ('ca', 'Canada'),
    ('de', 'Germany'),
    ('fr', 'France'),
    ('in', 'India'),
    ('it', 'Italy'),
    ('mx', 'Mexico'),
    ('nl', 'Netherlands'),
    ('nz', 'New Zealand'),
    ('pl', 'Poland'),
    ('ru', 'Russia'),
    ('sg', 'Singapore'),
    ('za', 'South Africa')
ON CONFLICT (country_code) DO NOTHING;

-- Master skills taxonomy
CREATE TABLE IF NOT EXISTS staging.dim_skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name TEXT UNIQUE NOT NULL,          -- Canonical name: "Python"
    skill_category TEXT,                       -- e.g., 'Programming Language', 'Cloud', 'Database'
    skill_subcategory TEXT,                    -- e.g., 'AWS Services', 'SQL Databases'
    aliases TEXT[],                            -- Alternative names: ["python3", "py"]
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- RAW LAYER - Landing Zone
-- ============================================================

-- Raw job postings directly from API
CREATE TABLE IF NOT EXISTS raw.jobs (
    id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,            -- Adzuna job ID
    search_role TEXT NOT NULL,                -- Role searched for
    country_code TEXT NOT NULL,               -- Country code used in API call
    raw_data JSONB NOT NULL,                  -- Complete API response
    extracted_at TIMESTAMP DEFAULT NOW(),
    extraction_batch_id UUID DEFAULT uuid_generate_v4(),
    
    -- Composite unique constraint (same job can appear in different countries)
    CONSTRAINT raw_jobs_unique UNIQUE (job_platform_id, country_code)
);

-- Index for faster querying
CREATE INDEX IF NOT EXISTS idx_raw_jobs_extracted_at ON raw.jobs(extracted_at);
CREATE INDEX IF NOT EXISTS idx_raw_jobs_search_role ON raw.jobs(search_role);
CREATE INDEX IF NOT EXISTS idx_raw_jobs_country ON raw.jobs(country_code);
CREATE INDEX IF NOT EXISTS idx_raw_jobs_batch ON raw.jobs(extraction_batch_id);

-- ============================================================
-- STAGING LAYER - Cleaned & Normalized
-- ============================================================

-- Cleaned job postings (flattened from JSONB)
CREATE TABLE IF NOT EXISTS staging.stg_jobs (
    job_id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    search_role TEXT NOT NULL,
    country_code TEXT NOT NULL,
    
    -- Core job info
    title TEXT,
    company_name TEXT,
    description TEXT,
    
    -- Location details
    location_display TEXT,
    location_areas TEXT[],                    -- Hierarchical: ['UK', 'London', 'Central London']
    
    -- Category
    category_tag TEXT,                        -- e.g., 'it-jobs'
    category_label TEXT,                      -- e.g., 'IT Jobs'
    
    -- Salary (nullable - not all jobs have salary)
    salary_min NUMERIC,
    salary_max NUMERIC,
    salary_is_predicted BOOLEAN DEFAULT FALSE,
    salary_currency TEXT DEFAULT 'GBP',       -- Derived from country
    
    -- Contract details
    contract_type TEXT,                       -- 'full_time', 'part_time', 'contract'
    contract_time TEXT,                       -- 'permanent', 'temporary'
    
    -- URLs
    redirect_url TEXT,
    
    -- Timestamps
    job_posted_at TIMESTAMP,                  -- When job was posted on Adzuna
    extracted_at TIMESTAMP,                   -- When we extracted it
    processed_at TIMESTAMP DEFAULT NOW(),     -- When we processed/cleaned it
    
    -- Source tracking
    raw_job_id INTEGER REFERENCES raw.jobs(id),
    
    CONSTRAINT stg_jobs_unique UNIQUE (job_platform_id, country_code)
);

-- Indexes for staging jobs
CREATE INDEX IF NOT EXISTS idx_stg_jobs_search_role ON staging.stg_jobs(search_role);
CREATE INDEX IF NOT EXISTS idx_stg_jobs_country ON staging.stg_jobs(country_code);
CREATE INDEX IF NOT EXISTS idx_stg_jobs_company ON staging.stg_jobs(company_name);
CREATE INDEX IF NOT EXISTS idx_stg_jobs_posted_at ON staging.stg_jobs(job_posted_at);

-- Skills extracted from job descriptions
CREATE TABLE IF NOT EXISTS staging.stg_job_skills (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES staging.stg_jobs(job_id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES staging.dim_skills(skill_id),
    skill_name TEXT NOT NULL,                 -- Denormalized for convenience
    mention_count INTEGER DEFAULT 1,          -- How many times skill appears in description
    extracted_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT stg_job_skills_unique UNIQUE (job_id, skill_id)
);

-- Index for skill analysis
CREATE INDEX IF NOT EXISTS idx_stg_job_skills_skill ON staging.stg_job_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_stg_job_skills_job ON staging.stg_job_skills(job_id);

-- ============================================================
-- MARTS LAYER - Business Aggregations
-- ============================================================

-- Aggregated skill demand per role (refreshed by dbt)
CREATE TABLE IF NOT EXISTS marts.skill_demand (
    id SERIAL PRIMARY KEY,
    skill_id INTEGER REFERENCES staging.dim_skills(skill_id),
    skill_name TEXT NOT NULL,
    skill_category TEXT,
    search_role TEXT NOT NULL,
    country_code TEXT,                        -- NULL means global aggregate
    
    -- Metrics
    job_count INTEGER,                        -- Number of jobs mentioning this skill
    total_jobs_for_role INTEGER,              -- Total jobs for this role (for %)
    demand_percentage NUMERIC(5,2),           -- % of jobs requiring this skill
    avg_salary_min NUMERIC,
    avg_salary_max NUMERIC,
    
    -- Time window
    period_start DATE,
    period_end DATE,
    
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT skill_demand_unique UNIQUE (skill_id, search_role, country_code, period_start)
);

-- Skill co-occurrence matrix
CREATE TABLE IF NOT EXISTS marts.skill_cooccurrence (
    id SERIAL PRIMARY KEY,
    skill_id_1 INTEGER REFERENCES staging.dim_skills(skill_id),
    skill_name_1 TEXT NOT NULL,
    skill_id_2 INTEGER REFERENCES staging.dim_skills(skill_id),
    skill_name_2 TEXT NOT NULL,
    search_role TEXT,                         -- NULL means across all roles
    
    -- Metrics
    cooccurrence_count INTEGER,               -- Jobs where both skills appear
    skill_1_total INTEGER,                    -- Total jobs with skill 1
    skill_2_total INTEGER,                    -- Total jobs with skill 2
    jaccard_similarity NUMERIC(5,4),          -- Intersection / Union
    
    period_start DATE,
    period_end DATE,
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT skill_cooccurrence_unique UNIQUE (skill_id_1, skill_id_2, search_role, period_start)
);

-- Company hiring leaderboard
CREATE TABLE IF NOT EXISTS marts.company_leaderboard (
    id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    search_role TEXT,                         -- NULL means all roles
    country_code TEXT,                        -- NULL means global
    
    -- Metrics
    job_count INTEGER,
    avg_salary_min NUMERIC,
    avg_salary_max NUMERIC,
    roles_hiring TEXT[],                      -- Array of roles this company is hiring for
    
    -- Contract breakdown
    full_time_count INTEGER DEFAULT 0,
    part_time_count INTEGER DEFAULT 0,
    contract_count INTEGER DEFAULT 0,
    
    period_start DATE,
    period_end DATE,
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT company_leaderboard_unique UNIQUE (company_name, search_role, country_code, period_start)
);

-- Role similarity matrix (skill overlap between roles)
CREATE TABLE IF NOT EXISTS marts.role_similarity (
    id SERIAL PRIMARY KEY,
    role_1 TEXT NOT NULL,
    role_2 TEXT NOT NULL,
    
    -- Metrics
    shared_skills_count INTEGER,              -- Number of skills in common
    role_1_unique_skills INTEGER,             -- Skills only in role 1
    role_2_unique_skills INTEGER,             -- Skills only in role 2
    jaccard_similarity NUMERIC(5,4),          -- Shared / Total unique skills
    overlap_coefficient NUMERIC(5,4),         -- Shared / min(role1_skills, role2_skills)
    top_shared_skills TEXT[],                 -- Top 10 shared skills
    
    period_start DATE,
    period_end DATE,
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT role_similarity_unique UNIQUE (role_1, role_2, period_start)
);

-- Salary insights by skill
CREATE TABLE IF NOT EXISTS marts.salary_by_skill (
    id SERIAL PRIMARY KEY,
    skill_id INTEGER REFERENCES staging.dim_skills(skill_id),
    skill_name TEXT NOT NULL,
    search_role TEXT,                         -- NULL means all roles
    country_code TEXT,                        -- NULL means global
    
    -- Salary metrics for jobs WITH this skill
    jobs_with_skill INTEGER,
    avg_salary_with_skill NUMERIC,
    median_salary_with_skill NUMERIC,
    min_salary_with_skill NUMERIC,
    max_salary_with_skill NUMERIC,
    
    -- Market average (all jobs for comparison)
    total_jobs_in_market INTEGER,
    market_avg_salary NUMERIC,
    
    -- Salary premium
    salary_premium_absolute NUMERIC,          -- avg_with_skill - market_avg
    salary_premium_percentage NUMERIC(5,2),   -- % above market
    
    period_start DATE,
    period_end DATE,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- ARCHIVE LAYER - Historical Snapshots
-- ============================================================

-- Weekly snapshots of skill demand
CREATE TABLE IF NOT EXISTS archive.skill_demand_history (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    skill_id INTEGER,
    skill_name TEXT NOT NULL,
    search_role TEXT NOT NULL,
    country_code TEXT,
    job_count INTEGER,
    demand_percentage NUMERIC(5,2),
    avg_salary_min NUMERIC,
    avg_salary_max NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_skill_demand_history_date ON archive.skill_demand_history(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_skill_demand_history_skill ON archive.skill_demand_history(skill_name, search_role);

-- ============================================================
-- UTILITY FUNCTIONS
-- ============================================================

-- Function to archive current skill demand before refresh
CREATE OR REPLACE FUNCTION archive_skill_demand()
RETURNS void AS $$
BEGIN
    INSERT INTO archive.skill_demand_history (
        snapshot_date, skill_id, skill_name, search_role, country_code,
        job_count, demand_percentage, avg_salary_min, avg_salary_max
    )
    SELECT 
        CURRENT_DATE,
        skill_id, skill_name, search_role, country_code,
        job_count, demand_percentage, avg_salary_min, avg_salary_max
    FROM marts.skill_demand;
END;
$$ LANGUAGE plpgsql;

-- Function to get currency by country
CREATE OR REPLACE FUNCTION get_currency_by_country(country TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN CASE country
        WHEN 'gb' THEN 'GBP'
        WHEN 'us' THEN 'USD'
        WHEN 'au' THEN 'AUD'
        WHEN 'ca' THEN 'CAD'
        WHEN 'de' THEN 'EUR'
        WHEN 'fr' THEN 'EUR'
        WHEN 'it' THEN 'EUR'
        WHEN 'nl' THEN 'EUR'
        WHEN 'at' THEN 'EUR'
        WHEN 'be' THEN 'EUR'
        WHEN 'in' THEN 'INR'
        WHEN 'br' THEN 'BRL'
        WHEN 'mx' THEN 'MXN'
        WHEN 'pl' THEN 'PLN'
        WHEN 'ru' THEN 'RUB'
        WHEN 'sg' THEN 'SGD'
        WHEN 'za' THEN 'ZAR'
        WHEN 'nz' THEN 'NZD'
        ELSE 'USD'
    END;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- GRANTS (adjust based on your Supabase roles)
-- ============================================================
-- These are optional - Supabase handles auth differently
-- GRANT USAGE ON SCHEMA raw, staging, marts, archive TO authenticated;
-- GRANT SELECT ON ALL TABLES IN SCHEMA marts TO anon;
