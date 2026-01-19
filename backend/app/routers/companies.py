"""
Companies API Router
Endpoints for company hiring data and leaderboards.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List
import logging

from ..database import Database, get_db
from ..models.schemas import CompanyLeaderboard, CompanyResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/leaderboard", response_model=CompanyResponse)
async def get_company_leaderboard(
    role: str = Query(..., description="Job role to filter by"),
    country: Optional[str] = Query(None, description="Country code"),
    limit: int = Query(50, ge=1, le=100),
    db: Database = Depends(get_db)
):
    """
    Get top hiring companies for a specific role.
    """
    if country:
        query = """
            SELECT 
                company_name, search_role, country_code, job_count,
                avg_salary_min, avg_salary_max, avg_salary_midpoint,
                full_time_count, part_time_count, contract_count,
                rank_in_role_country
            FROM staging_marts.mart_company_leaderboard
            WHERE search_role = $1 AND country_code = $2
            ORDER BY rank_in_role_country
            LIMIT $3
        """
        rows = await db.fetch_all(query, role, country, limit)
    else:
        # Aggregate across countries
        query = """
            SELECT 
                company_name, search_role,
                SUM(job_count) as job_count,
                AVG(avg_salary_min) as avg_salary_min,
                AVG(avg_salary_max) as avg_salary_max,
                AVG(avg_salary_midpoint) as avg_salary_midpoint,
                SUM(full_time_count) as full_time_count,
                SUM(part_time_count) as part_time_count,
                SUM(contract_count) as contract_count
            FROM staging_marts.mart_company_leaderboard
            WHERE search_role = $1
            GROUP BY company_name, search_role
            ORDER BY job_count DESC
            LIMIT $2
        """
        rows = await db.fetch_all(query, role, limit)
    
    return CompanyResponse(
        role=role,
        country=country,
        total_count=len(rows),
        data=[CompanyLeaderboard(**row) for row in rows]
    )


@router.get("/contract-types")
async def get_contract_type_distribution(
    role: str = Query(..., description="Job role"),
    country: Optional[str] = Query(None, description="Country code"),
    db: Database = Depends(get_db)
):
    """
    Get distribution of contract types (full-time, part-time, contract).
    """
    if country:
        query = """
            SELECT 
                SUM(full_time_count) as full_time,
                SUM(part_time_count) as part_time,
                SUM(contract_count) as contract
            FROM staging_marts.mart_company_leaderboard
            WHERE search_role = $1 AND country_code = $2
        """
        row = await db.fetch_one(query, role, country)
    else:
        query = """
            SELECT 
                SUM(full_time_count) as full_time,
                SUM(part_time_count) as part_time,
                SUM(contract_count) as contract
            FROM staging_marts.mart_company_leaderboard
            WHERE search_role = $1
        """
        row = await db.fetch_one(query, role)
    
    if row:
        return {
            "full_time": row['full_time'] or 0,
            "part_time": row['part_time'] or 0,
            "contract": row['contract'] or 0
        }
    return {"full_time": 0, "part_time": 0, "contract": 0}


@router.get("/search")
async def search_companies(
    query: str = Query(..., min_length=2, description="Company name search"),
    role: Optional[str] = Query(None, description="Filter by role"),
    limit: int = Query(20, ge=1, le=50),
    db: Database = Depends(get_db)
):
    """
    Search companies by name (partial match).
    """
    search_pattern = f"%{query}%"
    
    if role:
        sql = """
            SELECT DISTINCT company_name, search_role, country_code, job_count
            FROM staging_marts.mart_company_leaderboard
            WHERE company_name ILIKE $1 AND search_role = $2
            ORDER BY job_count DESC
            LIMIT $3
        """
        rows = await db.fetch_all(sql, search_pattern, role, limit)
    else:
        sql = """
            SELECT company_name, search_role, country_code, SUM(job_count) as job_count
            FROM staging_marts.mart_company_leaderboard
            WHERE company_name ILIKE $1
            GROUP BY company_name, search_role, country_code
            ORDER BY job_count DESC
            LIMIT $2
        """
        rows = await db.fetch_all(sql, search_pattern, limit)
    
    return rows
