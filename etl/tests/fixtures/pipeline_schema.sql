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
    skip_reason TEXT,
    CONSTRAINT raw_jobs_unique UNIQUE (job_platform_id, country_code)
);

CREATE TABLE staging.stg_jobs (
    job_id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    search_role TEXT NOT NULL DEFAULT 'Data Engineer',
    country_code TEXT NOT NULL DEFAULT 'remote',
    title TEXT,
    job_posted_at TIMESTAMP,
    extracted_at TIMESTAMP,
    processed_at TIMESTAMP DEFAULT NOW(),
    raw_job_id INTEGER REFERENCES raw.jobs(id),
    source TEXT NOT NULL DEFAULT 'adzuna',
    CONSTRAINT stg_jobs_unique UNIQUE (job_platform_id, country_code)
);

CREATE TABLE staging.stg_job_skills (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES staging.stg_jobs(job_id) ON DELETE CASCADE,
    skill_id INTEGER,
    skill_name TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1
);
