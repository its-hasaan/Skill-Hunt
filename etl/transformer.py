"""
Job Script - Skill Extraction Transformer
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
import time
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict, Set, Tuple, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_patterns import build_patterns  # noqa: E402  (shared with the API)
from connectors.utils import RoleMatcher  # noqa: E402

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
            
        self.patterns = build_patterns(data.get('skills', []))
        logger.info(f"LegacyExtractor: Loaded {len(self.skills)} skills")
    
    def extract_skills(self, text: str, context: str = "") -> List[Dict]:
        if not text:
            return []
        
        found_skills = {}
        lowered = text.lower()  # once per text: cheap prefilter for every pattern
        for pattern in self.patterns:
            n = pattern.count(text, lowered)
            if n:
                found_skills[pattern.canonical] = found_skills.get(pattern.canonical, 0) + n
        
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


def get_db_connection():
    """Create and return a database connection."""
    if not DB_URL:
        logger.error("SUPABASE_URL not set in environment")
        sys.exit(1)
    return psycopg2.connect(DB_URL)


# In-memory cache of skill_name -> skill_id. dim_skills is small (hundreds of
# rows) and effectively append-only during a run, so caching it eliminates the
# per-skill SELECT round-trip that otherwise dominates transform time (each job
# mentions ~5-10 skills, so this is the difference between ~15 DB round-trips
# per job and ~1). Pre-warmed by warm_skill_cache() at the start of a run.
_SKILL_CACHE: Dict[str, int] = {}


def warm_skill_cache(cursor) -> int:
    """Load all existing skills into the in-memory cache in one query."""
    cursor.execute("SELECT skill_name, skill_id FROM staging.dim_skills")
    _SKILL_CACHE.clear()
    for name, sid in cursor.fetchall():
        _SKILL_CACHE[name] = sid
    return len(_SKILL_CACHE)


def get_or_create_skill(cursor, skill_name: str, category: str, subcategory: str) -> int:
    """
    Get skill_id from dim_skills, or create if not exists.

    Uses a read-through in-memory cache (`_SKILL_CACHE`) so known skills cost
    zero DB round-trips; only genuinely new skills hit the database.

    Args:
        cursor: Database cursor
        skill_name: Canonical skill name
        category: Skill category
        subcategory: Skill subcategory

    Returns:
        skill_id (int)
    """
    cached = _SKILL_CACHE.get(skill_name)
    if cached is not None:
        return cached

    # Cache miss — look it up (covers rows created before the cache warmed).
    cursor.execute(
        "SELECT skill_id FROM staging.dim_skills WHERE skill_name = %s",
        (skill_name,)
    )
    result = cursor.fetchone()

    if result:
        _SKILL_CACHE[skill_name] = result[0]
        return result[0]

    # Create new skill
    cursor.execute(
        """
        INSERT INTO staging.dim_skills (skill_name, skill_category, skill_subcategory)
        VALUES (%s, %s, %s)
        ON CONFLICT (skill_name) DO UPDATE SET skill_name = EXCLUDED.skill_name
        RETURNING skill_id
        """,
        (skill_name, category, subcategory)
    )
    skill_id = cursor.fetchone()[0]
    _SKILL_CACHE[skill_name] = skill_id
    return skill_id


def _parse_datetime(value):
    """Coerce an ISO string / datetime / None into a datetime (or None)."""
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def parse_normalized_job(raw_data: dict, raw_job_id: int, search_role: str,
                         country_code: str, source: str, job_platform_id: str) -> dict:
    """Parse a job stored by the multi-source connectors.

    These land in raw.jobs with a `_normalized` envelope already in the exact
    staging shape (see etl/connectors/base.NormalizedJob), so this is a
    straight pass-through — no source-specific logic needed here.
    """
    n = raw_data.get('_normalized', {})
    return {
        'job_platform_id': job_platform_id or n.get('job_platform_id') or f"{source}:{n.get('external_id', '')}",
        'search_role': search_role,
        'country_code': country_code,
        'title': n.get('title', ''),
        'company_name': n.get('company_name', ''),
        'description': n.get('description', ''),
        'location_display': n.get('location_display', ''),
        'location_areas': n.get('location_areas', []) or [],
        'category_tag': n.get('category_tag', ''),
        'category_label': n.get('category_label', ''),
        'salary_min': n.get('salary_min'),
        'salary_max': n.get('salary_max'),
        'salary_is_predicted': bool(n.get('salary_is_predicted', False)),
        'salary_currency': n.get('salary_currency', 'USD'),
        'contract_type': n.get('contract_type', ''),
        'contract_time': n.get('contract_time', ''),
        'redirect_url': n.get('redirect_url', ''),
        'job_posted_at': _parse_datetime(n.get('job_posted_at')),
        'raw_job_id': raw_job_id,
        'source': source,
        'workplace_type': n.get('workplace_type') or None,
    }


def parse_raw_job(raw_data: dict, raw_job_id: int, search_role: str, country_code: str,
                  source: str = 'adzuna', job_platform_id: str = None) -> dict:
    """
    Parse raw job JSON into cleaned staging format.

    Dispatches by source: connector-ingested jobs carry a `_normalized`
    envelope and pass straight through; everything else is treated as the
    Adzuna API shape (original behavior, unchanged).

    Args:
        raw_data: Raw JSON (Adzuna response or connector envelope)
        raw_job_id: ID from raw.jobs table
        search_role: Role that was searched
        country_code: Country code
        source: Provider name ('adzuna' by default)
        job_platform_id: Namespaced id from raw.jobs (used for non-Adzuna sources)

    Returns:
        Dict with cleaned job data
    """
    # Multi-source fast path: already normalized by the connector.
    if isinstance(raw_data, dict) and raw_data.get('_normalized'):
        return parse_normalized_job(raw_data, raw_job_id, search_role, country_code,
                                    source, job_platform_id)

    # Currency mapping by country
    currency_map = {
        'gb': 'GBP', 'us': 'USD', 'au': 'AUD', 'ca': 'CAD',
        'de': 'EUR', 'fr': 'EUR', 'it': 'EUR', 'nl': 'EUR',
        'at': 'EUR', 'be': 'EUR', 'in': 'INR', 'br': 'BRL',
        'mx': 'MXN', 'pl': 'PLN', 'ru': 'RUB', 'sg': 'SGD',
        'za': 'ZAR', 'nz': 'NZD', 'pk': 'PKR', 'remote': 'USD'
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
    # Adzuna sends "1"/"0" as strings, but coerce via str() so an int 1/0
    # (or future API change) is still interpreted correctly.
    salary_is_predicted = str(raw_data.get('salary_is_predicted', '0')) in ('1', 'True', 'true')
    
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
        'raw_job_id': raw_job_id,
        'source': source,
        'workplace_type': None,  # Adzuna has no structured workplace field
    }


EXTRACTION_CONFIG_PATH = Path(__file__).parent / "config" / "extraction_config.json"

# Sources searched by keyword ("Data Engineer" -> whatever the search engine
# returns). Their search_role is only a hint; the job title decides.
KEYWORD_SOURCES = {"adzuna", "jooble"}


def validated_role(source: str, search_role: str, title: str, matcher: RoleMatcher) -> Optional[str]:
    """Keyword search is fuzzy ("Data Engineer" returns warehouse jobs), so
    for keyword-searched sources the TITLE decides the role. Feed sources
    were already classified by title in their connector."""
    if source not in KEYWORD_SOURCES:
        return search_role
    return matcher.match(title)


def load_role_matcher() -> RoleMatcher:
    with open(EXTRACTION_CONFIG_PATH, "r", encoding="utf-8") as f:
        return RoleMatcher(json.load(f)["roles"])


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
        SELECT r.id, r.job_platform_id, r.search_role, r.country_code, r.raw_data, r.extracted_at,
               COALESCE(r.source, 'adzuna') AS source
        FROM raw.jobs r
        LEFT JOIN staging.stg_jobs s ON r.id = s.raw_job_id
        WHERE s.job_id IS NULL
          AND NOT (r.raw_data ? '_stripped')  -- payload removed by ops.retention; nothing to parse
          AND r.skip_reason IS NULL           -- e.g. title matched no tracked role
        ORDER BY r.extracted_at
        LIMIT %s
        """,
        (batch_size,)
    )

    columns = ['id', 'job_platform_id', 'search_role', 'country_code', 'raw_data', 'extracted_at', 'source']
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


