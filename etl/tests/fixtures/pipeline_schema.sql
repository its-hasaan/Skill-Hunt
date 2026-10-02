-- Subset of database/schema.sql touched by the ops tools, with identical column types.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE raw.jobs (
    id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    search_role TEXT NOT NULL DEFAULT 'Data Engineer',
    country_code TEXT NOT NULL DEFAULT 'remote',
    raw_data JSONB NOT NULL,
    source TEXT NOT NULL DEFAULT 'adzuna',
    extracted_at TIMESTAMP DEFAULT NOW(),
    extraction_batch_id UUID,
    skip_reason TEXT,
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP,
    CONSTRAINT raw_jobs_unique UNIQUE (job_platform_id, country_code)
);

CREATE TABLE staging.stg_jobs (
    job_id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    search_role TEXT NOT NULL DEFAULT 'Data Engineer',
    country_code TEXT NOT NULL DEFAULT 'remote',
    title TEXT,
    company_name TEXT,
    description TEXT,
    location_display TEXT,
    location_areas TEXT[],
    category_tag TEXT,
    category_label TEXT,
    salary_min NUMERIC,
    salary_max NUMERIC,
    salary_is_predicted BOOLEAN DEFAULT FALSE,
    salary_currency TEXT DEFAULT 'GBP',
    contract_type TEXT,
    contract_time TEXT,
    redirect_url TEXT,
    job_posted_at TIMESTAMP,
    extracted_at TIMESTAMP,
    processed_at TIMESTAMP DEFAULT NOW(),
    raw_job_id INTEGER REFERENCES raw.jobs(id),
    source TEXT NOT NULL DEFAULT 'adzuna',
    workplace_type TEXT,
    CONSTRAINT stg_jobs_unique UNIQUE (job_platform_id, country_code)
);

CREATE TABLE staging.stg_job_skills (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES staging.stg_jobs(job_id) ON DELETE CASCADE,
    skill_id INTEGER,
    skill_name TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1,
    extracted_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT stg_job_skills_unique UNIQUE (job_id, skill_id)
);

CREATE TABLE staging.dim_skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name TEXT UNIQUE NOT NULL,
    skill_category TEXT,
    skill_subcategory TEXT,
    aliases TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
