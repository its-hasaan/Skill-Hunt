{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Mart: Skills by Country
    Skill demand compared across different countries
    Answers: "Is Python more demanded in the US or UK for Data Engineers?"
*/

WITH skill_country_demand AS (
    SELECT 
        skill_id,
        skill_name,
        skill_category,
        search_role,
        country_code,
        COUNT(DISTINCT job_id) AS job_count
    FROM {{ ref('int_job_skills_enriched') }}
    GROUP BY skill_id, skill_name, skill_category, search_role, country_code
),

country_totals AS (
    SELECT 
        search_role,
        country_code,
        COUNT(DISTINCT job_id) AS total_jobs
    FROM {{ ref('int_job_skills_enriched') }}
    GROUP BY search_role, country_code
),

skill_demand_pct AS (
    SELECT 
        scd.skill_id,
        scd.skill_name,
        scd.skill_category,
        scd.search_role,
        scd.country_code,
        scd.job_count,
        ct.total_jobs,
        ROUND((scd.job_count::NUMERIC / NULLIF(ct.total_jobs, 0)) * 100, 2) AS demand_percentage,
        ROW_NUMBER() OVER (
            PARTITION BY scd.skill_name, scd.search_role 
            ORDER BY (scd.job_count::NUMERIC / NULLIF(ct.total_jobs, 0)) DESC
        ) AS rank_by_country
    FROM skill_country_demand scd
    JOIN country_totals ct 
        ON scd.search_role = ct.search_role 
        AND scd.country_code = ct.country_code
)

SELECT 
    skill_id,
    skill_name,
    skill_category,
    search_role,
    country_code,
    job_count,
    total_jobs,
    demand_percentage,
    rank_by_country,
    -- Pivot for comparison (highest demand country for this skill/role)
    FIRST_VALUE(country_code) OVER (
        PARTITION BY skill_name, search_role 
        ORDER BY demand_percentage DESC
    ) AS top_country_for_skill,
    FIRST_VALUE(demand_percentage) OVER (
        PARTITION BY skill_name, search_role 
        ORDER BY demand_percentage DESC
    ) AS top_country_demand_pct,
    CURRENT_DATE - INTERVAL '30 days' AS period_start,
    CURRENT_DATE AS period_end,
    NOW() AS updated_at
FROM skill_demand_pct
WHERE job_count >= 3  -- Minimum threshold
ORDER BY skill_name, search_role, demand_percentage DESC
