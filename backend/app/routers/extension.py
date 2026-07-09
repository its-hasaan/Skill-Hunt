"""
Browser Extension API Router
Single endpoint that powers the Skill Hunt browser extension: it receives the
job title + description scraped from a LinkedIn/Indeed posting and returns the
skills found in it, enriched with live market data from the marts.

Design notes:
- Skill extraction reuses the taxonomy-based extractor from the resume router,
  so the extension and the dashboard always agree on the taxonomy.
- The role is inferred server-side (title match first, weighted skill overlap
  as fallback) so the extension stays a thin client.
- If the scraped country isn't tracked (no mart rows), we silently fall back
  to the global (all-countries) view and report country_tracked=False.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List, Tuple
import logging
import re

from ..database import Database, get_db
from ..models.schemas import (
    ExtensionAnalyzeRequest,
    ExtensionAnalyzeResponse,
    ExtensionSkill,
)
from .resume import skill_extractor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/extension", tags=["Browser Extension"])


async def _infer_role_from_title(db: Database, title: str) -> Optional[str]:
    """Match the job title against tracked search roles (longest match wins)."""
    rows = await db.fetch_all(
        "SELECT DISTINCT search_role FROM staging_marts.mart_skill_demand"
    )
    title_lower = title.lower()
    best = None
    for row in rows:
        role = row["search_role"]
        if role and role.lower() in title_lower:
            if best is None or len(role) > len(best):
                best = role
    return best


async def _infer_role_from_skills(db: Database, skill_names: List[str]) -> Optional[str]:
    """Fallback: the role whose demand is most concentrated in these skills."""
    if not skill_names:
        return None
    row = await db.fetch_one(
        """
        SELECT search_role, SUM(job_count) AS weight
        FROM staging_marts.mart_skill_demand
        WHERE skill_name = ANY($1::text[])
        GROUP BY search_role
        ORDER BY weight DESC
        LIMIT 1
        """,
        skill_names,
    )
    return row["search_role"] if row else None


async def _fetch_market_data(
    db: Database, role: str, country: Optional[str], skill_names: List[str]
) -> Tuple[dict, dict, Optional[float], Optional[int], bool]:
    """
    Returns (demand_by_skill, premium_by_skill, market_avg_salary, total_role_jobs,
    country_used). Falls back to the global view when the country has no data.
    """

    async def demand_rows(cc: Optional[str]):
        if cc:
            return await db.fetch_all(
                """
                SELECT skill_name, skill_category, job_count, demand_percentage,
                       rank_in_role_country AS rank_in_role,
                       avg_salary_midpoint_usd AS avg_salary_usd
                FROM staging_marts.mart_skill_demand
                WHERE search_role = $1 AND country_code = $2
                  AND skill_name = ANY($3::text[])
                """,
                role, cc, skill_names,
            )
        return await db.fetch_all(
            """
            SELECT skill_name, MAX(skill_category) AS skill_category,
                   SUM(job_count) AS job_count,
                   AVG(demand_percentage) AS demand_percentage,
                   MIN(rank_in_role_global) AS rank_in_role,
                   AVG(avg_salary_midpoint_usd) AS avg_salary_usd
            FROM staging_marts.mart_skill_demand
            WHERE search_role = $1 AND skill_name = ANY($2::text[])
            GROUP BY skill_name
            """,
            role, skill_names,
        )

    country_used = None
    rows = []
    if country:
        rows = await demand_rows(country)
        if rows:
            country_used = country
    if not rows:
        rows = await demand_rows(None)

    demand_by_skill = {r["skill_name"]: dict(r) for r in rows}

    # Salary premium per skill (currency-invariant percentage, safe to blend)
    if country_used:
        premium_rows = await db.fetch_all(
            """
            SELECT skill_name, salary_premium_percentage
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND country_code = $2
              AND skill_name = ANY($3::text[])
            """,
            role, country_used, skill_names,
        )
        market_row = await db.fetch_one(
            """
            SELECT AVG(market_avg_salary_usd) AS market_avg
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND country_code = $2
            """,
            role, country_used,
        )
        jobs_row = await db.fetch_one(
            "SELECT COUNT(*) AS count FROM staging.stg_jobs WHERE search_role = $1 AND country_code = $2",
            role, country_used,
        )
    else:
        premium_rows = await db.fetch_all(
            """
            SELECT skill_name, AVG(salary_premium_percentage) AS salary_premium_percentage
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1 AND skill_name = ANY($2::text[])
            GROUP BY skill_name
            """,
            role, skill_names,
        )
        market_row = await db.fetch_one(
            """
            SELECT AVG(market_avg_salary_usd) AS market_avg
            FROM staging_marts.mart_salary_by_skill
            WHERE search_role = $1
            """,
            role,
        )
        jobs_row = await db.fetch_one(
            "SELECT COUNT(*) AS count FROM staging.stg_jobs WHERE search_role = $1",
            role,
        )

    premium_by_skill = {
        r["skill_name"]: r["salary_premium_percentage"] for r in premium_rows
    }
    market_avg = market_row["market_avg"] if market_row else None
    total_jobs = jobs_row["count"] if jobs_row else None

    return demand_by_skill, premium_by_skill, market_avg, total_jobs, country_used


@router.post("/analyze", response_model=ExtensionAnalyzeResponse)
async def analyze_job_posting(
    payload: ExtensionAnalyzeRequest,
    db: Database = Depends(get_db),
):
    """
    Analyze a scraped job posting: extract skills from its text and enrich
    each with demand, salary, and premium data for the inferred role.
    """
    text = f"{payload.title}\n{payload.description}"
    extracted = skill_extractor.extract_skills(text)
    if not extracted:
        return ExtensionAnalyzeResponse(extracted_count=0, skills=[])

    skill_names = [s["skill_name"] for s in extracted]
    mention_by_skill = {s["skill_name"]: s for s in extracted}

    # Normalize the scraped country code (extension sends best-effort guesses)
    country = payload.country.strip().lower() if payload.country else None
    if country and not re.fullmatch(r"[a-z]{2}|remote", country):
        country = None

    # Infer the role: exact title match beats skill-overlap fallback
    role = await _infer_role_from_title(db, payload.title)
    role_source = "title" if role else None
    if not role:
        role = await _infer_role_from_skills(db, skill_names)
        role_source = "skills" if role else None

    if not role:
        # No market context available — return the raw extraction
        return ExtensionAnalyzeResponse(
            extracted_count=len(extracted),
            skills=[
                ExtensionSkill(
                    skill_name=s["skill_name"],
                    skill_category=s["category"],
                    mention_count=s["mention_count"],
                )
                for s in extracted
            ],
        )

    demand_by_skill, premium_by_skill, market_avg, total_jobs, country_used = (
        await _fetch_market_data(db, role, country, skill_names)
    )

    skills = []
    for name in skill_names:
        base = mention_by_skill[name]
        market = demand_by_skill.get(name)
        skills.append(ExtensionSkill(
            skill_name=name,
            skill_category=(market or {}).get("skill_category") or base.get("category"),
            mention_count=base["mention_count"],
            job_count=(market or {}).get("job_count"),
            demand_percentage=(market or {}).get("demand_percentage"),
            rank_in_role=(market or {}).get("rank_in_role"),
            avg_salary_usd=(market or {}).get("avg_salary_usd"),
            salary_premium_percentage=premium_by_skill.get(name),
        ))

    # Skills with market data first (by demand rank), then the rest by mentions
    skills.sort(key=lambda s: (
        s.rank_in_role is None,
        s.rank_in_role if s.rank_in_role is not None else 0,
        -s.mention_count,
    ))

    return ExtensionAnalyzeResponse(
        role=role,
        role_source=role_source,
        country=country_used,
        country_tracked=country_used is not None,
        market_avg_salary_usd=round(market_avg, 0) if market_avg is not None else None,
        total_role_jobs=total_jobs,
        extracted_count=len(extracted),
        skills=skills,
    )
