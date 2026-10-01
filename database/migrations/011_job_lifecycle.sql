-- ============================================================
-- MIGRATION 011 — Job lifecycle + workplace type (Phase 1b)
-- ============================================================
-- raw.jobs records every sighting: first_seen_at, last_seen_at, and
-- closed_at once a job stops appearing (company job boards: missing from
-- a successful full fetch; feed sources: unseen for 14 days). The feed
-- (Phase 1c) shows only open jobs.
-- staging.stg_jobs.workplace_type: remote | hybrid | onsite.
-- Idempotent.
-- ============================================================
BEGIN;

ALTER TABLE raw.jobs ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMP;
ALTER TABLE raw.jobs ADD COLUMN IF NOT EXISTS last_seen_at  TIMESTAMP;
ALTER TABLE raw.jobs ADD COLUMN IF NOT EXISTS closed_at     TIMESTAMP;

UPDATE raw.jobs SET first_seen_at = extracted_at WHERE first_seen_at IS NULL;
UPDATE raw.jobs SET last_seen_at  = extracted_at WHERE last_seen_at IS NULL;

ALTER TABLE raw.jobs ALTER COLUMN first_seen_at SET DEFAULT now();
ALTER TABLE raw.jobs ALTER COLUMN last_seen_at  SET DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_raw_jobs_open ON raw.jobs (source, last_seen_at) WHERE closed_at IS NULL;

ALTER TABLE staging.stg_jobs ADD COLUMN IF NOT EXISTS workplace_type TEXT;

COMMIT;
