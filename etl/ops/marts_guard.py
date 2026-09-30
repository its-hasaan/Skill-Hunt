"""
Refuse to rebuild the marts on too little fresh data.

dbt rebuilds every mart with --full-refresh over the last 60 days. If the
big weekly source (Adzuna) hasn't landed yet (the first run after an outage,
or its step failed), a rebuild would replace a full dashboard with a few
hundred jobs. This check keeps the existing marts instead and says why.

    python -m ops.marts_guard [--min-jobs 1000]
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg2

from ops.dbconfig import load_local_env, session_pooler_url

WINDOW_DAYS = 60  # must match the marts' freshness window (int_job_skills_enriched)
MIN_JOBS = 1000


def fresh_job_count(url: str, days: int = WINDOW_DAYS) -> int:
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT count(*) FROM staging.stg_jobs
                           WHERE COALESCE(job_posted_at, extracted_at) >= now() - make_interval(days => %s)""",
                        (days,))
            return cur.fetchone()[0]
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check there is enough fresh data to rebuild the marts")
    parser.add_argument("--min-jobs", type=int, default=MIN_JOBS)
    args = parser.parse_args(argv)
    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    count = fresh_job_count(url)
    print(f"{count} jobs in the last {WINDOW_DAYS} days (minimum {args.min_jobs})")
    if count < args.min_jobs:
        print("Too little fresh data; keeping the existing marts. "
              "Run the pipeline with adzuna=true to load the weekly source.")
        return 1
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
