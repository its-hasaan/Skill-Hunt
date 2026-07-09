{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Mart: Skill Demand
    Top skills per role and country with demand percentages
    Answers: "What are the top 10 skills for Data Engineers?"
*/

WITH job_counts AS (
    -- Total unique jobs per role and country
    SELECT 
        search_role,
        country_code,
        COUNT(DISTINCT job_id) AS total_jobs
    FROM {{ ref('int_job_skills_enriched') }}
    GROUP BY search_role, country_code
),

skill_counts AS (
    -- Count jobs per skill, role, country
    SELECT 
        skill_id,
        skill_name,
        skill_category,
        skill_subcategory,
        search_role,
        country_code,
        COUNT(DISTINCT job_id) AS job_count,
        AVG(salary_min) AS avg_salary_min,
        AVG(salary_max) AS avg_salary_max,
        AVG(salary_midpoint) AS avg_salary_midpoint,
        -- USD-normalized: safe to average ACROSS this row's country too (the
        -- API uses these, not the native fields above, when country=None)
        AVG(salary_min_usd) AS avg_salary_min_usd,
        AVG(salary_max_usd) AS avg_salary_max_usd,
        AVG(salary_midpoint_usd) AS avg_salary_midpoint_usd
    FROM {{ ref('int_job_skills_enriched') }}
    GROUP BY skill_id, skill_name, skill_category, skill_subcategory, search_role, country_code
),

ranked_skills AS (
    SELECT 
        sc.*,
        jc.total_jobs,
        ROUND((sc.job_count::NUMERIC / NULLIF(jc.total_jobs, 0)) * 100, 2) AS demand_percentage,
        ROW_NUMBER() OVER (
            PARTITION BY sc.search_role, sc.country_code 
            ORDER BY sc.job_count DESC
        ) AS rank_in_role_country,
        ROW_NUMBER() OVER (
            PARTITION BY sc.search_role 
            ORDER BY sc.job_count DESC
        ) AS rank_in_role_global
    FROM skill_counts sc
    JOIN job_counts jc 
        ON sc.search_role = jc.search_role 
        AND sc.country_code = jc.country_code
)

SELECT 
    skill_id,
    skill_name,
    skill_category,
    skill_subcategory,
    search_role,
    country_code,
    job_count,
    total_jobs AS total_jobs_for_role,
    demand_percentage,
    avg_salary_min,
    avg_salary_max,
    avg_salary_midpoint,
    avg_salary_min_usd,
    avg_salary_max_usd,
    avg_salary_midpoint_usd,
    rank_in_role_country,
    rank_in_role_global,
    CURRENT_DATE - INTERVAL '30 days' AS period_start,
    CURRENT_DATE AS period_end,
    NOW() AS updated_at
FROM ranked_skills
WHERE rank_in_role_country <= 50  -- Keep top 50 skills per role/country
ORDER BY search_role, country_code, rank_in_role_country
