{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Mart: Skill Co-occurrence
    Skills that frequently appear together in job postings
    Answers: "If a job requires Python, what other skills does it typically require?"
*/

WITH job_skill_pairs AS (
    -- Create pairs of skills that appear in the same job
    SELECT DISTINCT
        a.job_id,
        a.skill_id AS skill_id_1,
        a.skill_name AS skill_name_1,
        a.skill_category AS skill_category_1,
        b.skill_id AS skill_id_2,
        b.skill_name AS skill_name_2,
        b.skill_category AS skill_category_2,
        a.search_role
    FROM {{ ref('int_job_skills_enriched') }} a
    JOIN {{ ref('int_job_skills_enriched') }} b
        ON a.job_id = b.job_id
        AND a.skill_id < b.skill_id  -- Avoid duplicates and self-pairs
),

skill_totals AS (
    -- Total jobs per skill (for Jaccard calculation)
    SELECT 
        skill_id,
        skill_name,
        search_role,
        COUNT(DISTINCT job_id) AS total_jobs
    FROM {{ ref('int_job_skills_enriched') }}
    GROUP BY skill_id, skill_name, search_role
),

cooccurrence_counts AS (
    SELECT 
        skill_id_1,
        skill_name_1,
        skill_category_1,
        skill_id_2,
        skill_name_2,
        skill_category_2,
        search_role,
        COUNT(DISTINCT job_id) AS cooccurrence_count
    FROM job_skill_pairs
    GROUP BY 
        skill_id_1, skill_name_1, skill_category_1,
        skill_id_2, skill_name_2, skill_category_2,
        search_role
    HAVING COUNT(DISTINCT job_id) >= 5  -- Minimum threshold
)

SELECT 
    cc.skill_id_1,
    cc.skill_name_1,
    cc.skill_category_1,
    cc.skill_id_2,
    cc.skill_name_2,
    cc.skill_category_2,
    cc.search_role,
    cc.cooccurrence_count,
    st1.total_jobs AS skill_1_total,
    st2.total_jobs AS skill_2_total,
    -- Jaccard Similarity: intersection / union
    ROUND(
        cc.cooccurrence_count::NUMERIC / 
        NULLIF((st1.total_jobs + st2.total_jobs - cc.cooccurrence_count), 0),
        4
    ) AS jaccard_similarity,
    -- Conditional probability: P(skill_2 | skill_1)
    ROUND(
        cc.cooccurrence_count::NUMERIC / NULLIF(st1.total_jobs, 0),
        4
    ) AS prob_skill2_given_skill1,
    -- Conditional probability: P(skill_1 | skill_2)
    ROUND(
        cc.cooccurrence_count::NUMERIC / NULLIF(st2.total_jobs, 0),
        4
    ) AS prob_skill1_given_skill2,
    CURRENT_DATE - INTERVAL '30 days' AS period_start,
    CURRENT_DATE AS period_end,
    NOW() AS updated_at
FROM cooccurrence_counts cc
JOIN skill_totals st1 
    ON cc.skill_id_1 = st1.skill_id 
    AND cc.search_role = st1.search_role
JOIN skill_totals st2 
    ON cc.skill_id_2 = st2.skill_id 
    AND cc.search_role = st2.search_role
ORDER BY cc.search_role, cc.cooccurrence_count DESC
