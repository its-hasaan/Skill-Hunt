"""
Registry of company job boards on hiring-system APIs (ops.companies).

    python -m ops.companies seed                 # add etl/config/ats_seed_companies.json
    python -m ops.companies validate [--ats X] [--limit N]

A board is a candidate (active NULL) until a probe succeeds; three
consecutive failed probes mark it inactive so dead or renamed boards stop
costing requests. Connectors only read active boards.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable, Optional

import psycopg2

from ops.dbconfig import load_local_env, session_pooler_url

ETL_DIR = Path(__file__).resolve().parents[1]
if str(ETL_DIR) not in sys.path:
    sys.path.insert(0, str(ETL_DIR))
from connectors.ats_endpoints import ATS_SYSTEMS, job_items, probe_url  # noqa: E402

SEED_PATH = ETL_DIR / "config" / "ats_seed_companies.json"
MAX_FAILS = 3

Probe = Callable[[str, str], Optional[int]]


def upsert_candidates(conn, ats: str, tokens, via: str) -> int:
    tokens = sorted({t for t in tokens if t})
    if not tokens:
        return 0
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ops.companies (ats, board_token, discovered_via)
               SELECT %s, t, %s FROM unnest(%s::text[]) AS t
               ON CONFLICT (ats, board_token) DO NOTHING
               RETURNING 1""",
            (ats, via, tokens),
        )
        return len(cur.fetchall())


def record_check(conn, ats: str, token: str, ok: bool, job_count: Optional[int] = None) -> None:
    with conn, conn.cursor() as cur:
        if ok:
            cur.execute(
                """UPDATE ops.companies SET active = TRUE, fail_count = 0,
                          last_checked_at = now(), last_job_count = %s
                   WHERE ats = %s AND board_token = %s""",
                (job_count, ats, token),
            )
        else:
            cur.execute(
                """UPDATE ops.companies SET fail_count = fail_count + 1, last_checked_at = now(),
                          active = CASE WHEN fail_count + 1 >= %s THEN FALSE ELSE active END
                   WHERE ats = %s AND board_token = %s""",
                (MAX_FAILS, ats, token),
            )


def active_boards(conn, ats: str) -> list[str]:
    with conn.cursor() as cur:
        # Least recently fetched first: with max_boards per run, the connectors
        # rotate through every board instead of re-reading the same ones.
        cur.execute("""SELECT board_token FROM ops.companies WHERE ats = %s AND active
                       ORDER BY last_checked_at NULLS FIRST, board_token""", (ats,))
        boards = [r[0] for r in cur.fetchall()]
    conn.rollback()
    return boards


def validate(conn, probe: Probe, ats: Optional[str] = None, limit: Optional[int] = None) -> dict:
    """Probe candidate and active boards (least recently checked first)."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT ats, board_token FROM ops.companies
               WHERE active IS NOT FALSE AND (%s::text IS NULL OR ats = %s)
               ORDER BY last_checked_at NULLS FIRST, id
               LIMIT %s""",
            (ats, ats, limit),
        )
        boards = cur.fetchall()
    conn.rollback()
    result = {"checked": 0, "active": 0, "failed": 0}
    for board_ats, token in boards:
        count = probe(board_ats, token)
        record_check(conn, board_ats, token, ok=count is not None, job_count=count)
        result["checked"] += 1
        result["active" if count is not None else "failed"] += 1
    return result


def interpret(ats: str, status: int, payload) -> Optional[int]:
    """Job count from a list-endpoint response, or None if the board doesn't
    exist. SmartRecruiters answers unknown companies with 200 + an empty list,
    so there an empty board is indistinguishable from a missing one."""
    if status != 200:
        return None
    items = job_items(ats, payload)
    if items is None:
        return None
    if ats == "smartrecruiters" and not items:
        return None
    return len(items)


def http_probe(session=None) -> Probe:
    """Real probe: one request to the board's list endpoint; job count or None."""
    import requests
    from connectors.base import build_session

    session = session or build_session(timeout=20, total_retries=1)

    def probe(ats: str, token: str) -> Optional[int]:
        try:
            resp = session.get(probe_url(ats, token), timeout=20)
            payload = resp.json() if resp.status_code == 200 else None
            return interpret(ats, resp.status_code, payload)
        except (requests.RequestException, ValueError):
            return None

    return probe


def seed(conn, path: Path = SEED_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {ats: upsert_candidates(conn, ats, data.get(ats, []), "seed") for ats in ATS_SYSTEMS}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Manage the company job-board registry")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    val = sub.add_parser("validate")
    val.add_argument("--ats", choices=ATS_SYSTEMS)
    val.add_argument("--limit", type=int)
    args = parser.parse_args(argv)

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    conn = psycopg2.connect(url)
    try:
        if args.command == "seed":
            print(f"seeded (new boards per system): {seed(conn)}")
        else:
            print(f"validated: {validate(conn, http_probe(), args.ats, args.limit)}")
            with conn.cursor() as cur:
                cur.execute("SELECT ats, count(*) FILTER (WHERE active), count(*) FROM ops.companies GROUP BY ats ORDER BY ats")
                for ats, live, total in cur.fetchall():
                    print(f"  {ats:16} {live} active / {total} known")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
