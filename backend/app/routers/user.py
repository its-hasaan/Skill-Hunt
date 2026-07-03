"""
User API Router
Personalized features for authenticated users: profile & preferences,
saved searches, and resume-analysis history.

All endpoints require a valid Supabase session token
(`Authorization: Bearer <access_token>`).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import AuthUser, get_current_user
from ..database import Database, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["User"])

MAX_SAVED_SEARCHES = 30


# ============================================
# Schemas
# ============================================

class UserProfile(BaseModel):
    id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    default_role: Optional[str] = None
    default_country: Optional[str] = None


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    default_role: Optional[str] = Field(None, max_length=100)
    default_country: Optional[str] = Field(None, max_length=10)


class SavedSearchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=100)
    country: Optional[str] = Field(None, max_length=10)


class SavedSearch(SavedSearchCreate):
    id: int
    created_at: Optional[str] = None


class ResumeHistoryItem(BaseModel):
    id: str
    filename: str
    analysis_type: Optional[str] = None
    target_role: Optional[str] = None
    country: Optional[str] = None
    match_score: Optional[float] = None
    extracted_skills_count: Optional[int] = None
    uploaded_at: Optional[str] = None


# ============================================
# Profile
# ============================================

async def _ensure_profile(db: Database, user: AuthUser) -> dict:
    """Fetch the profile, creating it on the fly for users who signed up
    before the signup trigger existed."""
    row = await db.fetch_one(
        "SELECT id, email, display_name, avatar_url, default_role, default_country "
        "FROM public.user_profiles WHERE id = $1",
        user.id,
    )
    if row:
        return dict(row)
    await db.execute(
        """
        INSERT INTO public.user_profiles (id, email, display_name)
        VALUES ($1, $2, split_part($2, '@', 1))
        ON CONFLICT (id) DO NOTHING
        """,
        user.id, user.email,
    )
    row = await db.fetch_one(
        "SELECT id, email, display_name, avatar_url, default_role, default_country "
        "FROM public.user_profiles WHERE id = $1",
        user.id,
    )
    return dict(row) if row else {"id": user.id, "email": user.email}


@router.get("/me", response_model=UserProfile)
async def get_me(
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Current user's profile and dashboard preferences."""
    profile = await _ensure_profile(db, user)
    profile["id"] = str(profile["id"])
    return UserProfile(**profile)


@router.put("/me", response_model=UserProfile)
async def update_me(
    update: ProfileUpdate,
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Update display name and/or default dashboard filters."""
    await _ensure_profile(db, user)
    await db.execute(
        """
        UPDATE public.user_profiles SET
            display_name    = COALESCE($2, display_name),
            default_role    = COALESCE($3, default_role),
            default_country = COALESCE($4, default_country),
            updated_at      = NOW()
        WHERE id = $1
        """,
        user.id, update.display_name, update.default_role, update.default_country,
    )
    profile = await _ensure_profile(db, user)
    profile["id"] = str(profile["id"])
    return UserProfile(**profile)


# ============================================
# Saved searches
# ============================================

@router.get("/saved-searches", response_model=List[SavedSearch])
async def list_saved_searches(
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    rows = await db.fetch_all(
        """
        SELECT id, name, role, country, created_at::text AS created_at
        FROM public.saved_searches
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user.id,
    )
    return [SavedSearch(**dict(r)) for r in rows]


@router.post("/saved-searches", response_model=SavedSearch, status_code=201)
async def create_saved_search(
    search: SavedSearchCreate,
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    count = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM public.saved_searches WHERE user_id = $1", user.id
    )
    if count and count["n"] >= MAX_SAVED_SEARCHES:
        raise HTTPException(status_code=400, detail=f"Limit of {MAX_SAVED_SEARCHES} saved searches reached")

    row = await db.fetch_one(
        """
        INSERT INTO public.saved_searches (user_id, name, role, country)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, role, country) DO UPDATE SET name = EXCLUDED.name
        RETURNING id, name, role, country, created_at::text AS created_at
        """,
        user.id, search.name, search.role, search.country,
    )
    return SavedSearch(**dict(row))


@router.delete("/saved-searches/{search_id}", status_code=204)
async def delete_saved_search(
    search_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    result = await db.execute(
        "DELETE FROM public.saved_searches WHERE id = $1 AND user_id = $2",
        search_id, user.id,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Saved search not found")


# ============================================
# Resume history
# ============================================

@router.get("/resume-history", response_model=List[ResumeHistoryItem])
async def resume_history(
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """The user's past resume analyses (gap analyses and role matches)."""
    rows = await db.fetch_all(
        """
        SELECT id::text AS id, filename, analysis_type, target_role, country,
               match_score, extracted_skills_count, uploaded_at::text AS uploaded_at
        FROM public.resume_uploads
        WHERE user_id = $1
        ORDER BY uploaded_at DESC
        LIMIT 50
        """,
        user.id,
    )
    return [ResumeHistoryItem(**dict(r)) for r in rows]


@router.delete("/resume-history/{resume_id}", status_code=204)
async def delete_resume_analysis(
    resume_id: str,
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Delete one of the user's resume analyses (detail rows cascade)."""
    result = await db.execute(
        "DELETE FROM public.resume_uploads WHERE id = $1::uuid AND user_id = $2",
        resume_id, user.id,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Analysis not found")
