-- ============================================================
-- MIGRATION 007 — Pipeline run ledger (ops.pipeline_runs)
-- ============================================================
-- One row per pipeline step (preflight, adzuna, ingest, transform, fx,
-- dbt, archive, retention), written by etl/ops/run_step.py and
-- refresh_all.py. Gives failure visibility beyond "read the log file"
-- and the numbers the failure email reports.
-- Idempotent.
-- ============================================================
BEGIN;

CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT        NOT NULL,   -- 'gh-<run id>-<attempt>' or 'local-<utc timestamp>'
    step        TEXT        NOT NULL,
    status      TEXT        NOT NULL CHECK (status IN ('success', 'failure')),
    exit_code   INTEGER,
    rows_out    BIGINT,                 -- value of the step's metric (see run_step.METRICS)
    started_at  TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    error       TEXT,                   -- last lines of output when the step failed
    details     JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS pipeline_runs_run_id_idx  ON ops.pipeline_runs (run_id);
CREATE INDEX IF NOT EXISTS pipeline_runs_started_idx ON ops.pipeline_runs (started_at DESC);

-- ops is internal: keep it away from Supabase's API roles (they only
-- exist on Supabase, hence the guard).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON SCHEMA ops FROM anon, authenticated';
    END IF;
END $$;

COMMIT;