STG_COLUMNS = (
    "job_platform_id", "search_role", "country_code", "title", "company_name",
    "description", "location_display", "location_areas", "category_tag",
    "category_label", "salary_min", "salary_max", "salary_is_predicted",
    "salary_currency", "contract_type", "contract_time", "redirect_url",
    "job_posted_at", "extracted_at", "raw_job_id", "source", "workplace_type",
)

# DO NOTHING (not DO UPDATE): a key already in staging belongs to another raw
# row, so this raw row is a duplicate. Rows missing from RETURNING are exactly
# those duplicates (in-batch repeats included), and get marked so they leave
# the queue instead of being re-fetched every batch.
_INSERT_JOBS_SQL = f"""
    INSERT INTO staging.stg_jobs ({', '.join(STG_COLUMNS)}) VALUES %s
    ON CONFLICT (job_platform_id, country_code) DO NOTHING
    RETURNING job_id, raw_job_id
"""

_INSERT_SKILLS_SQL = """
    INSERT INTO staging.stg_job_skills (job_id, skill_id, skill_name, mention_count) VALUES %s
    ON CONFLICT (job_id, skill_id) DO UPDATE SET mention_count = EXCLUDED.mention_count
"""

_CONNECTION_ERRORS = (psycopg2.OperationalError, psycopg2.InterfaceError)


