-- Minimal stand-ins for the Supabase auth schema and the pipeline tables the
-- copilot API reads (same column names/types as production).
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (id UUID PRIMARY KEY, email TEXT);
CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS staging_marts;

CREATE TABLE IF NOT EXISTS raw.jobs (
    id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'greenhouse',
    first_seen_at TIMESTAMP DEFAULT now(),
    last_seen_at TIMESTAMP DEFAULT now(),
    closed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.stg_jobs (
    job_id SERIAL PRIMARY KEY,
    job_platform_id TEXT,
    search_role TEXT,
    country_code TEXT,
    title TEXT,
    company_name TEXT,
    description TEXT,
    workplace_type TEXT,
    raw_job_id INTEGER,
    source TEXT
);

CREATE TABLE IF NOT EXISTS staging_marts.mart_job_feed (
    job_id INTEGER PRIMARY KEY,
    title TEXT, company_name TEXT, search_role TEXT, source TEXT, workplace_type TEXT,
    country_code TEXT, location_display TEXT, apply_url TEXT, job_posted_at TIMESTAMP,
    first_seen_at TIMESTAMP, last_seen_at TIMESTAMP, remote_scope TEXT,
    eligible_pk BOOLEAN, eligible_in BOOLEAN, eligible_countries TEXT[], eligible_regions TEXT[],
    eligibility_confidence NUMERIC(3,2), eligibility_evidence TEXT, eligibility_method TEXT,
    seniority TEXT, min_years INTEGER, tz_overlap TEXT, salary_min_usd NUMERIC, salary_max_usd NUMERIC,
    skills TEXT[], built_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.saved_searches (
    id BIGSERIAL PRIMARY KEY, user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE, name TEXT
);
CREATE TABLE IF NOT EXISTS public.resume_uploads (
    id BIGSERIAL PRIMARY KEY, user_id UUID, file_path TEXT, original_filename TEXT
);
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE, display_name TEXT
);
