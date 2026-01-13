{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Mart: Role Similarity
    Measures skill overlap between different job roles
    Answers: "If I'm a Data Analyst, how close am I to being a Data Engineer?"
*/

WITH role_skills AS (
    -- Top skills per role (using job count threshold)
    SELECT 
        search_role,
        skill_id,
        skill_name,
        COUNT(DISTINCT job_id) AS job_count
    FROM {{ ref('int_job_skills_enriched') }}
    GROUP BY search_role, skill_id, skill_name
    HAVING COUNT(DISTINCT job_id) >= 3  -- Minimum threshold
),

role_skill_sets AS (
    -- Create array of skills per role
    SELECT 
        search_role,
        ARRAY_AGG(skill_name ORDER BY job_count DESC) AS skills,
        COUNT(DISTINCT skill_id) AS total_skills
    FROM role_skills
    GROUP BY search_role
),

role_pairs AS (
    -- Create all role pairs
    SELECT 
        a.search_role AS role_1,
        a.skills AS role_1_skills,
        a.total_skills AS role_1_total,
        b.search_role AS role_2,
        b.skills AS role_2_skills,
        b.total_skills AS role_2_total
    FROM role_skill_sets a
    CROSS JOIN role_skill_sets b
    WHERE a.search_role < b.search_role  -- Avoid duplicates
),

shared_skills AS (
    -- Calculate shared skills between roles
    SELECT 
        rs1.search_role AS role_1,
        rs2.search_role AS role_2,
        rs1.skill_name,
        rs1.job_count AS role_1_job_count,
        rs2.job_count AS role_2_job_count
    FROM role_skills rs1
    JOIN role_skills rs2 
        ON rs1.skill_name = rs2.skill_name
        AND rs1.search_role < rs2.search_role
),

similarity_metrics AS (
    SELECT 
        rp.role_1,
        rp.role_2,
        rp.role_1_total,
        rp.role_2_total,
        COUNT(DISTINCT ss.skill_name) AS shared_skills_count,
        rp.role_1_total - COUNT(DISTINCT ss.skill_name) AS role_1_unique_skills,
        rp.role_2_total - COUNT(DISTINCT ss.skill_name) AS role_2_unique_skills,
        -- Top shared skills
        ARRAY_AGG(DISTINCT ss.skill_name ORDER BY ss.skill_name) FILTER (WHERE ss.skill_name IS NOT NULL) AS top_shared_skills
    FROM role_pairs rp
    LEFT JOIN shared_skills ss 
        ON rp.role_1 = ss.role_1 
        AND rp.role_2 = ss.role_2
    GROUP BY rp.role_1, rp.role_2, rp.role_1_total, rp.role_2_total
)

SELECT 
    role_1,
    role_2,
    shared_skills_count,
    role_1_unique_skills,
    role_2_unique_skills,
    role_1_total,
    role_2_total,
    -- Jaccard Similarity: shared / (total1 + total2 - shared)
    ROUND(
        shared_skills_count::NUMERIC / 
        NULLIF((role_1_total + role_2_total - shared_skills_count), 0),
        4
    ) AS jaccard_similarity,
    -- Overlap Coefficient: shared / min(total1, total2)
    ROUND(
        shared_skills_count::NUMERIC / 
        NULLIF(LEAST(role_1_total, role_2_total), 0),
        4
    ) AS overlap_coefficient,
    -- Dice Coefficient: 2*shared / (total1 + total2)
    ROUND(
        (2 * shared_skills_count)::NUMERIC / 
        NULLIF((role_1_total + role_2_total), 0),
        4
    ) AS dice_coefficient,
    (top_shared_skills)[1:10] AS top_shared_skills,  -- Limit to top 10
    CURRENT_DATE - INTERVAL '30 days' AS period_start,
    CURRENT_DATE AS period_end,
    NOW() AS updated_at
FROM similarity_metrics
ORDER BY jaccard_similarity DESC
