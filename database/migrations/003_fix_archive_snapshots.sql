-- ============================================================
-- MIGRATION 003 — Fix skill-demand history snapshots
-- ============================================================
-- BUG: archive_skill_demand() read from marts.skill_demand — the empty
-- placeholder table created by schema.sql. dbt actually materializes the
-- mart as staging_marts.mart_skill_demand (custom-schema prefixing), which
-- is also what the API queries. Result: every scheduled archive run
-- snapshotted 0 rows and archive.skill_demand_history stayed empty.
--
-- This migration repoints the function at the real mart and takes the
-- first snapshot immediately (skipped if one already exists for today),
-- so the trend history starts accumulating from the moment you run it.
--
-- Idempotent — safe to run repeatedly.
-- ============================================================

BEGIN;

CREATE OR REPLACE FUNCTION archive_skill_demand()
RETURNS void AS $$
BEGIN
    -- Guard: dbt may not have built the mart yet (fresh environment).
    IF to_regclass('staging_marts.mart_skill_demand') IS NULL THEN
        RAISE NOTICE 'staging_marts.mart_skill_demand not found - nothing to archive';
        RETURN;
    END IF;

    -- One snapshot per day: re-runs on the same day are no-ops.
    IF EXISTS (SELECT 1 FROM archive.skill_demand_history WHERE snapshot_date = CURRENT_DATE) THEN
        RAISE NOTICE 'Snapshot for % already exists - skipping', CURRENT_DATE;
        RETURN;
    END IF;

    INSERT INTO archive.skill_demand_history (
        snapshot_date, skill_id, skill_name, search_role, country_code,
        job_count, demand_percentage, avg_salary_min, avg_salary_max
    )
    SELECT
        CURRENT_DATE,
        skill_id, skill_name, search_role, country_code,
        job_count, demand_percentage, avg_salary_min, avg_salary_max
    FROM staging_marts.mart_skill_demand;
END;
$$ LANGUAGE plpgsql;

-- Take the first real snapshot right now.
SELECT archive_skill_demand();

COMMIT;

-- ------------------------------------------------------------
-- Verify (optional):
--   SELECT snapshot_date, COUNT(*) FROM archive.skill_demand_history
--   GROUP BY 1 ORDER BY 1;   -- should show today's date with ~7-8k rows
-- ------------------------------------------------------------
