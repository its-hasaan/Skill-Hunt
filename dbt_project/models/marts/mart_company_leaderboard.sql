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
                    CASE WHEN j.salary_max IS NOT NULL THEN 1 ELSE 0 END), 0) AS salary_midpoint,
        -- USD-normalized (see int_job_skills_enriched.sql for the rationale) —
        -- required for the cross-country aggregate branch in companies.py
        j.salary_min / cr.rate_to_usd AS salary_min_usd,
        j.salary_max / cr.rate_to_usd AS salary_max_usd,
        (COALESCE(j.salary_min, 0) + COALESCE(j.salary_max, 0)) /
            NULLIF((CASE WHEN j.salary_min IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN j.salary_max IS NOT NULL THEN 1 ELSE 0 END), 0)
            / cr.rate_to_usd AS salary_midpoint_usd
    FROM {{ source('staging', 'stg_jobs') }} j
    LEFT JOIN {{ source('staging', 'currency_rates') }} cr
        ON j.salary_currency = cr.currency_code
    WHERE j.company_name IS NOT NULL
      AND j.company_name != ''
      -- Same 60-day freshness window as int_job_skills_enriched: without it
      -- this mart showed ALL-TIME hiring counts while every other mart (and
      -- the dashboard KPIs) shows the last 60 days — silently inconsistent.
      AND COALESCE(j.job_posted_at, j.extracted_at) >= CURRENT_DATE - INTERVAL '60 days'
),

company_aggregates AS (
    SELECT
        company_name,
        search_role,
        country_code,
        COUNT(DISTINCT job_id) AS job_count,

        -- Salary stats (native currency — correct for single-country views)
        AVG(salary_min) AS avg_salary_min,
        AVG(salary_max) AS avg_salary_max,
        AVG(salary_midpoint) AS avg_salary_midpoint,
        -- USD-normalized — use these when blending ACROSS countries
        AVG(salary_min_usd) AS avg_salary_min_usd,
        AVG(salary_max_usd) AS avg_salary_max_usd,
        AVG(salary_midpoint_usd) AS avg_salary_midpoint_usd,

        -- Contract type breakdown
        COUNT(DISTINCT CASE WHEN contract_time = 'full_time' THEN job_id END) AS full_time_count,
        COUNT(DISTINCT CASE WHEN contract_time = 'part_time' THEN job_id END) AS part_time_count,
        COUNT(DISTINCT CASE WHEN contract_type = 'contract' THEN job_id END) AS contract_count,
        COUNT(DISTINCT CASE WHEN contract_type = 'permanent' THEN job_id END) AS permanent_count
    FROM company_jobs
    GROUP BY company_name, search_role, country_code
),

-- All roles a company is hiring for in a country (across role groups).
-- Computed separately: inside company_aggregates the group is one
-- (company, role, country), so ARRAY_AGG(DISTINCT search_role) there was
-- always a single-element array — its own group's role, never the list the
-- column promises.
company_roles AS (
    SELECT
        company_name,
        country_code,
        ARRAY_AGG(DISTINCT search_role) AS roles_hiring
    FROM company_jobs
    GROUP BY company_name, country_code
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
    rc.avg_salary_min_usd,
    rc.avg_salary_max_usd,
    rc.avg_salary_midpoint_usd,
    rc.full_time_count,
    rc.part_time_count,
    rc.contract_count,
    rc.permanent_count,
    cr.roles_hiring,
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
LEFT JOIN company_roles cr
    ON rc.company_name = cr.company_name
    AND rc.country_code = cr.country_code
WHERE rc.rank_in_role_country <= 100  -- Top 100 companies per role/country
ORDER BY rc.search_role, rc.country_code, rc.rank_in_role_country
