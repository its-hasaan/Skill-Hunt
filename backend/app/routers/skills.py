"""
Skills API Router
Endpoints for skill demand, co-occurrence, and network data.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
import logging

from ..database import Database, get_db
from ..models.schemas import (
    SkillDemand, SkillDemandResponse,
    SkillCooccurrence, SkillNetworkResponse, SkillConnection,
    SkillByCountry, GlobalComparisonResponse,
    SkillJobsResponse, JobPosting, HighlightSkill
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/skills", tags=["Skills"])


# ============================================
# Skill Demand Endpoints
# ============================================

@router.get("/demand", response_model=SkillDemandResponse)
async def get_skill_demand(
    role: str = Query(..., description="Job role to filter by"),
    country: Optional[str] = Query(None, description="Country code (e.g., 'gb', 'us')"),
    limit: int = Query(30, ge=1, le=100, description="Maximum results"),
    db: Database = Depends(get_db)
):
    """
    Get skill demand data for a specific role and optionally country.
    Returns top skills ranked by job count.
    """
    if country:
        query = """
            SELECT 
                skill_name, skill_category, search_role, country_code,
                job_count, demand_percentage, avg_salary_min, avg_salary_max,
                avg_salary_midpoint, rank_in_role_country, rank_in_role_global
            FROM staging_marts.mart_skill_demand
            WHERE search_role = $1 AND country_code = $2
            ORDER BY rank_in_role_country
            LIMIT $3
        """
        rows = await db.fetch_all(query, role, country, limit)
    else:
        # Aggregate across all countries for global view
        query = """
            SELECT 
                skill_name, skill_category, search_role,
                SUM(job_count) as job_count,
                AVG(demand_percentage) as demand_percentage,
                AVG(avg_salary_min) as avg_salary_min,
                AVG(avg_salary_max) as avg_salary_max,
                AVG(avg_salary_midpoint) as avg_salary_midpoint,
                MIN(rank_in_role_global) as rank_in_role_global
            FROM staging_marts.mart_skill_demand
            WHERE search_role = $1
            GROUP BY skill_name, skill_category, search_role
            ORDER BY job_count DESC
            LIMIT $2
        """
        rows = await db.fetch_all(query, role, limit)
    
    return SkillDemandResponse(
        role=role,
        country=country,
        total_count=len(rows),
        data=[SkillDemand(**row) for row in rows]
    )


@router.get("/demand/all", response_model=List[SkillDemand])
async def get_all_skill_demand(
    limit: int = Query(500, ge=1, le=1000),
    db: Database = Depends(get_db)
):
    """
    Get all skill demand data (for client-side filtering).
    """
    query = """
        SELECT 
            skill_name, skill_category, search_role, country_code,
            job_count, demand_percentage, avg_salary_min, avg_salary_max,
            avg_salary_midpoint, rank_in_role_country, rank_in_role_global
        FROM staging_marts.mart_skill_demand
        WHERE rank_in_role_country <= 30
        ORDER BY search_role, country_code, rank_in_role_country
        LIMIT $1
    """
    rows = await db.fetch_all(query, limit)
    return [SkillDemand(**row) for row in rows]


# ============================================
# Job Postings Drill-down
# ============================================

@router.get("/jobs", response_model=SkillJobsResponse)
async def get_jobs_for_skill(
    skill: str = Query(..., description="Skill that must be mentioned in the job"),
    role: str = Query(..., description="Job role to filter by"),
    country: Optional[str] = Query(None, description="Country code (e.g., 'gb', 'us')"),
    limit: int = Query(20, ge=1, le=100, description="Jobs per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    top_skills: int = Query(25, ge=1, le=100, description="How many top role skills to highlight"),
    db: Database = Depends(get_db)
):
    """
    List the real job postings where a given skill was detected, for a role
    (optionally scoped to a country). Also returns the role's top skills (with
    aliases) so the frontend can highlight every top skill in each description,
    with the selected skill highlighted distinctly.
    """
    # --- 1. Count + page of jobs mentioning this skill --------------------
    if country:
        count_query = """
            SELECT COUNT(DISTINCT j.job_id) AS count
            FROM staging.stg_jobs j
            JOIN staging.stg_job_skills js ON js.job_id = j.job_id
            WHERE js.skill_name = $1 AND j.search_role = $2 AND j.country_code = $3
        """
        total = await db.fetch_one(count_query, skill, role, country)

        jobs_query = """
            SELECT DISTINCT
                j.job_id, j.title, j.company_name, j.location_display, j.country_code,
                j.salary_min, j.salary_max, j.salary_currency, j.salary_is_predicted,
                j.contract_type, j.contract_time, j.redirect_url, j.job_posted_at,
                j.description
            FROM staging.stg_jobs j
            JOIN staging.stg_job_skills js ON js.job_id = j.job_id
            WHERE js.skill_name = $1 AND j.search_role = $2 AND j.country_code = $3
            ORDER BY j.job_posted_at DESC NULLS LAST, j.job_id DESC
            LIMIT $4 OFFSET $5
        """
        job_rows = await db.fetch_all(jobs_query, skill, role, country, limit, offset)
    else:
        count_query = """
            SELECT COUNT(DISTINCT j.job_id) AS count
            FROM staging.stg_jobs j
            JOIN staging.stg_job_skills js ON js.job_id = j.job_id
            WHERE js.skill_name = $1 AND j.search_role = $2
        """
        total = await db.fetch_one(count_query, skill, role)

        jobs_query = """
            SELECT DISTINCT
                j.job_id, j.title, j.company_name, j.location_display, j.country_code,
                j.salary_min, j.salary_max, j.salary_currency, j.salary_is_predicted,
                j.contract_type, j.contract_time, j.redirect_url, j.job_posted_at,
                j.description
            FROM staging.stg_jobs j
            JOIN staging.stg_job_skills js ON js.job_id = j.job_id
            WHERE js.skill_name = $1 AND j.search_role = $2
            ORDER BY j.job_posted_at DESC NULLS LAST, j.job_id DESC
            LIMIT $3 OFFSET $4
        """
        job_rows = await db.fetch_all(jobs_query, skill, role, limit, offset)

    total_count = total['count'] if total else 0

    # --- 2. Top skills for the role (the highlight set) -------------------
    if country:
        top_query = """
            SELECT skill_name, skill_category
            FROM staging_marts.mart_skill_demand
            WHERE search_role = $1 AND country_code = $2
            ORDER BY rank_in_role_country
            LIMIT $3
        """
        top_rows = await db.fetch_all(top_query, role, country, top_skills)
    else:
        top_query = """
            SELECT skill_name, MAX(skill_category) AS skill_category
            FROM staging_marts.mart_skill_demand
            WHERE search_role = $1
            GROUP BY skill_name
            ORDER BY SUM(job_count) DESC
            LIMIT $2
        """
        top_rows = await db.fetch_all(top_query, role, top_skills)

    # Ordered map of highlight skill_name -> category (selected skill guaranteed present)
    highlight_map = {}
    for r in top_rows:
        highlight_map[r['skill_name']] = r['skill_category']
    if skill not in highlight_map:
        highlight_map[skill] = None  # backfilled from dim_skills below

    # --- 3. Aliases + categories for the highlight skills -----------------
    names = list(highlight_map.keys())
    alias_rows = await db.fetch_all(
        """
        SELECT skill_name, skill_category, aliases
        FROM staging.dim_skills
        WHERE skill_name = ANY($1::text[])
        """,
        names
    )
    alias_map = {r['skill_name']: (r['aliases'] or []) for r in alias_rows}
    for r in alias_rows:
        if highlight_map.get(r['skill_name']) is None and r['skill_category']:
            highlight_map[r['skill_name']] = r['skill_category']

    highlight_skills = [
        HighlightSkill(
            skill_name=name,
            skill_category=highlight_map.get(name),
            aliases=alias_map.get(name, []),
            is_selected=(name == skill),
        )
        for name in names
    ]
    highlight_names = set(names)

    # --- 4. Which highlight skills were detected in each returned job -----
    job_ids = [row['job_id'] for row in job_rows]
    detected_by_job = {}
    if job_ids:
        detected_rows = await db.fetch_all(
            """
            SELECT job_id, skill_name
            FROM staging.stg_job_skills
            WHERE job_id = ANY($1::int[])
            """,
            job_ids
        )
        for r in detected_rows:
            if r['skill_name'] in highlight_names:
                detected_by_job.setdefault(r['job_id'], []).append(r['skill_name'])

    def order_matched(matched):
        # Selected skill first, then the rest alphabetically
        rest = sorted(s for s in matched if s != skill)
        return ([skill] if skill in matched else []) + rest

    jobs = []
    for row in job_rows:
        data = dict(row)
        data['matched_skills'] = order_matched(detected_by_job.get(row['job_id'], []))
        jobs.append(JobPosting(**data))

    return SkillJobsResponse(
        skill=skill,
        role=role,
        country=country,
        total_count=total_count,
        limit=limit,
        offset=offset,
        highlight_skills=highlight_skills,
        jobs=jobs,
    )


# ============================================
# Skill Co-occurrence Endpoints
# ============================================

@router.get("/cooccurrence", response_model=List[SkillCooccurrence])
async def get_skill_cooccurrence(
    role: str = Query(..., description="Job role to filter by"),
    skill: Optional[str] = Query(None, description="Filter connections for a specific skill"),
    min_count: int = Query(5, ge=1, description="Minimum co-occurrence count"),
    limit: int = Query(100, ge=1, le=500),
    db: Database = Depends(get_db)
):
    """
    Get skill co-occurrence data showing which skills appear together.
    """
    if skill:
        query = """
            SELECT 
                skill_name_1, skill_category_1, skill_name_2, skill_category_2,
                search_role, cooccurrence_count, jaccard_similarity,
                prob_skill2_given_skill1, prob_skill1_given_skill2
            FROM staging_marts.mart_skill_cooccurrence
            WHERE search_role = $1 
              AND (skill_name_1 = $2 OR skill_name_2 = $2)
              AND cooccurrence_count >= $3
            ORDER BY cooccurrence_count DESC
            LIMIT $4
        """
        rows = await db.fetch_all(query, role, skill, min_count, limit)
    else:
        query = """
            SELECT 
                skill_name_1, skill_category_1, skill_name_2, skill_category_2,
                search_role, cooccurrence_count, jaccard_similarity,
                prob_skill2_given_skill1, prob_skill1_given_skill2
            FROM staging_marts.mart_skill_cooccurrence
            WHERE search_role = $1 AND cooccurrence_count >= $2
            ORDER BY cooccurrence_count DESC
            LIMIT $3
        """
        rows = await db.fetch_all(query, role, min_count, limit)
    
    return [SkillCooccurrence(**row) for row in rows]


@router.get("/network", response_model=SkillNetworkResponse)
async def get_skill_network(
    role: str = Query(..., description="Job role to filter by"),
    min_count: int = Query(10, ge=1, description="Minimum co-occurrence for links"),
    limit: int = Query(50, ge=10, le=200, description="Max number of links"),
    db: Database = Depends(get_db)
):
    """
    Get skill network data formatted for D3.js force-directed graph.
    Returns nodes (skills) and links (co-occurrences).
    """
    query = """
        SELECT 
            skill_name_1, skill_category_1, skill_name_2, skill_category_2,
            cooccurrence_count, jaccard_similarity
        FROM staging_marts.mart_skill_cooccurrence
        WHERE search_role = $1 AND cooccurrence_count >= $2
        ORDER BY cooccurrence_count DESC
        LIMIT $3
    """
    rows = await db.fetch_all(query, role, min_count, limit)
    
    # Build nodes and links for D3
    nodes_dict = {}  # skill_name -> {id, category, count}
    links = []
    
    for row in rows:
        # Add skill 1 to nodes
        if row['skill_name_1'] not in nodes_dict:
            nodes_dict[row['skill_name_1']] = {
                'id': row['skill_name_1'],
                'category': row['skill_category_1'] or 'Other',
                'count': 0
            }
        nodes_dict[row['skill_name_1']]['count'] += row['cooccurrence_count']
        
        # Add skill 2 to nodes
        if row['skill_name_2'] not in nodes_dict:
            nodes_dict[row['skill_name_2']] = {
                'id': row['skill_name_2'],
                'category': row['skill_category_2'] or 'Other',
                'count': 0
            }
        nodes_dict[row['skill_name_2']]['count'] += row['cooccurrence_count']
        
        # Add link
        links.append(SkillConnection(
            source=row['skill_name_1'],
            target=row['skill_name_2'],
            weight=row['cooccurrence_count'],
            similarity=row['jaccard_similarity'] or 0
        ))
    
    return SkillNetworkResponse(
        nodes=list(nodes_dict.values()),
        links=links
    )


# ============================================
# Global Comparison Endpoints
# ============================================

@router.get("/by-country", response_model=GlobalComparisonResponse)
async def get_skill_by_country(
    skill: str = Query(..., description="Skill name to compare"),
    role: str = Query(..., description="Job role"),
    db: Database = Depends(get_db)
):
    """
    Get demand for a specific skill across all countries.
    Useful for geographic analysis.
    """
    query = """
        SELECT 
            skill_name, skill_category, search_role, country_code,
            job_count, demand_percentage, rank_by_country,
            top_country_for_skill, top_country_demand_pct
        FROM staging_marts.mart_skills_by_country
        WHERE skill_name = $1 AND search_role = $2 AND job_count >= 3
        ORDER BY demand_percentage DESC
    """
    rows = await db.fetch_all(query, skill, role)
    
    # Add country names
    country_names = {
        'gb': 'United Kingdom', 'us': 'United States', 'au': 'Australia',
        'at': 'Austria', 'be': 'Belgium', 'br': 'Brazil',
        'ca': 'Canada', 'de': 'Germany', 'fr': 'France',
        'in': 'India', 'it': 'Italy', 'mx': 'Mexico',
        'nl': 'Netherlands', 'nz': 'New Zealand', 'pl': 'Poland',
        'sg': 'Singapore', 'za': 'South Africa'
    }
    
    data = []
    for row in rows:
        row_data = dict(row)
        row_data['country_name'] = country_names.get(row['country_code'], row['country_code'])
        data.append(SkillByCountry(**row_data))
    
    return GlobalComparisonResponse(
        skill_name=skill,
        role=role,
        data=data
    )


@router.get("/categories")
async def get_skill_categories(db: Database = Depends(get_db)):
    """
    Get list of all skill categories.
    """
    query = """
        SELECT DISTINCT skill_category 
        FROM staging.dim_skills 
        WHERE skill_category IS NOT NULL
        ORDER BY skill_category
    """
    rows = await db.fetch_all(query)
    return [row['skill_category'] for row in rows]


@router.get("/list")
async def get_skills_list(
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Database = Depends(get_db)
):
    """
    Get list of all skills, optionally filtered by category.
    """
    if category:
        query = """
            SELECT skill_name, skill_category, skill_subcategory
            FROM staging.dim_skills
            WHERE skill_category = $1
            ORDER BY skill_name
        """
        rows = await db.fetch_all(query, category)
    else:
        query = """
            SELECT skill_name, skill_category, skill_subcategory
            FROM staging.dim_skills
            ORDER BY skill_name
        """
        rows = await db.fetch_all(query)
    
    return rows
