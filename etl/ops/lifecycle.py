"""
Job lifecycle on raw.jobs: record every sighting, close jobs that stop
appearing.

- save_jobs():  upsert; a new job is inserted, a known one gets
                last_seen_at = now() and is re-opened if it had closed.
- close_unseen(): for sources that return a company's FULL list of open
                jobs (company job boards), a job missing from a board that
                was fetched successfully is closed. Boards that failed this
                run are never passed in, so an outage closes nothing.
- age_out_feed_jobs(): feed/search sources only show a slice of jobs, so
                they close after N days without a sighting.
"""
from __future__ import annotations

from psycopg2.extras import execute_values

UPSERT_SQL = """
    INSERT INTO raw.jobs (job_platform_id, search_role, country_code, raw_data, extraction_batch_id, source)
    VALUES %s
    ON CONFLICT (job_platform_id, country_code) DO UPDATE
        SET last_seen_at = now(), closed_at = NULL
    RETURNING (xmax = 0) AS inserted
"""


def save_jobs(conn, rows: list[tuple]) -> tuple[int, int]:
    """rows: (job_platform_id, search_role, country_code, raw_json, batch_id, source).
    Returns (inserted, seen)."""
    if not rows:
        return 0, 0
    # One upsert may not touch the same row twice, and feeds sometimes list a
    # job twice in one fetch: keep the last occurrence of each key.
    rows = list({(r[0], r[2]): r for r in rows}.values())
    with conn, conn.cursor() as cur:
        results = execute_values(cur, UPSERT_SQL, rows, page_size=max(1, len(rows)), fetch=True)
    inserted = sum(1 for (is_new,) in results if is_new)
    return inserted, len(rows)


def close_unseen(conn, source: str, boards: list[str], since) -> int:
    if not boards:
        return 0
    with conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE raw.jobs SET closed_at = now()
               WHERE source = %s AND split_part(job_platform_id, ':', 2) = ANY(%s)
                 AND last_seen_at < %s AND closed_at IS NULL""",
            (source, list(boards), since),
        )
        return cur.rowcount


def age_out_feed_jobs(conn, days: int = 14, exclude_sources: set[str] = frozenset()) -> int:
    with conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE raw.jobs SET closed_at = now()
               WHERE closed_at IS NULL
                 AND last_seen_at < now() - make_interval(days => %s)
                 AND NOT (source = ANY(%s))""",
            (days, list(exclude_sources)),
        )
        return cur.rowcount


def touch_board(conn, source: str, board: str) -> int:
    """A board whose listing page is unchanged (HTTP 304) still lists the same
    jobs: record a sighting for its open jobs without re-reading them."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE raw.jobs SET last_seen_at = now()
               WHERE source = %s AND split_part(job_platform_id, ':', 2) = %s AND closed_at IS NULL""",
            (source, board),
        )
        return cur.rowcount
