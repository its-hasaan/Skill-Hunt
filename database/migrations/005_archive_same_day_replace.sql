-- ============================================================
-- MIGRATION 005 — Archive snapshots: replace-same-day semantics
-- ============================================================
-- BUG (introduced by migration 003's once-per-day guard):
-- refresh_all.py snapshots BEFORE the refresh (step 0, to preserve history
-- if the rebuild fails) and again AFTER it (step 6, to record the fresh
-- state). With the once-per-day guard, the pre-refresh snapshot always won
-- and the post-refresh call was a silent no-op — so every archived trend
-- point actually described the marts as they were BEFORE that day's
-- refresh (i.e. the previous refresh's data, labeled with today's date).
--
-- FIX: a same-day re-run now REPLACES today's snapshot instead of skipping.
-- Sequence per refresh day:
--   pre-refresh  -> writes today's snapshot (protection if the run dies)
--   post-refresh -> replaces it with the fresh state (the value we want)
-- Distinct days are unaffected: still exactly one snapshot per day.
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

    -- Replace any snapshot already taken today so the LAST call of the day
    -- (post-refresh = the fresh marts) is what history keeps.
    DELETE FROM archive.skill_demand_history WHERE snapshot_date = CURRENT_DATE;

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

COMMIT;

-- ------------------------------------------------------------
-- Verify (optional):
--   SELECT snapshot_date, COUNT(*) FROM archive.skill_demand_history
--   GROUP BY 1 ORDER BY 1 DESC LIMIT 5;
-- ------------------------------------------------------------
