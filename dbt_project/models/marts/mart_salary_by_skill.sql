{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Mart: Salary by Skill
    Compares average salary for jobs requiring specific skills vs market average
    Answers: "Do jobs requiring Python pay more than average?"
*/

WITH jobs_with_salary AS (
    -- Jobs that have salary data
    SELECT DISTINCT
        job_id,
        search_role,
        country_code,
        salary_min,
        salary_max,
        salary_midpoint,
        salary_currency
    FROM {{ ref('int_job_skills_enriched') }}
    WHERE salary_midpoint IS NOT NULL
      AND salary_midpoint > 0
),

market_averages AS (
    -- Market average salary per role and country
    SELECT 
        search_role,
        country_code,
        COUNT(DISTINCT job_id) AS total_jobs_with_salary,
        AVG(salary_midpoint) AS market_avg_salary,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary_midpoint) AS market_median_salary,
        MIN(salary_midpoint) AS market_min_salary,
        MAX(salary_midpoint) AS market_max_salary
    FROM jobs_with_salary
    GROUP BY search_role, country_code
),

skill_salaries AS (
    -- Salary stats for jobs with each skill
    SELECT 
        jse.skill_id,
        jse.skill_name,
        jse.skill_category,
        jse.search_role,
        jse.country_code,
        jws.salary_currency,
        COUNT(DISTINCT jse.job_id) AS jobs_with_skill,
        AVG(jws.salary_midpoint) AS avg_salary_with_skill,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY jws.salary_midpoint) AS median_salary_with_skill,
        MIN(jws.salary_midpoint) AS min_salary_with_skill,
        MAX(jws.salary_midpoint) AS max_salary_with_skill
    FROM {{ ref('int_job_skills_enriched') }} jse
    JOIN jobs_with_salary jws 
        ON jse.job_id = jws.job_id
    GROUP BY 
        jse.skill_id, jse.skill_name, jse.skill_category,
        jse.search_role, jse.country_code, jws.salary_currency
    HAVING COUNT(DISTINCT jse.job_id) >= 5  -- Minimum sample size
)

SELECT 
    ss.skill_id,
    ss.skill_name,
    ss.skill_category,
    ss.search_role,
    ss.country_code,
    ss.salary_currency,
    
    -- Skill salary stats
    ss.jobs_with_skill,
    ROUND(ss.avg_salary_with_skill::numeric, 2) AS avg_salary_with_skill,
    ROUND(ss.median_salary_with_skill::numeric, 2) AS median_salary_with_skill,
    ROUND(ss.min_salary_with_skill::numeric, 2) AS min_salary_with_skill,
    ROUND(ss.max_salary_with_skill::numeric, 2) AS max_salary_with_skill,
    
    -- Market comparison
    ma.total_jobs_with_salary,
    ROUND(ma.market_avg_salary::numeric, 2) AS market_avg_salary,
    ROUND(ma.market_median_salary::numeric, 2) AS market_median_salary,
    
    -- Premium calculation
    ROUND((ss.avg_salary_with_skill - ma.market_avg_salary)::numeric, 2) AS salary_premium_absolute,
    ROUND(
        (((ss.avg_salary_with_skill - ma.market_avg_salary) / NULLIF(ma.market_avg_salary, 0)) * 100)::numeric,
        2
    ) AS salary_premium_percentage,
    
    -- Rank by premium
    ROW_NUMBER() OVER (
        PARTITION BY ss.search_role, ss.country_code 
        ORDER BY ss.avg_salary_with_skill DESC
    ) AS rank_by_salary,
    
    CURRENT_DATE - INTERVAL '30 days' AS period_start,
    CURRENT_DATE AS period_end,
    NOW() AS updated_at
FROM skill_salaries ss
JOIN market_averages ma 
    ON ss.search_role = ma.search_role 
    AND ss.country_code = ma.country_code
ORDER BY ss.search_role, ss.country_code, salary_premium_percentage DESC NULLS LAST