def prepare_batch(raw_jobs: List[dict], role_matcher: RoleMatcher, extractor):
    """Parse, role-check and skill-extract a batch in memory (no DB writes).

    Returns (ready, skipped_ids, failed_ids) where ready is a list of
    (parsed_job, skills) pairs.
    """
    ready, skipped, failed = [], [], []
    for raw_job in raw_jobs:
        try:
            raw_data = raw_job['raw_data']
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
            parsed = parse_raw_job(
                raw_data, raw_job['id'], raw_job['search_role'], raw_job['country_code'],
                source=raw_job.get('source', 'adzuna'), job_platform_id=raw_job.get('job_platform_id'),
            )
            role = validated_role(parsed['source'], parsed['search_role'], parsed['title'] or '', role_matcher)
            if role is None:
                skipped.append(raw_job['id'])  # not a tracked tech role
                continue
            parsed['search_role'] = role
            parsed['extracted_at'] = raw_job['extracted_at']
            skills = extractor.extract_skills(f"{parsed['title']} {parsed['description']}",
                                              context=f"{parsed['title']} @ {parsed['company_name']}")
            ready.append((parsed, skills))
        except _CONNECTION_ERRORS:
            raise  # e.g. discovery persistence lost the connection: reconnect, don't blame the job
        except Exception as e:
            logger.error(f"Error preparing job {raw_job['id']}: {e}")
            failed.append(raw_job['id'])
    return ready, skipped, failed


def resolve_skill_ids(cursor, ready) -> None:
    """Make sure every extracted skill has a dim_skills id in the cache.

    Runs before the batch savepoint, so a rolled-back job insert never
    leaves the cache pointing at a skill row that doesn't exist.
    """
    for _, skills in ready:
        for skill in skills:
            get_or_create_skill(cursor, skill['skill_name'], skill['category'], skill.get('subcategory', ''))


def write_jobs(cursor, ready) -> Tuple[Dict[int, int], int]:
    """Bulk-insert jobs, then their skills. Returns ({raw_job_id: job_id}, skill_rows)."""
    values = [tuple(parsed[c] for c in STG_COLUMNS) for parsed, _ in ready]
    returned = execute_values(cursor, _INSERT_JOBS_SQL, values, page_size=500, fetch=True)
    job_ids = {raw_id: job_id for job_id, raw_id in returned}

    skill_rows = {}
    for parsed, skills in ready:
        job_id = job_ids.get(parsed['raw_job_id'])
        if job_id is None:
            continue
        for skill in skills:
            mention_count = skill.get('mention_count', 1)
            if mention_count == 0 and 'confidence' in skill:
                mention_count = 1  # LLM-extracted skills count as 1 mention
            key = (job_id, _SKILL_CACHE[skill['skill_name']])
            prev = skill_rows.get(key)
            if prev is None or mention_count > prev[3]:
                skill_rows[key] = (*key, skill['skill_name'], mention_count)
    if skill_rows:
        execute_values(cursor, _INSERT_SKILLS_SQL, list(skill_rows.values()), page_size=1000)
    return job_ids, len(skill_rows)


