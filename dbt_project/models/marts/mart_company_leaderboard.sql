{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Mart: Company Leaderboard
    Top hiring companies by job count, role, country, and contract type
    Answers: "Which companies are hiring the most Data Engineers in the UK?"
*/

WITH company_jobs AS (
    SELECT 
        j.company_name,
        j.search_role,
        j.country_code,
        j.job_id,
        j.contract_type,
        j.contract_time,
        j.salary_min,
        j.salary_max,
        (COALESCE(j.salary_min, 0) + COALESCE(j.salary_max, 0)) / 
            NULLIF((CASE WHEN j.salary_min IS NOT NULL THEN 1 ELSE 0 END + 
                    CASE WHEN j.salary_max IS NOT NULL THEN 1 ELSE 0 END), 0) AS salary_midpoint
    FROM {{ source('staging', 'stg_jobs') }} j
    WHERE j.company_name IS NOT NULL 
      AND j.company_name != ''
),

company_aggregates AS (
    SELECT 
        company_name,
        search_role,
        country_code,
        COUNT(DISTINCT job_id) AS job_count,
        
        -- Salary stats
        AVG(salary_min) AS avg_salary_min,
        AVG(salary_max) AS avg_salary_max,
        AVG(salary_midpoint) AS avg_salary_midpoint,
        
        -- Contract type breakdown
        COUNT(DISTINCT CASE WHEN contract_time = 'full_time' THEN job_id END) AS full_time_count,
        COUNT(DISTINCT CASE WHEN contract_time = 'part_time' THEN job_id END) AS part_time_count,
        COUNT(DISTINCT CASE WHEN contract_type = 'contract' THEN job_id END) AS contract_count,
        COUNT(DISTINCT CASE WHEN contract_type = 'permanent' THEN job_id END) AS permanent_count,
        
        -- Roles this company is hiring for
        ARRAY_AGG(DISTINCT search_role) AS roles_hiring
    FROM company_jobs
    GROUP BY company_name, search_role, country_code
),

-- Rank by role and country
ranked_by_role_country AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY search_role, country_code 
            ORDER BY job_count DESC
        ) AS rank_in_role_country
    FROM company_aggregates
),

-- Rank by country only (all roles)
ranked_by_country AS (
    SELECT 
        company_name,
        country_code,
        SUM(job_count) AS total_jobs_in_country,
        ROW_NUMBER() OVER (
            PARTITION BY country_code 
            ORDER BY SUM(job_count) DESC
        ) AS rank_in_country
    FROM company_aggregates
    GROUP BY company_name, country_code
)

SELECT 
    rc.company_name,
    rc.search_role,
    rc.country_code,
    rc.job_count,
    rc.avg_salary_min,
    rc.avg_salary_max,
    rc.avg_salary_midpoint,
    rc.full_time_count,
    rc.part_time_count,
    rc.contract_count,
    rc.permanent_count,
    rc.roles_hiring,
    rc.rank_in_role_country,
    rbc.rank_in_country,
    rbc.total_jobs_in_country AS company_total_jobs_in_country,
    CURRENT_DATE - INTERVAL '30 days' AS period_start,
    CURRENT_DATE AS period_end,
    NOW() AS updated_at
FROM ranked_by_role_country rc
LEFT JOIN ranked_by_country rbc 
    ON rc.company_name = rbc.company_name 
    AND rc.country_code = rbc.country_code
WHERE rc.rank_in_role_country <= 100  -- Top 100 companies per role/country
ORDER BY rc.search_role, rc.country_code, rc.rank_in_role_country
