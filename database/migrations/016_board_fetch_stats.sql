-- ============================================================
-- MIGRATION 016 — Board fetch rotation (Phase 1 volume)
-- ============================================================
-- last_fetched_at: when a connector last read the board's jobs (validation
--                  probes don't count), so each run reads the boards that
--                  waited longest and newly validated boards go first.
-- last_kept:       how many jobs the last fetch kept (tracked role + remote
--                  or Pakistan/India). Boards that kept none are re-read
--                  weekly instead of every run.
-- Idempotent.
-- ============================================================
BEGIN;

ALTER TABLE ops.companies ADD COLUMN IF NOT EXISTS last_fetched_at TIMESTAMPTZ;
ALTER TABLE ops.companies ADD COLUMN IF NOT EXISTS last_kept INTEGER;

CREATE INDEX IF NOT EXISTS companies_rotation_idx ON ops.companies (ats, active, last_fetched_at);

COMMIT;
