"""
Pydantic schemas for API request/response models.
Designed for extensibility - easy to add new fields for future features.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
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
# Skill Trend Models
# ============================================

class SkillTrendPoint(BaseModel):
    """One skill's demand in one time period."""
    period: str                      # ISO month start, e.g. '2026-04-01'
    job_count: int                   # postings that period mentioning the skill
    demand_percentage: float         # job_count / total postings that period


class SkillTrendSeries(BaseModel):
    """One skill's demand across all periods (zero-filled)."""
    skill_name: str
    points: List[SkillTrendPoint]


class TrendPeriod(BaseModel):
    """A time bucket with its total posting volume (the % denominator)."""
    period: str
    total_jobs: int


class SkillTrendResponse(BaseModel):
    """Demand-over-time for up to 5 skills, bucketed by month posted."""
    role: Optional[str] = None
    country: Optional[str] = None
    months: int
    interval: str = "month"
    periods: List[TrendPeriod]
    series: List[SkillTrendSeries]


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
# Job Postings (drill-down) Models
# ============================================

class HighlightSkill(BaseModel):
    """A skill to highlight inside job descriptions."""
    skill_name: str
    skill_category: Optional[str] = None
    aliases: List[str] = []
    is_selected: bool = False


class JobPosting(BaseModel):
    """A single real job posting for the skill drill-down view."""
    job_id: int
    title: Optional[str] = None
    company_name: Optional[str] = None
    location_display: Optional[str] = None
    country_code: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_is_predicted: Optional[bool] = None
    contract_type: Optional[str] = None
    contract_time: Optional[str] = None
    redirect_url: Optional[str] = None
    job_posted_at: Optional[datetime] = None
    description: Optional[str] = None
    matched_skills: List[str] = []  # highlight skills detected in this job (selected first)


class SkillJobsResponse(BaseModel):
    """Response wrapper for jobs mentioning a specific skill."""
    skill: str
    role: str
    country: Optional[str] = None
    total_count: int
    limit: int
    offset: int
    highlight_skills: List[HighlightSkill]
    jobs: List[JobPosting]


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
    current_jobs: int          # posted (or seen) in the last 60 days
    current_companies: int     # distinct companies hiring in that window
    last_updated: Optional[datetime] = None


# ============================================
# Filter Options Models
# ============================================

class FilterOptions(BaseModel):
    """Available filter options for the dashboard."""
    roles: List[str]
    countries: List[CountryInfo]
    skill_categories: List[str]
    role_job_counts: Dict[str, int] = {}   # search_role -> total jobs tracked


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
# Resume Analysis Models (Active)
# ============================================

class ExtractedSkill(BaseModel):
    """Skill extracted from resume text."""
    skill_name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    mention_count: int = 1


class SkillGapAnalysis(BaseModel):
    """Skill with market demand data for gap analysis."""
    skill_name: str
    skill_category: Optional[str] = None
    job_count: int
    demand_percentage: Optional[float] = None
    avg_salary: Optional[float] = None
    market_rank: Optional[int] = None


class ResumeAnalysisResponse(BaseModel):
    """Full resume analysis response."""
    target_role: str
    country: Optional[str] = None
    total_resume_skills: int
    resume_skills: List[ExtractedSkill]
    match_percentage: float
    skills_you_have: List[SkillGapAnalysis]
    skills_you_need: List[SkillGapAnalysis]
    top_skills_to_learn: List[SkillGapAnalysis]


class MatchedSkill(BaseModel):
    """A skill that matched between resume and role."""
    skill_name: str
    category: Optional[str] = None
    job_count: int


class RoleMatchResult(BaseModel):
    """Result of matching resume against a job role."""
    role: str
    match_score: float
    matched_skills_count: int
    total_skills_evaluated: int
    top_matched_skills: List[MatchedSkill]
    top_missing_skills: List[MatchedSkill]


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
