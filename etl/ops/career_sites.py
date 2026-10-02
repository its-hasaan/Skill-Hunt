"""
Registry of company career sites for the career-page crawler (ops.career_sites).

    python -m ops.career_sites seed      # add etl/config/career_sites_seed.json
    python -m ops.career_sites status    # sites per status

sites_to_crawl() picks never-crawled and JSON-LD sites first, retries
empty/blocked sites weekly, and drops sites after 3 failed crawls in a row.
Sites that embed a hiring-system board (status 'ats') are not crawled: the
board connector reads them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from ops.dbconfig import load_local_env, session_pooler_url

SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "career_sites_seed.json"
MAX_FAILS = 3

SITES_SQL = """
    SELECT domain, careers_url, status, etag, last_modified
    FROM ops.career_sites
    WHERE fail_count < %(max_fails)s
      AND (status IN ('candidate', 'jsonld')
           OR (status IN ('empty', 'blocked') AND last_crawled_at < now() - interval '7 days'))
    ORDER BY last_crawled_at NULLS FIRST, id
    LIMIT %(limit)s
"""


def seed(conn, path: Path = SEED_PATH, via: str = "seed") -> int:
    sites = json.loads(Path(path).read_text(encoding="utf-8"))["sites"]
    added = 0
    with conn, conn.cursor() as cur:
        for site in sites:
            cur.execute("""INSERT INTO ops.career_sites (domain, careers_url, discovered_via)
                           VALUES (%s, %s, %s) ON CONFLICT (domain) DO NOTHING""",
                        (site["domain"].strip().lower(), site.get("careers_url"), via))
            added += cur.rowcount
    return added


def sites_to_crawl(conn, limit: int) -> list[dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(SITES_SQL, {"max_fails": MAX_FAILS, "limit": limit})
        sites = [dict(r) for r in cur.fetchall()]
    conn.rollback()
    return sites


def record_crawl(conn, domain: str, status: Optional[str], jobs_found: Optional[int] = None,
                 etag: Optional[str] = None, last_modified: Optional[str] = None,
                 ats: Optional[str] = None, board_token: Optional[str] = None, failed: bool = False) -> None:
    with conn, conn.cursor() as cur:
        if failed:
            cur.execute("""UPDATE ops.career_sites SET fail_count = fail_count + 1, last_crawled_at = now()
                           WHERE domain = %s""", (domain,))
            return
        cur.execute(
            """UPDATE ops.career_sites SET
                   status = %s, fail_count = 0, last_crawled_at = now(),
                   jobs_found = COALESCE(%s, jobs_found), etag = COALESCE(%s, etag),
                   last_modified = COALESCE(%s, last_modified),
                   ats = COALESCE(%s, ats), board_token = COALESCE(%s, board_token)
               WHERE domain = %s""",
            (status, jobs_found, etag, last_modified, ats, board_token, domain),
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Manage the career-site registry")
    parser.add_argument("command", choices=["seed", "status"])
    args = parser.parse_args(argv)
    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    conn = psycopg2.connect(url)
    try:
        if args.command == "seed":
            print(f"seeded: {seed(conn)} new sites")
        with conn.cursor() as cur:
            cur.execute("SELECT status, count(*), sum(jobs_found) FROM ops.career_sites GROUP BY 1 ORDER BY 1")
            for status, count, jobs in cur.fetchall():
                print(f"  {status:10} {count} sites, {jobs or 0} jobs found")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
