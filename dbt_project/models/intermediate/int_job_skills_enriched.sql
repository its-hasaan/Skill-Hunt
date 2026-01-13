{{
    config(
        materialized='view',
        schema='staging'
    )
}}

/*
    Intermediate model: Joins jobs with their extracted skills
    Enriches skill data with category information
*/

SELECT 
    js.job_id,
    js.skill_id,
    js.skill_name,
    ds.skill_category,
    ds.skill_subcategory,
    js.mention_count,
    
    -- Job info
    j.job_platform_id,
    j.search_role,
    j.country_code,
    j.title AS job_title,
    j.company_name,
    j.description,
    j.location_display,
    j.location_areas,
    
    -- Salary info
    j.salary_min,
    j.salary_max,
    j.salary_is_predicted,
    j.salary_currency,
    CASE 
        WHEN j.salary_min IS NOT NULL AND j.salary_max IS NOT NULL 
        THEN (j.salary_min + j.salary_max) / 2
        WHEN j.salary_min IS NOT NULL THEN j.salary_min
        WHEN j.salary_max IS NOT NULL THEN j.salary_max
        ELSE NULL
    END AS salary_midpoint,
    
    -- Contract info
    j.contract_type,
    j.contract_time,
    
    -- Timestamps
    j.job_posted_at,
    j.processed_at,
    DATE(j.job_posted_at) AS job_posted_date

FROM {{ source('staging', 'stg_job_skills') }} js
LEFT JOIN {{ source('staging', 'dim_skills') }} ds 
    ON js.skill_id = ds.skill_id
LEFT JOIN {{ source('staging', 'stg_jobs') }} j 
    ON js.job_id = j.job_id
WHERE j.job_id IS NOT NULL