def _mark(cursor, raw_ids, reason: str) -> None:
    if raw_ids:
        cursor.execute("UPDATE raw.jobs SET skip_reason = %s WHERE id = ANY(%s)", (reason, list(raw_ids)))


def process_batch(cursor, raw_jobs, role_matcher, extractor) -> Dict[str, int]:
    """Transform one batch inside the caller's transaction (caller commits).

    Every fetched row leaves the queue: it lands in staging, or is marked
    role_mismatch / duplicate / transform_error (reversible: clear
    skip_reason to retry).
    """
    ready, skipped, failed = prepare_batch(raw_jobs, role_matcher, extractor)
    _mark(cursor, skipped, 'role_mismatch')
    resolve_skill_ids(cursor, ready)

    cursor.execute("SAVEPOINT batch_sp")
    try:
        job_ids, skill_rows = write_jobs(cursor, ready)
        cursor.execute("RELEASE SAVEPOINT batch_sp")
    except _CONNECTION_ERRORS:
        raise
    except psycopg2.Error as e:
        # One bad row poisons a bulk statement; redo the batch row by row so
        # only that row fails.
        logger.warning(f"Bulk insert failed ({e.__class__.__name__}); retrying batch row by row")
        cursor.execute("ROLLBACK TO SAVEPOINT batch_sp")
        job_ids, skill_rows = {}, 0
        for item in ready:
            cursor.execute("SAVEPOINT job_sp")
            try:
                ids, n = write_jobs(cursor, [item])
                cursor.execute("RELEASE SAVEPOINT job_sp")
                job_ids.update(ids)
                skill_rows += n
            except _CONNECTION_ERRORS:
                raise
            except psycopg2.Error as row_error:
                cursor.execute("ROLLBACK TO SAVEPOINT job_sp")
                logger.error(f"Error writing job {item[0]['raw_job_id']}: {row_error}")
                failed.append(item[0]['raw_job_id'])

    failed_set = set(failed)
    duplicates = [p['raw_job_id'] for p, _ in ready
                  if p['raw_job_id'] not in job_ids and p['raw_job_id'] not in failed_set]
    _mark(cursor, duplicates, 'duplicate')
    _mark(cursor, failed, 'transform_error')
    return {"processed": len(job_ids), "skipped": len(skipped), "failed": len(failed),
            "duplicates": len(duplicates), "skills": skill_rows}


