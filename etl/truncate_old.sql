TRUNCATE TABLE staging.stg_job_skills CASCADE;
TRUNCATE TABLE staging.stg_jobs CASCADE;

DELETE FROM staging.dim_skills WHERE skill_id > 0;
-- Step 4: Truncate marts (if they exist)
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'marts' AND (tablename LIKE 'skill_%' OR tablename LIKE 'company_%'))
    LOOP
        EXECUTE 'TRUNCATE TABLE marts.' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END $$;

-- Step 5: Reset sequences
ALTER SEQUENCE raw.jobs_id_seq RESTART WITH 1;
ALTER SEQUENCE staging.stg_jobs_job_id_seq RESTART WITH 1;
ALTER SEQUENCE staging.stg_job_skills_id_seq RESTART WITH 1;
ALTER SEQUENCE staging.dim_skills_skill_id_seq RESTART WITH 1;

-- Verify counts
SELECT 'raw.jobs' as table_name, COUNT(*) as count FROM raw.jobs
UNION ALL
SELECT 'staging.stg_jobs', COUNT(*) FROM staging.stg_jobs
UNION ALL
SELECT 'staging.stg_job_skills', COUNT(*) FROM staging.stg_job_skills
UNION ALL
SELECT 'staging.dim_skills', COUNT(*) FROM staging.dim_skills
UNION ALL
SELECT 'staging.dim_job_roles', COUNT(*) FROM staging.dim_job_roles
UNION ALL
SELECT 'staging.dim_countries', COUNT(*) FROM staging.dim_countries;