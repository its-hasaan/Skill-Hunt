"""
Pydantic schemas for API request/response models.
Designed for extensibility - easy to add new fields for future features.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# ============================================
# Base Models
# ============================================

class SkillBase(BaseModel):
    """Base skill model."""
    skill_name: str
    skill_category: Optional[str] = None


class CountryInfo(BaseModel):
    """Country information."""
    country_code: str
    country_name: str


# ============================================
# Skill Demand Models
# ============================================

class SkillDemand(BaseModel):
    """Skill demand data for a role/country."""
    skill_name: str
    skill_category: Optional[str] = None
    search_role: str
    country_code: Optional[str] = None
    job_count: int
    demand_percentage: Optional[float] = None
    avg_salary_min: Optional[float] = None
    avg_salary_max: Optional[float] = None
    avg_salary_midpoint: Optional[float] = None
    rank_in_role_country: Optional[int] = None
    rank_in_role_global: Optional[int] = None


class SkillDemandResponse(BaseModel):
    """Response wrapper for skill demand data."""
    role: str
    country: Optional[str] = None
    total_count: int
    data: List[SkillDemand]


# ============================================
# Skill Co-occurrence Models
# ============================================

class SkillCooccurrence(BaseModel):
    """Skill pair co-occurrence data."""
    skill_name_1: str
    skill_category_1: Optional[str] = None
    skill_name_2: str
    skill_category_2: Optional[str] = None
    search_role: str
    cooccurrence_count: int
    jaccard_similarity: Optional[float] = None
    prob_skill2_given_skill1: Optional[float] = None
    prob_skill1_given_skill2: Optional[float] = None


class SkillConnection(BaseModel):
    """Simplified skill connection for network graphs."""
    source: str
    target: str
    weight: int
    similarity: float


class SkillNetworkResponse(BaseModel):
    """Response for skill network data (D3.js format)."""
    nodes: List[dict]
    links: List[SkillConnection]


# ============================================
# Salary Models
# ============================================

class SalaryBySkill(BaseModel):
    """Salary data for a skill."""
    skill_name: str
    skill_category: Optional[str] = None
    search_role: str
    country_code: Optional[str] = None
    salary_currency: Optional[str] = None
    jobs_with_skill: int
    avg_salary_with_skill: Optional[float] = None
    median_salary_with_skill: Optional[float] = None
    market_avg_salary: Optional[float] = None
    salary_premium_absolute: Optional[float] = None
    salary_premium_percentage: Optional[float] = None
    rank_by_salary: Optional[int] = None


class SalaryResponse(BaseModel):
    """Response wrapper for salary data."""
    role: str
    country: Optional[str] = None
    total_count: int
    data: List[SalaryBySkill]


# ============================================
# Company Models
# ============================================

class CompanyLeaderboard(BaseModel):
    """Company hiring data."""
    company_name: str
    search_role: str
    country_code: Optional[str] = None
    job_count: int
    avg_salary_min: Optional[float] = None
    avg_salary_max: Optional[float] = None
    avg_salary_midpoint: Optional[float] = None
    full_time_count: Optional[int] = 0
    part_time_count: Optional[int] = 0
    contract_count: Optional[int] = 0
    rank_in_role_country: Optional[int] = None


class CompanyResponse(BaseModel):
    """Response wrapper for company data."""
    role: str
    country: Optional[str] = None
    total_count: int
    data: List[CompanyLeaderboard]


# ============================================
# Role Similarity Models
# ============================================

class RoleSimilarity(BaseModel):
    """Role similarity/transition data."""
    role_1: str
    role_2: str
    shared_skills_count: int
    role_1_unique_skills: Optional[int] = None
    role_2_unique_skills: Optional[int] = None
    jaccard_similarity: float
    overlap_coefficient: Optional[float] = None
    dice_coefficient: Optional[float] = None
    top_shared_skills: Optional[List[str]] = None


class CareerTransition(BaseModel):
    """Career transition recommendation."""
    target_role: str
    similarity: float
    shared_skills: int
    difficulty: str  # "easy", "moderate", "significant"
    shared_skill_list: Optional[List[str]] = None


class CareerPathResponse(BaseModel):
    """Response for career path analysis."""
    current_role: str
    transitions: List[CareerTransition]


# ============================================
# Global/Country Comparison Models
# ============================================

class SkillByCountry(BaseModel):
    """Skill demand by country."""
    skill_name: str
    skill_category: Optional[str] = None
    search_role: str
    country_code: str
    country_name: Optional[str] = None
    job_count: int
    demand_percentage: Optional[float] = None
    rank_by_country: Optional[int] = None
    top_country_for_skill: Optional[str] = None
    top_country_demand_pct: Optional[float] = None


class GlobalComparisonResponse(BaseModel):
    """Response for global skill comparison."""
    skill_name: str
    role: str
    data: List[SkillByCountry]


# ============================================
# Summary/Stats Models
# ============================================

class DashboardStats(BaseModel):
    """High-level dashboard statistics."""
    total_jobs: int
    total_skills: int
    total_countries: int
    total_roles: int
    total_companies: int
    last_updated: Optional[datetime] = None


# ============================================
# Filter Options Models
# ============================================

class FilterOptions(BaseModel):
    """Available filter options for the dashboard."""
    roles: List[str]
    countries: List[CountryInfo]
    skill_categories: List[str]


# ============================================
# Future: Resume Comparison Models
# ============================================

class ResumeSkill(BaseModel):
    """Skill extracted from a resume."""
    skill_name: str
    confidence: float
    matched_category: Optional[str] = None


class ResumeAnalysis(BaseModel):
    """Resume analysis result (future feature)."""
    extracted_skills: List[ResumeSkill]
    matching_roles: List[dict]
    skill_gaps: List[SkillBase]
    recommendations: List[str]


# ============================================
# Generic Response Models
# ============================================

class HealthCheck(BaseModel):
    """API health check response."""
    status: str
    version: str
    database: str


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