def _close_quietly(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass


def transform_and_load(
    batch_size: int = 1000,
    reprocess: bool = False,
    discovery_mode: bool = False,
    fast_only: bool = False,
    connect=None,
    extractor=None,
    sleep=time.sleep,
    max_reconnects: int = 5,
):
    """
    Main transformation function with hybrid skill extraction.

    Each batch is written with two bulk statements (jobs, then skills) and
    committed. A dropped connection (Supabase pooler restarts, network
    blips) reconnects with backoff and carries on from the next
    unprocessed job; it gives up after `max_reconnects` failures in a row.

    Args:
        batch_size: Number of jobs to process per batch
        reprocess: If True, reprocess all jobs (truncates staging tables)
        discovery_mode: If True, use LLM for all jobs (expensive but thorough)
        fast_only: If True, disable LLM entirely (fast but no discovery)
        connect: Connection factory (defaults to SUPABASE_URL)
        extractor: Skill extractor (defaults to the hybrid extractor)
    """
    logger.info("Starting transformation process...")
    logger.info(f"Mode: {'discovery' if discovery_mode else 'fast-only' if fast_only else 'hybrid'}")

    connect = connect or get_db_connection
    conn = connect()
    cursor = conn.cursor()

    # Pre-warm the skill_id cache in one query so per-job skill lookups don't
    # each round-trip to the DB.
    cached_skills = warm_skill_cache(cursor)
    logger.info(f"Warmed skill cache: {cached_skills} skills")

    skill_extractor = extractor or create_skill_extractor(
        discovery_mode=discovery_mode,
        fast_only=fast_only,
        db_connection=conn
    )

    if reprocess:
        logger.warning("REPROCESS MODE: Truncating staging tables...")
        cursor.execute("TRUNCATE staging.stg_job_skills CASCADE")
        cursor.execute("TRUNCATE staging.stg_jobs CASCADE")
        conn.commit()

    role_matcher = load_role_matcher()

    totals = {"processed": 0, "skipped": 0, "failed": 0, "duplicates": 0, "skills": 0}
    reconnects = 0
    failures_in_row = 0
    start_time = datetime.now()

    while True:
        try:
            if conn is None:
                conn = connect()
                cursor = conn.cursor()
                reconnects += 1
                warm_skill_cache(cursor)  # skills created in the lost transaction are gone
                manager = getattr(skill_extractor, 'discovery_manager', None)
                if manager is not None:
                    manager.db_conn = conn
                logger.info("Reconnected to the database")

            raw_jobs = get_unprocessed_jobs(cursor, batch_size)
            if not raw_jobs:
                logger.info("No more unprocessed jobs found.")
                break

            batch = process_batch(cursor, raw_jobs, role_matcher, skill_extractor)
            conn.commit()
            failures_in_row = 0
        except _CONNECTION_ERRORS as e:
            failures_in_row += 1
            if failures_in_row > max_reconnects:
                logger.error(f"Database unreachable after {max_reconnects} reconnect attempts: {e}")
                raise
            wait = min(60, 5 * 2 ** (failures_in_row - 1))
            logger.warning(f"Lost database connection ({e.__class__.__name__}); reconnecting in {wait}s")
            if conn is not None:
                _close_quietly(conn)
            conn = None
            sleep(wait)
            continue

        for key in totals:
            totals[key] += batch[key]
        logger.info(f"Batch complete: {batch}. Total processed: {totals['processed']}")

        if not (batch["processed"] or batch["skipped"] or batch["failed"] or batch["duplicates"]):
            # Nothing left the queue, so the same rows would come back forever.
            logger.error("Batch made no progress; aborting. Raw job ids (first 10): %s",
                         [j['id'] for j in raw_jobs[:10]])
            break

    total_processed = totals["processed"]
    total_failed = totals["failed"]
    total_skipped = totals["skipped"]
    total_skills_extracted = totals["skills"]

    extractor_stats = skill_extractor.get_stats() if hasattr(skill_extractor, 'get_stats') else {}

    cursor.close()
    conn.close()

    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\n{'='*60}")
    logger.info(f"TRANSFORMATION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Jobs processed: {total_processed}")
    logger.info(f"Jobs failed: {total_failed}")
    logger.info(f"Jobs skipped (title matched no tracked role): {total_skipped}")
    logger.info(f"Duplicate staging keys: {totals['duplicates']}")
    logger.info(f"Skills extracted: {total_skills_extracted}")
    logger.info(f"Reconnects: {reconnects}")
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
        "jobs_failed": total_failed,
        "jobs_skipped": total_skipped,
        "jobs_duplicate": totals["duplicates"],
        "skills_extracted": total_skills_extracted,
        "reconnects": reconnects,
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
        confirm = input(
            "WARNING: This will delete all staging data. Jobs whose raw payload was "
            "stripped by ops.retention cannot be rebuilt and will be lost. Type 'YES' to confirm: "
        )
        if confirm != 'YES':
            logger.info("Aborted.")
            return
    
    result = transform_and_load(
        batch_size=args.batch_size,
        reprocess=args.reprocess,
        discovery_mode=args.discovery_mode,
        fast_only=args.fast_only
    )

    # Surface hard failure to orchestrators (refresh_all.py / CI): failures
    # with zero successes means the run made no progress at all.
    if result["jobs_failed"] > 0 and result["jobs_processed"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()