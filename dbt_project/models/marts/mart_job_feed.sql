{{
    config(
        materialized='table',
        schema='marts',
        indexes=[
            {'columns': ['job_id'], 'unique': True},
            {'columns': ['search_role']},
            {'columns': ['eligible_pk', 'eligible_in']},
            {'columns': ['first_seen_at']},
        ]
    )
}}

/*
    Mart: Job Feed (Phase 1c)
    One row per OPEN, CANONICAL job that is remote or located in Pakistan/India,
    with its eligibility labels, attributes and skills. This is what the
    copilot feed and match scores read.

    - Open = the raw listing is still live (raw.jobs.closed_at IS NULL). Unlike
      the analytics marts there is no 60-day window: company boards keep the
      original posting date on jobs that are still open.
    - Canonical = the listing chosen for its duplicate group (ops.dedup).
    - eligible_pk / eligible_in: TRUE / FALSE / NULL (= unclear).
    - Descriptions are not copied (database size); read them from
      staging.stg_jobs by job_id.
*/

WITH feed AS (
    SELECT j.*, r.first_seen_at, r.last_seen_at
    FROM {{ source('staging', 'stg_jobs') }} j
    JOIN {{ source('raw', 'jobs') }} r ON r.id = j.raw_job_id
    WHERE r.closed_at IS NULL
      AND j.canonical_job_id = j.job_id
      AND (j.workplace_type = 'remote' OR j.country_code IN ('pk', 'in'))
),

skills AS (
    SELECT js.job_id,
           array_agg(js.skill_name ORDER BY js.mention_count DESC, js.skill_name) AS skills
    FROM {{ source('staging', 'stg_job_skills') }} js
    JOIN feed f ON f.job_id = js.job_id
    GROUP BY js.job_id
)

SELECT
    f.job_id,
    f.title,
    f.company_name,
    f.search_role,
    f.source,
    COALESCE(f.workplace_type, 'onsite') AS workplace_type,
    f.country_code,
    f.location_display,
    f.redirect_url AS apply_url,
    f.job_posted_at,
    f.first_seen_at,
    f.last_seen_at,
    e.remote_scope,
    e.eligible_pk,
    e.eligible_in,
    e.eligible_countries,
    e.eligible_regions,
    e.eligibility_confidence,
    e.eligibility_evidence,
    e.method AS eligibility_method,
    e.seniority,
    e.min_years,
    e.tz_overlap,
    e.salary_min_usd,
    e.salary_max_usd,
    COALESCE(s.skills, ARRAY[]::TEXT[]) AS skills,
    NOW() AS built_at
FROM feed f
JOIN {{ source('staging', 'job_enrichment') }} e ON e.job_id = f.job_id
LEFT JOIN skills s ON s.job_id = f.job_id
