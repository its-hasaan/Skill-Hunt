"""
Career API Router
Endpoints for role similarity and career transition analysis.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional, List
import logging

from ..database import Database, get_db
from ..models.schemas import RoleSimilarity, CareerTransition, CareerPathResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/career", tags=["Career"])


@router.get("/role-similarity", response_model=List[RoleSimilarity])
async def get_role_similarity(
    db: Database = Depends(get_db)
):
    """
    Get all role similarity data.
    Shows how similar different tech roles are based on shared skills.
    """
    query = """
        SELECT 
            role_1, role_2, shared_skills_count,
            role_1_unique_skills, role_2_unique_skills,
            jaccard_similarity, overlap_coefficient, dice_coefficient,
            top_shared_skills
        FROM staging_marts.mart_role_similarity
        ORDER BY jaccard_similarity DESC
    """
    rows = await db.fetch_all(query)
    
    # Parse top_shared_skills from PostgreSQL array format
    results = []
    for row in rows:
        row_dict = dict(row)
        if row_dict.get('top_shared_skills'):
            skills = row_dict['top_shared_skills']
            if isinstance(skills, str):
                # Parse PostgreSQL array string format: {skill1,skill2,...}
                skills = skills.strip('{}').split(',') if skills.strip('{}') else []
            row_dict['top_shared_skills'] = skills
        results.append(RoleSimilarity(**row_dict))
    
    return results


@router.get("/transitions/{current_role}", response_model=CareerPathResponse)
async def get_career_transitions(
    current_role: str,
    db: Database = Depends(get_db)
):
    """
    Get career transition recommendations from a specific role.
    Shows similar roles ranked by ease of transition.
    """
    query = """
        SELECT 
            role_1, role_2, shared_skills_count,
            jaccard_similarity, top_shared_skills
        FROM staging_marts.mart_role_similarity
        WHERE role_1 = $1 OR role_2 = $1
        ORDER BY jaccard_similarity DESC
    """
    rows = await db.fetch_all(query, current_role)
    
    transitions = []
    for row in rows:
        # Determine target role
        target_role = row['role_2'] if row['role_1'] == current_role else row['role_1']
        similarity = row['jaccard_similarity']
        
        # Determine difficulty
        if similarity >= 0.5:
            difficulty = "easy"
        elif similarity >= 0.3:
            difficulty = "moderate"
        else:
            difficulty = "significant"
        
        # Parse shared skills
        shared_skills = row.get('top_shared_skills')
        if isinstance(shared_skills, str):
            shared_skills = shared_skills.strip('{}').split(',') if shared_skills.strip('{}') else []
        
        transitions.append(CareerTransition(
            target_role=target_role,
            similarity=similarity,
            shared_skills=row['shared_skills_count'],
            difficulty=difficulty,
            shared_skill_list=shared_skills[:10] if shared_skills else None
        ))
    
    return CareerPathResponse(
        current_role=current_role,
        transitions=transitions
    )


@router.get("/similarity-matrix")
async def get_similarity_matrix(
    db: Database = Depends(get_db)
):
    """
    Get role similarity as a matrix format (for heatmap visualization).
    """
    query = """
        SELECT 
            role_1, role_2, jaccard_similarity
        FROM staging_marts.mart_role_similarity
    """
    rows = await db.fetch_all(query)
    
    # Build list of all roles
    roles = set()
    for row in rows:
        roles.add(row['role_1'])
        roles.add(row['role_2'])
    roles = sorted(list(roles))
    
    # Build matrix (list of lists for JSON serialization)
    matrix = {role: {r: 0.0 for r in roles} for role in roles}
    
    # Fill diagonal with 1.0
    for role in roles:
        matrix[role][role] = 1.0
    
    # Fill from data
    for row in rows:
        matrix[row['role_1']][row['role_2']] = row['jaccard_similarity']
        matrix[row['role_2']][row['role_1']] = row['jaccard_similarity']
    
    return {
        "roles": roles,
        "matrix": [[matrix[r1][r2] for r2 in roles] for r1 in roles]
    }


@router.get("/skill-gap")
async def get_skill_gap(
    from_role: str = Query(..., description="Current role"),
    to_role: str = Query(..., description="Target role"),
    db: Database = Depends(get_db)
):
    """
    Get skills needed to transition from one role to another.
    Shows shared skills and skills to learn.
    """
    # Get shared skills data
    query = """
        SELECT 
            shared_skills_count, role_1_unique_skills, role_2_unique_skills,
            jaccard_similarity, top_shared_skills
        FROM staging_marts.mart_role_similarity
        WHERE (role_1 = $1 AND role_2 = $2) OR (role_1 = $2 AND role_2 = $1)
    """
    row = await db.fetch_one(query, from_role, to_role)
    
    if not row:
        return {"error": "Role combination not found"}
    
    # Get top skills for target role
    skills_query = """
        SELECT skill_name, skill_category, job_count
        FROM staging_marts.mart_skill_demand
        WHERE search_role = $1
        GROUP BY skill_name, skill_category
        ORDER BY SUM(job_count) DESC
        LIMIT 20
    """
    target_skills = await db.fetch_all(skills_query, to_role)
    
    # Parse shared skills
    shared_skills = row.get('top_shared_skills')
    if isinstance(shared_skills, str):
        shared_skills = shared_skills.strip('{}').split(',') if shared_skills.strip('{}') else []
    shared_skills_set = set(s.strip() for s in shared_skills) if shared_skills else set()
    
    # Identify skills to learn
    skills_to_learn = [
        skill for skill in target_skills 
        if skill['skill_name'] not in shared_skills_set
    ]
    
    return {
        "from_role": from_role,
        "to_role": to_role,
        "similarity": row['jaccard_similarity'],
        "shared_skills_count": row['shared_skills_count'],
        "shared_skills": list(shared_skills_set),
        "skills_to_learn": skills_to_learn[:10],
        "difficulty": (
            "easy" if row['jaccard_similarity'] >= 0.5 
            else "moderate" if row['jaccard_similarity'] >= 0.3 
            else "significant"
        )
    }
