-- ============================================================
-- MIGRATION 012 — Company job-board registry (Phase 1b)
-- ============================================================
-- One row per company board on a hiring system's public job-board API
-- (greenhouse | lever | ashby | smartrecruiters). Filled by the seed file
-- and Common Crawl discovery; `ops.companies validate` probes each board.
-- active: NULL = candidate (never succeeded yet), TRUE = live,
--         FALSE = given up after 3 consecutive failures.
-- Idempotent.
-- ============================================================
BEGIN;

CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.companies (
    id              BIGSERIAL PRIMARY KEY,
    ats             TEXT        NOT NULL,
    board_token     TEXT        NOT NULL,
    name            TEXT,
    active          BOOLEAN,
    fail_count      INTEGER     NOT NULL DEFAULT 0,
    last_checked_at TIMESTAMPTZ,
    last_job_count  INTEGER,
    discovered_via  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT companies_ats_board_unique UNIQUE (ats, board_token)
);

CREATE INDEX IF NOT EXISTS companies_ats_active_idx ON ops.companies (ats, active);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON SCHEMA ops FROM anon, authenticated';
    END IF;
END $$;

COMMIT;
