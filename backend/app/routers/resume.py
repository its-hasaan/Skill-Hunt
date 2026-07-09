"""
Resume Analysis API Router
Endpoints for resume parsing, skill extraction, and career matching.

Features:
1. Upload resume (PDF, DOCX, TXT, images)
2. Extract skills from resume
3. Compare skills vs market demand for a target role (Gap Analysis)
4. Match resume skills against all roles to find best fit
"""

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form, BackgroundTasks
from typing import Optional, List, Dict, Any
import logging
import re
import json
from pathlib import Path
import io

from ..database import Database, get_db
from ..auth import AuthUser, get_optional_user
from ..models.schemas import (
    ResumeAnalysisResponse,
    SkillGapAnalysis,
    RoleMatchResult,
    ExtractedSkill
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resume", tags=["Resume Analysis"])

# Load skills taxonomy for extraction
TAXONOMY_PATH = Path(__file__).parent.parent.parent.parent / "etl" / "config" / "skills_taxonomy.json"


class ResumeSkillExtractor:
    """
    Extract skills from resume text using taxonomy-based regex matching.
    Same approach as the ETL transformer but optimized for single document.
    """
    
    def __init__(self):
        self.skills = {}  # skill_name -> {category, subcategory}
        self.patterns = []  # List of (pattern, canonical_name, category, subcategory)
        self._load_taxonomy()
    
    def _load_taxonomy(self):
        """Load skills taxonomy from JSON file."""
        try:
            with open(TAXONOMY_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for skill in data.get('skills', []):
                name = skill['name']
                category = skill.get('category', 'Unknown')
                subcategory = skill.get('subcategory', '')
                aliases = skill.get('aliases', [])
                
                # Store skill info
                self.skills[name.lower()] = {
                    'name': name,
                    'category': category,
                    'subcategory': subcategory
                }
                
                # Create regex patterns for skill and all aliases
                all_terms = [name] + aliases
                for term in all_terms:
                    escaped_term = re.escape(term)
                    # Handle special cases like C++, C#, .NET
                    if term in ['C++', 'C#', '.NET']:
                        pattern = re.compile(rf'(?<![a-zA-Z]){escaped_term}(?![a-zA-Z])', re.IGNORECASE)
                    else:
                        pattern = re.compile(rf'\b{escaped_term}\b', re.IGNORECASE)
                    self.patterns.append((pattern, name, category, subcategory))
            
            logger.info(f"Loaded {len(self.skills)} skills with {len(self.patterns)} patterns")
        except FileNotFoundError:
            logger.error(f"Skills taxonomy not found at {TAXONOMY_PATH}")
            # Fallback to empty - will still work but extract no skills
            self.skills = {}
            self.patterns = []
    
    def extract_skills(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract skills from text.
        
        Returns:
            List of dicts: [{'skill_name': 'Python', 'category': 'Programming Language', 'mention_count': 3}, ...]
        """
        if not text:
            return []
        
        found_skills = {}  # canonical_name -> {category, subcategory, count}
        
        for pattern, canonical_name, category, subcategory in self.patterns:
            matches = pattern.findall(text)
            if matches:
                if canonical_name not in found_skills:
                    found_skills[canonical_name] = {
                        'category': category,
                        'subcategory': subcategory,
                        'count': 0
                    }
                found_skills[canonical_name]['count'] += len(matches)
        
        # Build result
        results = []
        for skill_name, info in found_skills.items():
            results.append({
                'skill_name': skill_name,
                'category': info['category'],
                'subcategory': info['subcategory'],
                'mention_count': info['count']
            })
        
        # Sort by count descending
        results.sort(key=lambda x: x['mention_count'], reverse=True)
        
        return results


# Global extractor instance (loaded once)
skill_extractor = ResumeSkillExtractor()


def extract_text_from_bytes(content: bytes, filename: str) -> str:
    """
    Extract text from file bytes synchronously.
    Supports: PDF, DOCX, TXT, and common text formats.
    """
    filename = filename.lower()

    try:
        # Plain text files
        if filename.endswith(('.txt', '.md', '.csv')):
            return content.decode('utf-8', errors='ignore')

        # PDF files
        elif filename.endswith('.pdf'):
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() or ""
                return text
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="PDF support not installed. Please install PyPDF2."
                )
        
        # Word documents
        elif filename.endswith(('.docx', '.doc')):
            try:
                import docx
                doc = docx.Document(io.BytesIO(content))
                text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
                return text
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="DOCX support not installed. Please install python-docx."
                )
        
        # Images (OCR) - optional, requires pytesseract
        elif filename.endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
            try:
                import pytesseract
                from PIL import Image
                image = Image.open(io.BytesIO(content))
                text = pytesseract.image_to_string(image)
                return text
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="Image OCR not installed. Please install pytesseract and Pillow."
                )
        
        else:
            # Try to decode as text anyway
            return content.decode('utf-8', errors='ignore')

    except Exception as e:
        logger.error(f"Error extracting text from {filename}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not extract text from file: {str(e)}"
        )


async def extract_text_from_file(file: UploadFile) -> tuple:
    """Read file bytes and extract text. Returns (bytes, text)."""
    content = await file.read()
    text = extract_text_from_bytes(content, file.filename)
    return content, text


async def _persist_analysis(
    db: "Database",
    filename: str,
    file_size: int,
    file_bytes: bytes,
    analysis_type: str,
    target_role: Optional[str],
    country: Optional[str],
    extracted_skills: list,
    match_score: Optional[float] = None,
    gap_rows: Optional[list] = None,
    role_rows: Optional[list] = None,
    user_id: Optional[str] = None,
) -> None:
    """
    Persist a full resume analysis to Supabase:
      - the file to Supabase Storage (if configured),
      - a parent row in public.resume_uploads,
      - one row per extracted skill in public.resume_skills,
      - gap-analysis detail in public.resume_gap_analysis (gap runs), OR
      - role-match detail in public.resume_role_matches (role-match runs).

    Runs best-effort in a single DB transaction — any failure is logged but
    never propagates to the user response.
    """
    from ..storage import upload_resume_file, is_storage_configured

    storage_path = None
    storage_url = None

    # 1) Upload the file to Supabase Storage (optional).
    if is_storage_configured():
        try:
            storage_path, storage_url = await upload_resume_file(file_bytes, filename)
            logger.info(f"Resume saved to storage: {storage_path}")
        except Exception as e:
            logger.warning(f"Storage upload failed (non-fatal): {e}")

    # 2) Write the parent + detail rows atomically.
    if db.pool is None:
        logger.warning("DB pool unavailable; skipping resume persistence.")
        return

    try:
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                resume_id = await conn.fetchval(
                    """
                    INSERT INTO public.resume_uploads
                        (filename, file_size, analysis_type, target_role, country,
                         extracted_skills_count, extracted_skills, match_score,
                         storage_path, storage_url, user_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11::uuid)
                    RETURNING id
                    """,
                    filename, file_size, analysis_type, target_role, country,
                    len(extracted_skills), json.dumps(extracted_skills), match_score,
                    storage_path, storage_url, user_id,
                )

                if extracted_skills:
                    await conn.executemany(
                        """
                        INSERT INTO public.resume_skills
                            (resume_id, skill_name, skill_category, mention_count)
                        VALUES ($1,$2,$3,$4)
                        """,
                        [
                            (resume_id, s.get('skill_name'), s.get('category'),
                             s.get('mention_count', 1))
                            for s in extracted_skills
                        ],
                    )

                if gap_rows:
                    await conn.executemany(
                        """
                        INSERT INTO public.resume_gap_analysis
                            (resume_id, target_role, country, skill_name, skill_category,
                             has_skill, job_count, demand_percentage, avg_salary, market_rank)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        """,
                        [
                            (resume_id, target_role, country, g['skill_name'],
                             g.get('skill_category'), g['has_skill'], g.get('job_count'),
                             g.get('demand_percentage'), g.get('avg_salary'), g.get('market_rank'))
                            for g in gap_rows
                        ],
                    )

                if role_rows:
                    await conn.executemany(
                        """
                        INSERT INTO public.resume_role_matches
                            (resume_id, country, role, match_score, matched_skills_count,
                             total_skills_evaluated, rank, top_matched_skills, top_missing_skills)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb)
                        """,
                        [
                            (resume_id, country, r['role'], r['match_score'],
                             r['matched_skills_count'], r['total_skills_evaluated'], r['rank'],
                             json.dumps(r.get('top_matched_skills', [])),
                             json.dumps(r.get('top_missing_skills', [])))
                            for r in role_rows
                        ],
                    )
        logger.info(f"Resume analysis persisted for '{filename}' ({analysis_type})")
    except Exception as e:
        logger.warning(f"DB persistence failed (non-fatal): {e}")


# ============================================
# API Endpoints
# ============================================

@router.post("/extract-skills", response_model=List[ExtractedSkill])
async def extract_skills_from_resume(
    file: UploadFile = File(..., description="Resume file (PDF, DOCX, TXT, or image)")
):
    """
    Extract skills from an uploaded resume file.
    
    Supported formats:
    - PDF (.pdf)
    - Word (.docx, .doc)
    - Text (.txt, .md)
    - Images (.png, .jpg, .jpeg) - requires OCR
    
    Returns list of extracted skills with categories and mention counts.
    """
    # Validate file type
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md', '.png', '.jpg', '.jpeg', '.webp'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Extract text from file
    file_bytes, text = await extract_text_from_file(file)
    
    if not text or len(text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract sufficient text from the file. Please check the file format."
        )
    
    # Extract skills
    skills = skill_extractor.extract_skills(text)
    
    return [ExtractedSkill(**skill) for skill in skills]


@router.post("/analyze", response_model=ResumeAnalysisResponse)
async def analyze_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Resume file (PDF, DOCX, TXT, or image)"),
    target_role: str = Form(..., description="Target job role (e.g., 'Data Engineer')"),
    country: Optional[str] = Form(None, description="Country code for market comparison (e.g., 'gb', 'us')"),
    db: Database = Depends(get_db),
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    """
    Full resume analysis: Extract skills and compare against market demand.
    
    **Feature 1: Gap Analysis**
    - Extracts skills from your resume
    - Compares against market demand for the target role
    - Shows skills you have vs skills you're missing
    
    Returns:
    - Extracted skills from resume
    - Skills you have that are in demand
    - Skills you're missing (high-demand but not on resume)
    - Match percentage
    """
    # Extract text
    file_bytes, text = await extract_text_from_file(file)
    
    if not text or len(text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract sufficient text from the file."
        )
    
    # Extract skills from resume
    resume_skills = skill_extractor.extract_skills(text)
    resume_skill_names = {s['skill_name'].lower() for s in resume_skills}
    
    # Get market demand for target role.
    # Salary uses the USD-normalized column (avg_salary_midpoint_usd) in BOTH
    # branches — same rationale as skills.py /demand: the cross-country blend
    # below would otherwise average raw INR against raw USD (the currency-
    # mixing bug fixed everywhere else), and the frontend renders these
    # numbers with a hardcoded "$" anyway.
    if country:
        query = """
            SELECT
                skill_name, skill_category, job_count, demand_percentage,
                avg_salary_midpoint_usd AS avg_salary_midpoint,
                rank_in_role_country as rank
            FROM staging_marts.mart_skill_demand
            WHERE search_role = $1 AND country_code = $2
            ORDER BY rank_in_role_country
            LIMIT 50
        """
        market_skills = await db.fetch_all(query, target_role, country)
    else:
        query = """
            SELECT
                skill_name, skill_category,
                SUM(job_count) as job_count,
                AVG(demand_percentage) as demand_percentage,
                AVG(avg_salary_midpoint_usd) as avg_salary_midpoint,
                MIN(rank_in_role_global) as rank
            FROM staging_marts.mart_skill_demand
            WHERE search_role = $1
            GROUP BY skill_name, skill_category
            ORDER BY job_count DESC
            LIMIT 50
        """
        market_skills = await db.fetch_all(query, target_role)
    
    if not market_skills:
        raise HTTPException(
            status_code=404,
            detail=f"No market data found for role: {target_role}"
        )
    
    # Categorize skills
    skills_you_have = []
    skills_you_need = []
    
    for market_skill in market_skills:
        skill_name = market_skill['skill_name']
        skill_data = {
            'skill_name': skill_name,
            'skill_category': market_skill['skill_category'],
            'job_count': market_skill['job_count'],
            'demand_percentage': market_skill['demand_percentage'],
            'avg_salary': market_skill['avg_salary_midpoint'],
            'market_rank': market_skill['rank']
        }
        
        if skill_name.lower() in resume_skill_names:
            skills_you_have.append(skill_data)
        else:
            skills_you_need.append(skill_data)
    
    # Calculate match percentage (weighted by demand)
    total_demand = sum(s['job_count'] for s in market_skills)
    matched_demand = sum(s['job_count'] for s in skills_you_have)
    match_percentage = (matched_demand / total_demand * 100) if total_demand > 0 else 0
    
    # Sort by priority
    skills_you_have.sort(key=lambda x: x['job_count'], reverse=True)
    skills_you_need.sort(key=lambda x: x['job_count'], reverse=True)

    # Build the full gap-analysis detail (one row per market skill, flagged owned/gap)
    gap_rows = [
        {
            'skill_name': s['skill_name'],
            'skill_category': s['skill_category'],
            'has_skill': True,
            'job_count': s['job_count'],
            'demand_percentage': s['demand_percentage'],
            'avg_salary': s['avg_salary'],
            'market_rank': s['market_rank'],
        }
        for s in skills_you_have
    ] + [
        {
            'skill_name': s['skill_name'],
            'skill_category': s['skill_category'],
            'has_skill': False,
            'job_count': s['job_count'],
            'demand_percentage': s['demand_percentage'],
            'avg_salary': s['avg_salary'],
            'market_rank': s['market_rank'],
        }
        for s in skills_you_need
    ]

    # Persist the full analysis to Supabase (reliable background task, best-effort)
    background_tasks.add_task(
        _persist_analysis,
        db=db,
        filename=file.filename,
        file_size=len(file_bytes),
        file_bytes=file_bytes,
        analysis_type="gap_analysis",
        target_role=target_role,
        country=country,
        extracted_skills=[
            {'skill_name': s['skill_name'], 'category': s['category'], 'mention_count': s['mention_count']}
            for s in resume_skills
        ],
        match_score=round(match_percentage, 1),
        gap_rows=gap_rows,
        user_id=user.id if user else None,
    )

    return ResumeAnalysisResponse(
        target_role=target_role,
        country=country,
        total_resume_skills=len(resume_skills),
        resume_skills=[ExtractedSkill(**s) for s in resume_skills],
        match_percentage=round(match_percentage, 1),
        skills_you_have=[SkillGapAnalysis(**s) for s in skills_you_have],
        skills_you_need=[SkillGapAnalysis(**s) for s in skills_you_need],
        top_skills_to_learn=skills_you_need[:5]
    )


@router.post("/match-roles", response_model=List[RoleMatchResult])
async def match_resume_to_roles(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Resume file (PDF, DOCX, TXT, or image)"),
    country: Optional[str] = Form(None, description="Country code (e.g., 'gb', 'us')"),
    limit: int = Form(10, ge=1, le=20, description="Number of top matching roles to return"),
    db: Database = Depends(get_db),
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    """
    Match resume skills against all job roles to find the best fit.
    
    **Feature 2: Role Matching**
    - Extracts skills from your resume
    - Compares against skill requirements for all tracked roles
    - Uses weighted scoring based on skill demand
    
    **Scoring Formula:**
    ```
    Score = Σ(skill_match × demand_weight) / Σ(demand_weight) × 100
    ```
    Where demand_weight = job_count for that skill in that role.
    
    This means:
    - Having high-demand skills for a role increases your score more
    - A role where you have the TOP skills will score higher than one where you have niche skills
    
    Returns top N matching roles with:
    - Match score (0-100)
    - Number of matching skills
    - Top skills you have for that role
    - Top skills you're missing for that role
    """
    # Extract text
    file_bytes, text = await extract_text_from_file(file)
    
    if not text or len(text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract sufficient text from the file."
        )
    
    # Extract skills from resume
    resume_skills = skill_extractor.extract_skills(text)
    resume_skill_names = {s['skill_name'].lower() for s in resume_skills}
    
    if not resume_skill_names:
        raise HTTPException(
            status_code=400,
            detail="No recognizable skills found in the resume."
        )
    
    # Get all available roles
    roles_query = """
        SELECT DISTINCT search_role FROM staging_marts.mart_skill_demand
    """
    roles = await db.fetch_all(roles_query)
    
    if not roles:
        raise HTTPException(
            status_code=404,
            detail="No role data available in the database."
        )
    
    # Calculate match score for each role
    role_matches = []
    
    for role_row in roles:
        role = role_row['search_role']
        
        # Get top skills for this role
        if country:
            query = """
                SELECT skill_name, skill_category, job_count, demand_percentage
                FROM staging_marts.mart_skill_demand
                WHERE search_role = $1 AND country_code = $2
                ORDER BY job_count DESC
                LIMIT 30
            """
            role_skills = await db.fetch_all(query, role, country)
        else:
            query = """
                SELECT 
                    skill_name, skill_category,
                    SUM(job_count) as job_count,
                    AVG(demand_percentage) as demand_percentage
                FROM staging_marts.mart_skill_demand
                WHERE search_role = $1
                GROUP BY skill_name, skill_category
                ORDER BY job_count DESC
                LIMIT 30
            """
            role_skills = await db.fetch_all(query, role)
        
        if not role_skills:
            continue
        
        # Calculate weighted match score
        total_weight = sum(s['job_count'] for s in role_skills)
        matched_weight = 0
        matched_skills = []
        missing_skills = []
        
        for skill in role_skills:
            if skill['skill_name'].lower() in resume_skill_names:
                matched_weight += skill['job_count']
                matched_skills.append({
                    'skill_name': skill['skill_name'],
                    'category': skill['skill_category'],
                    'job_count': skill['job_count']
                })
            else:
                missing_skills.append({
                    'skill_name': skill['skill_name'],
                    'category': skill['skill_category'],
                    'job_count': skill['job_count']
                })
        
        match_score = (matched_weight / total_weight * 100) if total_weight > 0 else 0
        
        role_matches.append({
            'role': role,
            'match_score': round(match_score, 1),
            'matched_skills_count': len(matched_skills),
            'total_skills_evaluated': len(role_skills),
            'top_matched_skills': matched_skills[:5],  # Top 5 skills you have
            'top_missing_skills': missing_skills[:5]   # Top 5 skills you need
        })
    
    # Sort by match score descending
    role_matches.sort(key=lambda x: x['match_score'], reverse=True)
    top_matches = role_matches[:limit]

    # Rank every evaluated role for persistence (1 = best fit)
    role_rows = [{**r, 'rank': i + 1} for i, r in enumerate(role_matches)]
    top_role = top_matches[0]['role'] if top_matches else None
    top_score = top_matches[0]['match_score'] if top_matches else None

    # Persist the full analysis to Supabase (reliable background task, best-effort)
    background_tasks.add_task(
        _persist_analysis,
        db=db,
        filename=file.filename,
        file_size=len(file_bytes),
        file_bytes=file_bytes,
        analysis_type="role_match",
        target_role=top_role,
        country=country,
        extracted_skills=[
            {'skill_name': s['skill_name'], 'category': s['category'], 'mention_count': s['mention_count']}
            for s in resume_skills
        ],
        match_score=top_score,
        role_rows=role_rows,
        user_id=user.id if user else None,
    )

    return [RoleMatchResult(**r) for r in top_matches]


@router.get("/supported-roles")
async def get_supported_roles(db: Database = Depends(get_db)):
    """Get list of all job roles available for analysis."""
    query = """
        SELECT DISTINCT search_role as role
        FROM staging_marts.mart_skill_demand
        ORDER BY search_role
    """
    rows = await db.fetch_all(query)
    return {"roles": [r['role'] for r in rows]}
