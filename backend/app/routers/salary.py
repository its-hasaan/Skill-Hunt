"""
Salary API Router
Endpoints for salary analysis by skill.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List
import logging

from ..database import Database, get_db
from ..models.schemas import SalaryBySkill, SalaryResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/salary", tags=["Salary"])


@router.get("/by-skill", response_model=SalaryResponse)
async def get_salary_by_skill(
    role: str = Query(..., description="Job role to filter by"),
    country: Optional[str] = Query(None, description="Country code"),
    min_jobs: int = Query(5, ge=1, description="Minimum jobs with skill"),
    limit: int = Query(50, ge=1, le=100),
    db: Database = Depends(get_db)
):
    """
    Get salary data by skill for a specific role.
    Shows salary premium for each skill.
    """
    if country:
        query = """
            SELECT 
                skill_name, skill_category, search_role, country_code,
                salary_currency, jobs_with_skill,
                avg_salary_with_skill, median_salary_with_skill,
                market_avg_salary, salary_premium_absolute, salary_premium_percentage,
                rank_by_salary
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND country_code = $2 AND jobs_with_skill >= $3
            ORDER BY salary_premium_percentage DESC NULLS LAST
            LIMIT $4
        """
        rows = await db.fetch_all(query, role, country, min_jobs, limit)
    else:
        # Aggregate across countries
        query = """
            SELECT 
                skill_name, skill_category, search_role,
                SUM(jobs_with_skill) as jobs_with_skill,
                AVG(avg_salary_with_skill) as avg_salary_with_skill,
                AVG(median_salary_with_skill) as median_salary_with_skill,
                AVG(market_avg_salary) as market_avg_salary,
                AVG(salary_premium_absolute) as salary_premium_absolute,
                AVG(salary_premium_percentage) as salary_premium_percentage
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND jobs_with_skill >= $2
            GROUP BY skill_name, skill_category, search_role
            HAVING SUM(jobs_with_skill) >= $2
            ORDER BY AVG(salary_premium_percentage) DESC NULLS LAST
            LIMIT $3
        """
        rows = await db.fetch_all(query, role, min_jobs, limit)
    
    return SalaryResponse(
        role=role,
        country=country,
        total_count=len(rows),
        data=[SalaryBySkill(**row) for row in rows]
    )


@router.get("/top-paying-skills")
async def get_top_paying_skills(
    role: str = Query(..., description="Job role"),
    country: Optional[str] = Query(None, description="Country code"),
    limit: int = Query(15, ge=1, le=50),
    db: Database = Depends(get_db)
):
    """
    Get skills with highest average salaries.
    """
    if country:
        query = """
            SELECT 
                skill_name, skill_category, 
                avg_salary_with_skill, jobs_with_skill,
                salary_premium_percentage
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND country_code = $2 
              AND jobs_with_skill >= 5 AND avg_salary_with_skill IS NOT NULL
            ORDER BY avg_salary_with_skill DESC
            LIMIT $3
        """
        rows = await db.fetch_all(query, role, country, limit)
    else:
        query = """
            SELECT 
                skill_name, skill_category,
                AVG(avg_salary_with_skill) as avg_salary_with_skill,
                SUM(jobs_with_skill) as jobs_with_skill,
                AVG(salary_premium_percentage) as salary_premium_percentage
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND jobs_with_skill >= 5 AND avg_salary_with_skill IS NOT NULL
            GROUP BY skill_name, skill_category
            ORDER BY AVG(avg_salary_with_skill) DESC
            LIMIT $2
        """
        rows = await db.fetch_all(query, role, limit)
    
    return rows


@router.get("/premium-skills")
async def get_premium_skills(
    role: str = Query(..., description="Job role"),
    country: Optional[str] = Query(None, description="Country code"),
    limit: int = Query(15, ge=1, le=50),
    db: Database = Depends(get_db)
):
    """
    Get skills with highest salary premium (% above market average).
    """
    if country:
        query = """
            SELECT 
                skill_name, skill_category,
                salary_premium_percentage, salary_premium_absolute,
                avg_salary_with_skill, market_avg_salary, jobs_with_skill
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND country_code = $2 
              AND jobs_with_skill >= 5 AND salary_premium_percentage IS NOT NULL
            ORDER BY salary_premium_percentage DESC
            LIMIT $3
        """
        rows = await db.fetch_all(query, role, country, limit)
    else:
        query = """
            SELECT 
                skill_name, skill_category,
                AVG(salary_premium_percentage) as salary_premium_percentage,
                AVG(salary_premium_absolute) as salary_premium_absolute,
                AVG(avg_salary_with_skill) as avg_salary_with_skill,
                AVG(market_avg_salary) as market_avg_salary,
                SUM(jobs_with_skill) as jobs_with_skill
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND jobs_with_skill >= 5 AND salary_premium_percentage IS NOT NULL
            GROUP BY skill_name, skill_category
            ORDER BY AVG(salary_premium_percentage) DESC
            LIMIT $2
        """
        rows = await db.fetch_all(query, role, limit)
    
    return rows


@router.get("/range")
async def get_salary_range(
    role: str = Query(..., description="Job role"),
    country: Optional[str] = Query(None, description="Country code"),
    db: Database = Depends(get_db)
):
    """
    Get salary range statistics for a role.
    """
    if country:
        query = """
            SELECT 
                MIN(avg_salary_with_skill) as min_salary,
                MAX(avg_salary_with_skill) as max_salary,
                AVG(avg_salary_with_skill) as avg_salary,
                AVG(market_avg_salary) as market_avg
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND country_code = $2 
              AND jobs_with_skill >= 5 AND avg_salary_with_skill IS NOT NULL
        """
        row = await db.fetch_one(query, role, country)
    else:
        query = """
            SELECT 
                MIN(avg_salary_with_skill) as min_salary,
                MAX(avg_salary_with_skill) as max_salary,
                AVG(avg_salary_with_skill) as avg_salary,
                AVG(market_avg_salary) as market_avg
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND jobs_with_skill >= 5 AND avg_salary_with_skill IS NOT NULL
        """
        row = await db.fetch_one(query, role)
    
    return row or {"min_salary": None, "max_salary": None, "avg_salary": None, "market_avg": None}
