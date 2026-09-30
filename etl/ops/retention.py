"""
Storage retention for the Supabase free tier (500 MB).

1. Once a job is processed and STRIP_AFTER_DAYS old, drop its source
   payload: connector envelopes lose `_raw` (keeping `_source` and
   `_normalized`), and Adzuna's native payload becomes {"_stripped": true}.
   stg_jobs already holds the cleaned copy. (Cost: transformer --reprocess
   can no longer rebuild stripped rows from raw.)
2. Delete jobs older than RETENTION_DAYS (by posting date) from staging and
   raw, plus old raw rows that never transformed. 400 days keeps a full
   year for the skill-trend chart, which is computed from stg_jobs.
3. VACUUM so freed space is reused (VACUUM FULL returns it; run weekly).

    python -m ops.retention --dry-run
    python -m ops.retention [--vacuum-full] [--max-delete N]

Known Phase-0 limitation: a feed that keeps listing a job posted >400 days
ago re-ingests it daily (the raw row is gone). Phase 1's job lifecycle
(first/last seen) replaces this rule.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import psycopg2

from ops.dbconfig import load_local_env, session_pooler_url

RETENTION_DAYS = 400
STRIP_AFTER_DAYS = 7
MAX_DELETE = 100_000

# Strippable: an envelope still carrying `_raw`, or a native (Adzuna)
# payload that is neither an envelope nor already a stub.
STRIP_WHERE = """(r.raw_data ? '_raw' OR NOT (r.raw_data ? '_source' OR r.raw_data ? '_stripped'))
    AND r.extracted_at < now() - make_interval(days => %(strip_days)s)
    AND EXISTS (SELECT 1 FROM staging.stg_jobs s WHERE s.raw_job_id = r.id)"""
EXPIRED_WHERE = "COALESCE(s.job_posted_at, s.extracted_at) < now() - make_interval(days => %(days)s)"
ORPHAN_WHERE = """r.extracted_at < now() - make_interval(days => %(days)s)
    AND NOT EXISTS (SELECT 1 FROM staging.stg_jobs s WHERE s.raw_job_id = r.id)"""


@dataclass
class RetentionResult:
    stripped: int
    deleted_stg: int
    deleted_raw: int


class RetentionLimitExceeded(RuntimeError):
    pass


def count_candidates(conn, days: int, strip_days: int) -> dict:
    params = {"days": days, "strip_days": strip_days}
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM raw.jobs r WHERE {STRIP_WHERE}", params)
        strip = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM staging.stg_jobs s WHERE {EXPIRED_WHERE}", params)
        expired = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM raw.jobs r WHERE {ORPHAN_WHERE}", params)
        orphans = cur.fetchone()[0]
    conn.rollback()
    return {"strip": strip, "expired_jobs": expired, "orphan_raw": orphans}


def apply(conn, days: int = RETENTION_DAYS, strip_days: int = STRIP_AFTER_DAYS,
          max_delete: int = MAX_DELETE) -> RetentionResult:
    """All changes in one transaction: either everything or nothing."""
    params = {"days": days, "strip_days": strip_days}
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM staging.stg_jobs s WHERE {EXPIRED_WHERE}", params)
            expired = cur.fetchone()[0]
            if expired > max_delete:
                raise RetentionLimitExceeded(
                    f"{expired} expired jobs exceeds --max-delete {max_delete}; "
                    "check the counts with --dry-run, then rerun with a higher limit."
                )
            cur.execute(f"""UPDATE raw.jobs r SET raw_data = CASE
                                WHEN r.raw_data ? '_source' THEN r.raw_data - '_raw'
                                ELSE '{{"_stripped": true}}'::jsonb END
                            WHERE {STRIP_WHERE}""", params)
            stripped = cur.rowcount
            cur.execute(f"""CREATE TEMP TABLE expired_jobs ON COMMIT DROP AS
                            SELECT s.job_id, s.raw_job_id FROM staging.stg_jobs s WHERE {EXPIRED_WHERE}""", params)
            cur.execute("DELETE FROM staging.stg_jobs s USING expired_jobs e WHERE s.job_id = e.job_id")
            deleted_stg = cur.rowcount
            cur.execute("DELETE FROM raw.jobs r USING expired_jobs e WHERE r.id = e.raw_job_id")
            deleted_raw = cur.rowcount
            cur.execute(f"DELETE FROM raw.jobs r WHERE {ORPHAN_WHERE}", params)
            deleted_raw += cur.rowcount
    return RetentionResult(stripped, deleted_stg, deleted_raw)


def vacuum(url: str, full: bool) -> None:
    conn = psycopg2.connect(url)
    conn.autocommit = True  # VACUUM cannot run inside a transaction
    try:
        with conn.cursor() as cur:
            options = "FULL, ANALYZE" if full else "ANALYZE"
            cur.execute(f"VACUUM ({options}) raw.jobs, staging.stg_jobs, staging.stg_job_skills")
    finally:
        conn.close()


def db_size_mb(conn) -> float:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database())")
        size = cur.fetchone()[0]
    conn.rollback()
    return round(size / 1024 / 1024, 1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Apply storage retention")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--vacuum-full", action="store_true")
    parser.add_argument("--days", type=int, default=RETENTION_DAYS)
    parser.add_argument("--max-delete", type=int, default=MAX_DELETE)
    args = parser.parse_args(argv)

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    conn = psycopg2.connect(url)
    try:
        if args.dry_run:
            print(f"would change: {count_candidates(conn, args.days, STRIP_AFTER_DAYS)}")
            print(f"db size: {db_size_mb(conn)} MB")
            return 0
        try:
            result = apply(conn, args.days, STRIP_AFTER_DAYS, args.max_delete)
        except RetentionLimitExceeded as exc:
            print(f"Retention refused: {exc}", file=sys.stderr)
            return 1
        print(f"stripped payloads: {result.stripped}, deleted jobs: {result.deleted_stg}, "
              f"deleted raw rows: {result.deleted_raw}")
    finally:
        conn.close()
    vacuum(url, full=args.vacuum_full)
    conn = psycopg2.connect(url)
    try:
        print(f"db size: {db_size_mb(conn)} MB")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
