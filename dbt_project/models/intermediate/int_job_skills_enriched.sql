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
    
    -- Salary info (native currency — correct as-is for single-country views,
    -- since one country = one currency in this dataset)
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

    -- USD-normalized salary — required whenever figures are blended ACROSS
    -- countries (different currencies aren't comparable as raw numbers).
    -- cr.rate_to_usd is "units of currency per 1 USD" (live, refreshed by
    -- etl/fetch_currency_rates.py), so usd_amount = native_amount / rate.
    -- NULL when the currency has no rate yet (e.g. a brand-new currency
    -- before the next fetch) rather than a guessed conversion.
    j.salary_min / cr.rate_to_usd AS salary_min_usd,
    j.salary_max / cr.rate_to_usd AS salary_max_usd,
    CASE
        WHEN j.salary_min IS NOT NULL AND j.salary_max IS NOT NULL
        THEN ((j.salary_min + j.salary_max) / 2) / cr.rate_to_usd
        WHEN j.salary_min IS NOT NULL THEN j.salary_min / cr.rate_to_usd
        WHEN j.salary_max IS NOT NULL THEN j.salary_max / cr.rate_to_usd
        ELSE NULL
    END AS salary_midpoint_usd,

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
LEFT JOIN {{ source('staging', 'currency_rates') }} cr
    ON j.salary_currency = cr.currency_code
WHERE j.job_id IS NOT NULL
  -- Filter to only include jobs from the last 2 months (60 days).
  -- COALESCE to extracted_at so a job whose source omitted a posting date is
  -- counted from when we ingested it rather than silently dropped (the
  -- /stats endpoints already use this same COALESCE convention).
  AND COALESCE(j.job_posted_at, j.extracted_at) >= CURRENT_DATE - INTERVAL '60 days'
