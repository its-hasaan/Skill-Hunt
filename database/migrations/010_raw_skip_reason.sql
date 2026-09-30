-- ============================================================
-- MIGRATION 010 — raw.jobs.skip_reason
-- ============================================================
-- The transformer now lets the job TITLE decide the role for keyword-
-- searched sources (Adzuna, Jooble). A raw row whose title matches no
-- tracked role is marked here instead of being transformed, so it is not
-- fetched again on every run.
-- Idempotent.
-- ============================================================
BEGIN;
ALTER TABLE raw.jobs ADD COLUMN IF NOT EXISTS skip_reason TEXT;
COMMIT;
