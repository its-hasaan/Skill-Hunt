"""
Skill Hunt - Job Data Extractor
================================
Extracts job postings from Adzuna API for multiple roles and countries.
Stores raw JSON data in Supabase PostgreSQL.

Usage:
    python extractor.py                    # Run full extraction
    python extractor.py --role "Data Engineer"  # Single role
    python extractor.py --country gb       # Single country
    python extractor.py --test             # Test mode (1 role, 1 country, 1 page)
"""

import os
import sys
import json
import time
import argparse
import requests
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from datetime import datetime
import logging
from uuid import uuid4
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('extraction.log')
    ]
)
logger = logging.getLogger(__name__)

# Load secrets from .env file
load_dotenv()

# Configuration
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
DB_URL = os.getenv("SUPABASE_URL")

# Load extraction configuration
CONFIG_PATH = Path(__file__).parent / "config" / "extraction_config.json"


def load_config():
    """Load extraction configuration from JSON file."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {CONFIG_PATH}")
        sys.exit(1)


def validate_credentials():
    """Validate that all required credentials are set."""
    missing = []
    if not ADZUNA_APP_ID:
        missing.append("ADZUNA_APP_ID")
    if not ADZUNA_APP_KEY:
        missing.append("ADZUNA_APP_KEY")
    if not DB_URL:
        missing.append("SUPABASE_URL")
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Please set them in your .env file")
        sys.exit(1)


def get_jobs(role: str, country: str = "gb", page: int = 1) -> list:
    """
    Fetches jobs from Adzuna API.
    
    Args:
        role: Job role to search for (e.g., "Data Engineer")
        country: Country code (e.g., "gb", "us", "in")
        page: Page number for pagination
    
    Returns:
        List of job dictionaries from API response
    """
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": role,
        "results_per_page": 50,
        "content-type": "application/json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            total_count = data.get('count', 0)
            
            logger.info(f"[{country.upper()}] {role}: Page {page} returned {len(results)} jobs (Total available: {total_count})")
            return results
            
        elif response.status_code == 429:
            logger.warning(f"Rate limited. Waiting 60 seconds...")
            time.sleep(60)
            return get_jobs(role, country, page)  # Retry
            
        else:
            logger.error(f"API Error ({response.status_code}): {response.text[:200]}")
            return []
            
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout for {role} in {country}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []


def save_to_database(jobs: list, role: str, country: str, batch_id: str):
    """
    Saves raw job data to Supabase raw.jobs table.
    Uses batch insert for efficiency. Skips duplicates.
    
    Args:
        jobs: List of job dictionaries from API
        role: Search role used
        country: Country code
        batch_id: UUID for this extraction batch
    """
    if not jobs:
        logger.warning(f"No jobs to save for {role} in {country}")
        return 0
    
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        # Prepare data for batch insert
        insert_data = []
        for job in jobs:
            if 'id' not in job:
                continue
            insert_data.append((
                str(job['id']),
                role,
                country,
                json.dumps(job),
                batch_id
            ))
        
        if not insert_data:
            logger.warning(f"No valid jobs to insert for {role} in {country}")
            return 0
        
        # Batch insert with ON CONFLICT DO NOTHING
        query = """
            INSERT INTO raw.jobs (job_platform_id, search_role, country_code, raw_data, extraction_batch_id)
            VALUES %s
            ON CONFLICT (job_platform_id, country_code) DO NOTHING
        """
        
        execute_values(cursor, query, insert_data)
        inserted_count = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        skipped = len(insert_data) - inserted_count
        logger.info(f"[{country.upper()}] {role}: Inserted {inserted_count} new jobs, skipped {skipped} duplicates")
        
        return inserted_count
        
    except Exception as e:
        logger.error(f"Database Error: {e}")
        return 0


def extract_all(roles: list = None, countries: dict = None, max_pages: int = 2, delay: float = 1.0, test_mode: bool = False):
    """
    Main extraction function. Iterates through all roles and countries.
    
    Args:
        roles: List of job roles to search
        countries: Dictionary of country codes and names
        max_pages: Maximum pages to fetch per role/country combination
        delay: Delay between API calls (seconds) to avoid rate limiting
        test_mode: If True, only extract 1 role, 1 country, 1 page
    """
    config = load_config()
    
    roles = roles or config['roles']
    countries = countries or config['countries']
    max_pages = max_pages or config['api']['max_pages_per_role_country']
    delay = delay or config['api']['rate_limit_delay_seconds']
    
    if test_mode:
        roles = [roles[0]]
        countries = {list(countries.keys())[0]: list(countries.values())[0]}
        max_pages = 1
        logger.info("=== TEST MODE: 1 role, 1 country, 1 page ===")
    
    # Generate unique batch ID for this extraction run
    batch_id = str(uuid4())
    logger.info(f"Starting extraction batch: {batch_id}")
    logger.info(f"Roles: {len(roles)}, Countries: {len(countries)}, Max pages: {max_pages}")
    
    # Statistics
    total_jobs = 0
    total_inserted = 0
    start_time = datetime.now()
    
    for role in roles:
        for country_code, country_name in countries.items():
            logger.info(f"\n--- Extracting: {role} in {country_name} ({country_code}) ---")
            
            for page in range(1, max_pages + 1):
                jobs = get_jobs(role, country_code, page)
                total_jobs += len(jobs)
                
                if jobs:
                    inserted = save_to_database(jobs, role, country_code, batch_id)
                    total_inserted += inserted
                
                # If we got fewer results than expected, no more pages
                if len(jobs) < 50:
                    break
                
                # Rate limiting delay
                time.sleep(delay)
    
    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"\n{'='*50}")
    logger.info(f"EXTRACTION COMPLETE")
    logger.info(f"{'='*50}")
    logger.info(f"Batch ID: {batch_id}")
    logger.info(f"Total jobs fetched: {total_jobs}")
    logger.info(f"Total jobs inserted: {total_inserted}")
    logger.info(f"Duplicates skipped: {total_jobs - total_inserted}")
    logger.info(f"Time elapsed: {elapsed:.2f} seconds")
    logger.info(f"{'='*50}")
    
    return {
        "batch_id": batch_id,
        "total_fetched": total_jobs,
        "total_inserted": total_inserted,
        "elapsed_seconds": elapsed
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Extract job data from Adzuna API')
    parser.add_argument('--role', type=str, help='Single role to extract')
    parser.add_argument('--country', type=str, help='Single country code to extract')
    parser.add_argument('--pages', type=int, default=2, help='Max pages per role/country')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between API calls')
    parser.add_argument('--test', action='store_true', help='Test mode: 1 role, 1 country, 1 page')
    
    args = parser.parse_args()
    
    # Validate credentials
    validate_credentials()
    
    # Load config
    config = load_config()
    
    # Determine roles and countries
    roles = [args.role] if args.role else config['roles']
    countries = {args.country: config['countries'].get(args.country, args.country)} if args.country else config['countries']
    
    # Validate inputs
    if args.role and args.role not in config['roles']:
        logger.warning(f"Role '{args.role}' not in configured roles, but will proceed anyway")
    
    if args.country and args.country not in config['countries']:
        logger.warning(f"Country '{args.country}' not in configured countries, but will proceed anyway")
    
    # Run extraction
    result = extract_all(
        roles=roles,
        countries=countries,
        max_pages=args.pages,
        delay=args.delay,
        test_mode=args.test
    )
    
    return result


if __name__ == "__main__":
    main()