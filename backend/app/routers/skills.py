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
    SkillByCountry, GlobalComparisonResponse
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
