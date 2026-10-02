"""
Duplicate removal: fingerprint staging jobs, then point every open job at
the one listing of its duplicate group that the feed shows.

    python -m ops.dedup [--recompute]

fill_fingerprints() fingerprints rows that have none (all rows with
--recompute, e.g. after the normalisation changes). assign_canonical()
ranks the OPEN jobs of each fingerprint by source priority (company board >
career page > boards/Jooble > Adzuna), then freshest sighting, then lowest
job_id, and stores the winner's job_id in canonical_job_id.
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg2
from psycopg2.extras import execute_values

from enrich.fingerprint import fingerprint
from ops.dbconfig import load_local_env, session_pooler_url

CANONICAL_SQL = """
WITH ranked AS (
    SELECT s.job_id,
           first_value(s.job_id) OVER (
               PARTITION BY s.fingerprint
               ORDER BY CASE
                            WHEN s.source IN ('greenhouse', 'lever', 'ashby', 'smartrecruiters', 'workable') THEN 1
                            WHEN s.source = 'careerpage' THEN 2
                            WHEN s.source = 'adzuna' THEN 4
                            ELSE 3
                        END,
                        r.last_seen_at DESC NULLS LAST,
                        s.job_id
           ) AS canon
    FROM staging.stg_jobs s
    JOIN raw.jobs r ON r.id = s.raw_job_id
    WHERE r.closed_at IS NULL AND s.fingerprint IS NOT NULL
)
UPDATE staging.stg_jobs s
SET canonical_job_id = ranked.canon
FROM ranked
WHERE s.job_id = ranked.job_id
  AND s.canonical_job_id IS DISTINCT FROM ranked.canon
"""


def fill_fingerprints(conn, recompute: bool = False) -> int:
    where = "" if recompute else "WHERE fingerprint IS NULL"
    with conn.cursor() as cur:
        cur.execute(f"SELECT job_id, company_name, title, location_display, location_areas "
                    f"FROM staging.stg_jobs {where}")
        rows = cur.fetchall()
    updates = [
        (job_id, fingerprint(company, title, "; ".join([display or ""] + list(areas or []))))
        for job_id, company, title, display, areas in rows
    ]
    if updates:
        with conn, conn.cursor() as cur:
            execute_values(cur, """UPDATE staging.stg_jobs s SET fingerprint = v.fp
                                   FROM (VALUES %s) AS v(job_id, fp) WHERE s.job_id = v.job_id""",
                           updates, page_size=1000)
    else:
        conn.rollback()  # close the read transaction
    return len(updates)


def assign_canonical(conn) -> int:
    with conn, conn.cursor() as cur:
        cur.execute(CANONICAL_SQL)
        return cur.rowcount


def run(conn, recompute: bool = False) -> dict:
    filled = fill_fingerprints(conn, recompute)
    changed = assign_canonical(conn)
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*), count(*) FILTER (WHERE s.canonical_job_id <> s.job_id)
                       FROM staging.stg_jobs s JOIN raw.jobs r ON r.id = s.raw_job_id
                       WHERE r.closed_at IS NULL""")
        open_jobs, duplicates = cur.fetchone()
    conn.rollback()
    return {"fingerprinted": filled, "canonical_changed": changed, "open_jobs": open_jobs,
            "open_duplicates": duplicates}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fingerprint jobs and pick canonical listings")
    parser.add_argument("--recompute", action="store_true", help="refingerprint every row")
    args = parser.parse_args(argv)
    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    conn = psycopg2.connect(url)
    try:
        print(f"dedup: {run(conn, args.recompute)}", flush=True)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
