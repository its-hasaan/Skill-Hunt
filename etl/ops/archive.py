"""Snapshot today's skill demand into archive.skill_demand_history.

archive_skill_demand() replaces a same-day snapshot (migration 005), so
running it after every successful mart rebuild keeps today's point fresh.
"""
import os
import sys

import psycopg2

from ops.dbconfig import load_local_env, session_pooler_url


def archive(url: str) -> None:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT archive_skill_demand()")
    finally:
        conn.close()


def main() -> int:
    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    archive(url)
    print("Archived today's skill-demand snapshot")
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
