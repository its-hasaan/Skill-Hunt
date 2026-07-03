-- ============================================================
-- MIGRATION 001 — Multi-Source Ingestion
-- ============================================================
-- Adds support for ingesting jobs from multiple providers
-- (RemoteOK, WeWorkRemotely, Arbeitnow, Jobicy, Himalayas,
--  Jooble, The Muse, USAJobs, ...) alongside the existing
-- Adzuna pipeline — WITHOUT breaking anything already in place.
--
-- Safe to run repeatedly (idempotent). Run it once against your
-- live Supabase database:
--
--   psql "$SUPABASE_URL" -f database/migrations/001_multi_source_ingestion.sql
--
-- or paste it into the Supabase SQL editor.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Provenance column
-- ------------------------------------------------------------
-- Every raw/staging row records which provider it came from.
-- Existing rows default to 'adzuna', so the current pipeline and
-- the extractor's `ON CONFLICT (job_platform_id, country_code)`
-- keep working unchanged. New connectors namespace their
-- job_platform_id as "<source>:<external_id>" (e.g. "remoteok:98765"),
-- so IDs never collide across providers and the existing unique
-- constraint still guarantees idempotency.
ALTER TABLE raw.jobs         ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'adzuna';
ALTER TABLE staging.stg_jobs ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'adzuna';

CREATE INDEX IF NOT EXISTS idx_raw_jobs_source ON raw.jobs(source);
CREATE INDEX IF NOT EXISTS idx_stg_jobs_source ON staging.stg_jobs(source);

-- ------------------------------------------------------------
-- 2. New geographies for the Asia / remote focus
-- ------------------------------------------------------------
-- 'pk'     -> local Pakistan postings (via Jooble, etc.)
-- 'remote' -> the remote-jobs boards (RemoteOK, WeWorkRemotely,
--             Arbeitnow, Jobicy, Himalayas). These are worldwide
--             remote roles that talent in Pakistan/India can apply to.
-- India ('in') already exists and is covered by Adzuna + Jooble.
INSERT INTO staging.dim_countries (country_code, country_name) VALUES
    ('pk',     'Pakistan'),
    ('remote', 'Remote / Worldwide')
ON CONFLICT (country_code) DO NOTHING;

-- ------------------------------------------------------------
-- 3. Currency mapping for the new geographies
-- ------------------------------------------------------------
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
        WHEN 'pk' THEN 'PKR'
        WHEN 'remote' THEN 'USD'
        ELSE 'USD'
    END;
END;
$$ LANGUAGE plpgsql;

COMMIT;

-- ------------------------------------------------------------
-- Verify (optional):
--   SELECT source, COUNT(*) FROM raw.jobs GROUP BY source;
--   SELECT country_code, country_name FROM staging.dim_countries
--   WHERE country_code IN ('pk','remote','in');
-- ------------------------------------------------------------
