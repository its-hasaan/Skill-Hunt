-- ============================================================
-- MIGRATION 013 — Duplicate removal + job enrichment (Phase 1c)
-- ============================================================
-- stg_jobs.fingerprint       normalised company|title|places (etl/enrich/fingerprint.py)
-- stg_jobs.canonical_job_id  the listing shown for a duplicate group (ops.dedup)
-- staging.job_enrichment     eligibility for Pakistan/India + seniority, years,
--                            timezone, USD salary; one row per job, redone only
--                            when content_hash or the rules version changes.
--                            eligible_pk / eligible_in: NULL = unclear.
-- Idempotent.
-- ============================================================
BEGIN;

ALTER TABLE staging.stg_jobs ADD COLUMN IF NOT EXISTS fingerprint TEXT;
ALTER TABLE staging.stg_jobs ADD COLUMN IF NOT EXISTS canonical_job_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_stg_jobs_fingerprint ON staging.stg_jobs (fingerprint);

CREATE TABLE IF NOT EXISTS staging.job_enrichment (
    job_id                 INTEGER PRIMARY KEY REFERENCES staging.stg_jobs(job_id) ON DELETE CASCADE,
    content_hash           TEXT      NOT NULL,
    rules_version          INTEGER   NOT NULL,
    remote_scope           TEXT      NOT NULL,  -- worldwide|regions|countries|hybrid|onsite|unclear
    eligible_countries     TEXT[],
    eligible_regions       TEXT[],
    eligible_pk            BOOLEAN,
    eligible_in            BOOLEAN,
    eligibility_confidence NUMERIC(3,2),
    eligibility_evidence   TEXT,
    seniority              TEXT,               -- intern|junior|mid|senior|lead
    min_years              INTEGER,
    tz_overlap             TEXT,               -- americas|europe|apac
    salary_min_usd         NUMERIC,
    salary_max_usd         NUMERIC,
    method                 TEXT      NOT NULL, -- rules|llm
    model                  TEXT,
    enriched_at            TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_enrichment_method ON staging.job_enrichment (method);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON staging.job_enrichment FROM anon, authenticated';
    END IF;
END $$;

COMMIT;
