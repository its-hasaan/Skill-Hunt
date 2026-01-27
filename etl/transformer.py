"""
Skill Hunt - Skill Extraction Transformer
==========================================
Extracts skills from job descriptions using HYBRID approach:
- Fast Path: Regex-based matching for known skills (instant, free)
- Slow Path: GLiNER NER-based extraction for skill discovery (local, free)

Processes raw.jobs -> staging.stg_jobs + staging.stg_job_skills

This transformer:
1. Reads unprocessed jobs from raw.jobs
2. Cleans and normalizes job data into staging.stg_jobs
3. Extracts skills using hybrid extractor (taxonomy + GLiNER discovery)
4. Tracks new skill discoveries as "Unverified" for manual review
5. Normalization (React.js -> React) handled by dbt layer

Usage:
    python transformer.py                    # Process all unprocessed jobs
    python transformer.py --batch-size 500   # Process in smaller batches
    python transformer.py --reprocess        # Reprocess all jobs (dangerous)
    python transformer.py --discovery-mode   # Force GLiNER for all jobs
    python transformer.py --fast-only        # Disable GLiNER, taxonomy only
"""

import os
import sys
import re
import json
import argparse
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict, Set, Tuple, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('transformation.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

DB_URL = os.getenv("SUPABASE_URL")
SKILLS_TAXONOMY_PATH = Path(__file__).parent / "config" / "skills_taxonomy.json"

# GLiNER settings (can be overridden via CLI or env)
ENABLE_GLINER = os.getenv("ENABLE_GLINER", "true").lower() == "true"
GLINER_MODEL = os.getenv("GLINER_MODEL", "urchade/gliner_medium-v2.1")
DISCOVERY_SAMPLE_RATE = float(os.getenv("DISCOVERY_SAMPLE_RATE", "0.1"))  # 10% of jobs


# =============================================================================
# HYBRID SKILL EXTRACTOR INTEGRATION
# =============================================================================

def create_skill_extractor(
    discovery_mode: bool = False,
    fast_only: bool = False,
    db_connection=None
):
    """
    Factory function to create the skill extractor.
    
    Args:
        discovery_mode: If True, always use GLiNER for all jobs
        fast_only: If True, disable GLiNER entirely (taxonomy only)
        db_connection: Database connection for discovery persistence
    
    Returns:
        Configured skill extractor instance
    """
    try:
        from skill_extractor import HybridSkillExtractor, HybridConfig
        
        config = HybridConfig(
            taxonomy_path=SKILLS_TAXONOMY_PATH,
            enable_gliner=ENABLE_GLINER and not fast_only,
            gliner_model=GLINER_MODEL,
            always_discover=discovery_mode,
            discovery_sample_rate=DISCOVERY_SAMPLE_RATE if not fast_only else 0,
            auto_promote=True
        )
        
        extractor = HybridSkillExtractor(
            config=config,
            db_connection=db_connection
        )
        
        logger.info(f"Initialized HybridSkillExtractor in '{extractor.mode}' mode")
        logger.info(f"Known skills in taxonomy: {extractor.get_known_skills_count()}")
        
        if extractor.mode == 'hybrid':
            logger.info("GLiNER discovery enabled for finding new skills")
        
        return extractor
        
    except ImportError:
        logger.warning("HybridSkillExtractor not available, falling back to legacy extractor")
        return LegacySkillExtractor(SKILLS_TAXONOMY_PATH)


class LegacySkillExtractor:
    """
    Fallback extractor using only regex matching (original behavior).
    Used when hybrid extractor dependencies are not available.
    """
    
    def __init__(self, taxonomy_path: Path):
        self.skills = {}
        self.patterns = []
        self._load_taxonomy(taxonomy_path)
    
    def _load_taxonomy(self, taxonomy_path: Path):
        try:
            with open(taxonomy_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error(f"Skills taxonomy not found: {taxonomy_path}")
            sys.exit(1)
        
        for skill in data.get('skills', []):
            name = skill['name']
            category = skill.get('category', 'Unknown')
            subcategory = skill.get('subcategory', '')
            aliases = skill.get('aliases', [])
            
            self.skills[name.lower()] = {
                'name': name,
                'category': category,
                'subcategory': subcategory
            }
            
            all_terms = [name] + aliases
            for term in all_terms:
                escaped_term = re.escape(term)
                if term in ['C++', 'C#', '.NET']:
                    pattern = re.compile(rf'(?<![a-zA-Z]){escaped_term}(?![a-zA-Z])', re.IGNORECASE)
                else:
                    pattern = re.compile(rf'\b{escaped_term}\b', re.IGNORECASE)
                self.patterns.append((pattern, name))
        
        logger.info(f"LegacyExtractor: Loaded {len(self.skills)} skills")
    
    def extract_skills(self, text: str, context: str = "") -> List[Dict]:
        if not text:
            return []
        
        found_skills = {}
        for pattern, canonical_name in self.patterns:
            matches = pattern.findall(text)
            if matches:
                if canonical_name not in found_skills:
                    found_skills[canonical_name] = 0
                found_skills[canonical_name] += len(matches)
        
        results = []
        for skill_name, count in found_skills.items():
            skill_info = self.skills.get(skill_name.lower(), {})
            results.append({
                'skill_name': skill_name,
                'category': skill_info.get('category', 'Unknown'),
                'subcategory': skill_info.get('subcategory', ''),
                'mention_count': count,
                'extraction_method': 'legacy'
            })
        
        results.sort(key=lambda x: x['mention_count'], reverse=True)
        return results
    
    def get_stats(self) -> Dict:
        return {'mode': 'legacy', 'total_skills': len(self.skills)}
    
    def get_known_skills_count(self) -> int:
        return len(self.skills)


class SkillExtractor:
    """
    DEPRECATED: Legacy class kept for backward compatibility.
    Use create_skill_extractor() instead.
    """
    """
    Extracts skills from text using a taxonomy-based approach.
    Uses regex patterns with word boundaries for accurate matching.
    """
    
    def __init__(self, taxonomy_path: Path):
        """
        Initialize the skill extractor with a taxonomy file.
        
        Args:
            taxonomy_path: Path to skills_taxonomy.json
        """
        self.skills = {}  # skill_name -> {category, subcategory, pattern}
        self.patterns = []  # List of (pattern, canonical_name)
        self._load_taxonomy(taxonomy_path)
    
    def _load_taxonomy(self, taxonomy_path: Path):
        """Load and compile skill patterns from taxonomy file."""
        try:
            with open(taxonomy_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error(f"Skills taxonomy not found: {taxonomy_path}")
            sys.exit(1)
        
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
                # Escape special regex characters
                escaped_term = re.escape(term)
                # Create word boundary pattern (case-insensitive)
                # Handle special cases like C++, C#, .NET
                if term in ['C++', 'C#', '.NET']:
                    pattern = re.compile(rf'(?<![a-zA-Z]){escaped_term}(?![a-zA-Z])', re.IGNORECASE)
                else:
                    pattern = re.compile(rf'\b{escaped_term}\b', re.IGNORECASE)
                self.patterns.append((pattern, name))
        
        logger.info(f"Loaded {len(self.skills)} skills with {len(self.patterns)} patterns")
    
    def extract_skills(self, text: str) -> List[Dict]:
        """
        Extract skills from text.
        
        Args:
            text: Job description or other text to analyze
        
        Returns:
            List of dicts: [{'skill_name': 'Python', 'category': 'Programming Language', 'count': 3}, ...]
        """
        if not text:
            return []
        
        # Normalize text (keep for matching)
        text_lower = text.lower()
        
        # Track found skills and counts
        found_skills = {}  # canonical_name -> count
        
        for pattern, canonical_name in self.patterns:
            matches = pattern.findall(text)
            if matches:
                if canonical_name not in found_skills:
                    found_skills[canonical_name] = 0
                found_skills[canonical_name] += len(matches)
        
        # Build result
        results = []
        for skill_name, count in found_skills.items():
            skill_info = self.skills.get(skill_name.lower(), {})
            results.append({
                'skill_name': skill_name,
                'category': skill_info.get('category', 'Unknown'),
                'subcategory': skill_info.get('subcategory', ''),
                'mention_count': count
            })
        
        # Sort by count descending
        results.sort(key=lambda x: x['mention_count'], reverse=True)
        
        return results


def get_db_connection():
    """Create and return a database connection."""
    if not DB_URL:
        logger.error("SUPABASE_URL not set in environment")
        sys.exit(1)
    return psycopg2.connect(DB_URL)


def get_or_create_skill(cursor, skill_name: str, category: str, subcategory: str) -> int:
    """
    Get skill_id from dim_skills, or create if not exists.
    
    Args:
        cursor: Database cursor
        skill_name: Canonical skill name
        category: Skill category
        subcategory: Skill subcategory
    
    Returns:
        skill_id (int)
    """
    # Try to get existing skill
    cursor.execute(
        "SELECT skill_id FROM staging.dim_skills WHERE skill_name = %s",
        (skill_name,)
    )
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    # Create new skill
    cursor.execute(
        """
        INSERT INTO staging.dim_skills (skill_name, skill_category, skill_subcategory)
        VALUES (%s, %s, %s)
        RETURNING skill_id
        """,
        (skill_name, category, subcategory)
    )
    return cursor.fetchone()[0]


def parse_raw_job(raw_data: dict, raw_job_id: int, search_role: str, country_code: str) -> dict:
    """
    Parse raw job JSON into cleaned staging format.
    
    Args:
        raw_data: Raw JSON from Adzuna API
        raw_job_id: ID from raw.jobs table
        search_role: Role that was searched
        country_code: Country code
    
    Returns:
        Dict with cleaned job data
    """
    # Currency mapping by country
    currency_map = {
        'gb': 'GBP', 'us': 'USD', 'au': 'AUD', 'ca': 'CAD',
        'de': 'EUR', 'fr': 'EUR', 'it': 'EUR', 'nl': 'EUR',
        'at': 'EUR', 'be': 'EUR', 'in': 'INR', 'br': 'BRL',
        'mx': 'MXN', 'pl': 'PLN', 'ru': 'RUB', 'sg': 'SGD',
        'za': 'ZAR', 'nz': 'NZD'
    }
    
    # Parse location
    location = raw_data.get('location', {})
    location_areas = location.get('area', []) if isinstance(location, dict) else []
    location_display = location.get('display_name', '') if isinstance(location, dict) else ''
    
    # Parse company
    company = raw_data.get('company', {})
    company_name = company.get('display_name', '') if isinstance(company, dict) else str(company) if company else ''
    
    # Parse category
    category = raw_data.get('category', {})
    category_tag = category.get('tag', '') if isinstance(category, dict) else ''
    category_label = category.get('label', '') if isinstance(category, dict) else ''
    
    # Parse dates
    created_str = raw_data.get('created', '')
    job_posted_at = None
    if created_str:
        try:
            job_posted_at = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            pass
    
    # Parse salary
    salary_min = raw_data.get('salary_min')
    salary_max = raw_data.get('salary_max')
    salary_is_predicted = raw_data.get('salary_is_predicted', '0') == '1'
    
    return {
        'job_platform_id': str(raw_data.get('id', '')),
        'search_role': search_role,
        'country_code': country_code,
        'title': raw_data.get('title', ''),
        'company_name': company_name,
        'description': raw_data.get('description', ''),
        'location_display': location_display,
        'location_areas': location_areas,
        'category_tag': category_tag,
        'category_label': category_label,
        'salary_min': salary_min,
        'salary_max': salary_max,
        'salary_is_predicted': salary_is_predicted,
        'salary_currency': currency_map.get(country_code, 'USD'),
        'contract_type': raw_data.get('contract_type', ''),
        'contract_time': raw_data.get('contract_time', ''),
        'redirect_url': raw_data.get('redirect_url', ''),
        'job_posted_at': job_posted_at,
        'raw_job_id': raw_job_id
    }


def get_unprocessed_jobs(cursor, batch_size: int = 1000) -> List[dict]:
    """
    Get raw jobs that haven't been processed yet.
    
    Args:
        cursor: Database cursor
        batch_size: Number of jobs to fetch
    
    Returns:
        List of raw job records
    """
    cursor.execute(
        """
        SELECT r.id, r.job_platform_id, r.search_role, r.country_code, r.raw_data, r.extracted_at
        FROM raw.jobs r
        LEFT JOIN staging.stg_jobs s ON r.id = s.raw_job_id
        WHERE s.job_id IS NULL
        ORDER BY r.extracted_at
        LIMIT %s
        """,
        (batch_size,)
    )
    
    columns = ['id', 'job_platform_id', 'search_role', 'country_code', 'raw_data', 'extracted_at']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def transform_and_load(
    batch_size: int = 1000,
    reprocess: bool = False,
    discovery_mode: bool = False,
    fast_only: bool = False
):
    """
    Main transformation function with hybrid skill extraction.
    
    Args:
        batch_size: Number of jobs to process per batch
        reprocess: If True, reprocess all jobs (truncates staging tables)
        discovery_mode: If True, use LLM for all jobs (expensive but thorough)
        fast_only: If True, disable LLM entirely (fast but no discovery)
    """
    logger.info("Starting transformation process...")
    logger.info(f"Mode: {'discovery' if discovery_mode else 'fast-only' if fast_only else 'hybrid'}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Initialize HYBRID skill extractor
    skill_extractor = create_skill_extractor(
        discovery_mode=discovery_mode,
        fast_only=fast_only,
        db_connection=conn
    )
    
    if reprocess:
        logger.warning("REPROCESS MODE: Truncating staging tables...")
        cursor.execute("TRUNCATE staging.stg_job_skills CASCADE")
        cursor.execute("TRUNCATE staging.stg_jobs CASCADE")
        conn.commit()
    
    # Statistics
    total_processed = 0
    total_skills_extracted = 0
    start_time = datetime.now()
    
    while True:
        # Get batch of unprocessed jobs
        raw_jobs = get_unprocessed_jobs(cursor, batch_size)
        
        if not raw_jobs:
            logger.info("No more unprocessed jobs found.")
            break
        
        logger.info(f"Processing batch of {len(raw_jobs)} jobs...")
        
        for raw_job in raw_jobs:
            try:
                raw_data = raw_job['raw_data']
                if isinstance(raw_data, str):
                    raw_data = json.loads(raw_data)
                
                # Parse raw job into staging format
                parsed_job = parse_raw_job(
                    raw_data,
                    raw_job['id'],
                    raw_job['search_role'],
                    raw_job['country_code']
                )
                
                # Insert into stg_jobs
                cursor.execute(
                    """
                    INSERT INTO staging.stg_jobs (
                        job_platform_id, search_role, country_code, title, company_name,
                        description, location_display, location_areas, category_tag,
                        category_label, salary_min, salary_max, salary_is_predicted,
                        salary_currency, contract_type, contract_time, redirect_url,
                        job_posted_at, extracted_at, raw_job_id
                    ) VALUES (
                        %(job_platform_id)s, %(search_role)s, %(country_code)s, %(title)s,
                        %(company_name)s, %(description)s, %(location_display)s,
                        %(location_areas)s, %(category_tag)s, %(category_label)s,
                        %(salary_min)s, %(salary_max)s, %(salary_is_predicted)s,
                        %(salary_currency)s, %(contract_type)s, %(contract_time)s,
                        %(redirect_url)s, %(job_posted_at)s, %(extracted_at)s, %(raw_job_id)s
                    )
                    ON CONFLICT (job_platform_id, country_code) DO UPDATE SET
                        processed_at = NOW()
                    RETURNING job_id
                    """,
                    {**parsed_job, 'extracted_at': raw_job['extracted_at']}
                )
                
                job_id = cursor.fetchone()[0]
                
                # Extract skills from description + title using HYBRID extractor
                text_to_analyze = f"{parsed_job['title']} {parsed_job['description']}"
                context = f"{parsed_job['title']} @ {parsed_job['company_name']}"
                skills = skill_extractor.extract_skills(text_to_analyze, context=context)
                
                # Insert skills
                for skill in skills:
                    # Handle both mention_count (fast path) and confidence (slow path)
                    mention_count = skill.get('mention_count', 1)
                    if mention_count == 0 and 'confidence' in skill:
                        mention_count = 1  # LLM-extracted skills count as 1 mention
                    
                    skill_id = get_or_create_skill(
                        cursor,
                        skill['skill_name'],
                        skill['category'],
                        skill.get('subcategory', '')
                    )
                    
                    cursor.execute(
                        """
                        INSERT INTO staging.stg_job_skills (job_id, skill_id, skill_name, mention_count)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (job_id, skill_id) DO UPDATE SET
                            mention_count = EXCLUDED.mention_count
                        """,
                        (job_id, skill_id, skill['skill_name'], mention_count)
                    )
                    total_skills_extracted += 1
                
                total_processed += 1
                
            except Exception as e:
                logger.error(f"Error processing job {raw_job['id']}: {e}")
                continue
        
        # Commit after each batch
        conn.commit()
        logger.info(f"Batch complete. Total processed: {total_processed}")
    
    # Final commit
    conn.commit()
    
    # Get extraction statistics from hybrid extractor
    extractor_stats = skill_extractor.get_stats() if hasattr(skill_extractor, 'get_stats') else {}
    
    cursor.close()
    conn.close()
    
    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\n{'='*60}")
    logger.info(f"TRANSFORMATION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Jobs processed: {total_processed}")
    logger.info(f"Skills extracted: {total_skills_extracted}")
    logger.info(f"Time elapsed: {elapsed:.2f} seconds")
    
    # Hybrid extractor stats
    if extractor_stats:
        logger.info(f"\n--- Hybrid Extractor Stats ---")
        logger.info(f"Total extractions: {extractor_stats.get('total_extractions', 'N/A')}")
        logger.info(f"Fast path only: {extractor_stats.get('fast_path_only', 'N/A')}")
        logger.info(f"Slow path invoked: {extractor_stats.get('slow_path_invoked', 'N/A')}")
        logger.info(f"New discoveries: {extractor_stats.get('new_discoveries', 'N/A')}")
        
        discovery_stats = extractor_stats.get('discovery', {})
        if discovery_stats:
            logger.info(f"\n--- Discovery Stats ---")
            logger.info(f"Total discovered: {discovery_stats.get('total_discoveries', 0)}")
            logger.info(f"Promoted to taxonomy: {discovery_stats.get('promoted_count', 0)}")
            logger.info(f"Pending promotion: {discovery_stats.get('pending_promotion', 0)}")
            
            top_pending = discovery_stats.get('top_pending', [])
            if top_pending:
                logger.info(f"\nTop pending discoveries:")
                for skill in top_pending[:5]:
                    logger.info(f"  - {skill['name']} ({skill['category']}) - seen {skill['occurrences']}x")
    
    logger.info(f"{'='*60}")
    
    return {
        "jobs_processed": total_processed,
        "skills_extracted": total_skills_extracted,
        "elapsed_seconds": elapsed,
        "extractor_stats": extractor_stats
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Transform raw job data and extract skills using hybrid approach (taxonomy + GLiNER)'
    )
    parser.add_argument('--batch-size', type=int, default=1000, help='Jobs per batch')
    parser.add_argument('--reprocess', action='store_true', help='Reprocess all jobs (dangerous!)')
    parser.add_argument(
        '--discovery-mode',
        action='store_true',
        help='Force GLiNER extraction for ALL jobs (slower, but finds more skills)'
    )
    parser.add_argument(
        '--fast-only',
        action='store_true',
        help='Disable GLiNER entirely, use only taxonomy-based extraction (fast)'
    )
    
    args = parser.parse_args()
    
    if args.discovery_mode and args.fast_only:
        logger.error("Cannot use both --discovery-mode and --fast-only")
        sys.exit(1)
    
    if args.reprocess:
        confirm = input("WARNING: This will delete all staging data. Type 'YES' to confirm: ")
        if confirm != 'YES':
            logger.info("Aborted.")
            return
    
    transform_and_load(
        batch_size=args.batch_size,
        reprocess=args.reprocess,
        discovery_mode=args.discovery_mode,
        fast_only=args.fast_only
    )


if __name__ == "__main__":
    main()