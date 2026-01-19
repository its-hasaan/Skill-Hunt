"""
Stats API Router
Endpoints for dashboard statistics and filter options.
"""

from fastapi import APIRouter, Depends
from typing import List
import logging

from ..database import Database, get_db
from ..models.schemas import DashboardStats, FilterOptions, CountryInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stats", tags=["Statistics"])

# Country code to name mapping
COUNTRY_NAMES = {
    'gb': 'United Kingdom', 'us': 'United States', 'au': 'Australia',
    'at': 'Austria', 'be': 'Belgium', 'br': 'Brazil',
    'ca': 'Canada', 'de': 'Germany', 'fr': 'France',
    'in': 'India', 'it': 'Italy', 'mx': 'Mexico',
    'nl': 'Netherlands', 'nz': 'New Zealand', 'pl': 'Poland',
    'sg': 'Singapore', 'za': 'South Africa'
}


@router.get("/summary", response_model=DashboardStats)
async def get_summary_stats(
    db: Database = Depends(get_db)
):
    """
    Get high-level dashboard statistics.
    """
    # Total jobs
    jobs_query = "SELECT COUNT(*) as count FROM staging.stg_jobs"
    jobs_result = await db.fetch_one(jobs_query)
    
    # Total skills tracked
    skills_query = "SELECT COUNT(DISTINCT skill_id) as count FROM staging.stg_job_skills"
    skills_result = await db.fetch_one(skills_query)
    
    # Countries
    countries_query = "SELECT COUNT(DISTINCT country_code) as count FROM staging.stg_jobs"
    countries_result = await db.fetch_one(countries_query)
    
    # Roles
    roles_query = "SELECT COUNT(DISTINCT search_role) as count FROM staging.stg_jobs"
    roles_result = await db.fetch_one(roles_query)
    
    # Companies
    companies_query = """
        SELECT COUNT(DISTINCT company_name) as count 
        FROM staging.stg_jobs 
        WHERE company_name IS NOT NULL
    """
    companies_result = await db.fetch_one(companies_query)
    
    return DashboardStats(
        total_jobs=jobs_result['count'] if jobs_result else 0,
        total_skills=skills_result['count'] if skills_result else 0,
        total_countries=countries_result['count'] if countries_result else 0,
        total_roles=roles_result['count'] if roles_result else 0,
        total_companies=companies_result['count'] if companies_result else 0
    )


@router.get("/filters", response_model=FilterOptions)
async def get_filter_options(
    db: Database = Depends(get_db)
):
    """
    Get all available filter options for the dashboard.
    Useful for populating dropdowns.
    """
    # Get roles
    roles_query = """
        SELECT DISTINCT search_role 
        FROM staging.stg_jobs 
        ORDER BY search_role
    """
    roles_result = await db.fetch_all(roles_query)
    roles = [r['search_role'] for r in roles_result]
    
    # Get countries
    countries_query = """
        SELECT DISTINCT country_code 
        FROM staging.stg_jobs 
        WHERE country_code IS NOT NULL
        ORDER BY country_code
    """
    countries_result = await db.fetch_all(countries_query)
    countries = [
        CountryInfo(
            country_code=r['country_code'],
            country_name=COUNTRY_NAMES.get(r['country_code'], r['country_code'].upper())
        )
        for r in countries_result
    ]
    
    # Get skill categories
    categories_query = """
        SELECT DISTINCT skill_category 
        FROM staging.dim_skills 
        WHERE skill_category IS NOT NULL
        ORDER BY skill_category
    """
    categories_result = await db.fetch_all(categories_query)
    categories = [r['skill_category'] for r in categories_result]
    
    return FilterOptions(
        roles=roles,
        countries=countries,
        skill_categories=categories
    )


@router.get("/roles")
async def get_available_roles(
    db: Database = Depends(get_db)
):
    """
    Get list of all available job roles.
    """
    query = """
        SELECT role_name, role_category 
        FROM staging.dim_job_roles 
        WHERE is_active = TRUE
        ORDER BY role_category, role_name
    """
    rows = await db.fetch_all(query)
    return rows


@router.get("/countries")
async def get_available_countries(
    db: Database = Depends(get_db)
):
    """
    Get list of all available countries with job data.
    """
    query = """
        SELECT DISTINCT j.country_code, c.country_name
        FROM staging.stg_jobs j
        LEFT JOIN staging.dim_countries c ON j.country_code = c.country_code
        WHERE j.country_code IS NOT NULL
        ORDER BY c.country_name
    """
    rows = await db.fetch_all(query)
    
    # Add fallback names
    return [
        {
            "country_code": r['country_code'],
            "country_name": r['country_name'] or COUNTRY_NAMES.get(r['country_code'], r['country_code'].upper())
        }
        for r in rows
    ]
