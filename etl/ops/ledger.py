"""
Pipeline run ledger: one row per pipeline step in ops.pipeline_runs.

Writing to the ledger must never break the pipeline. When the database is
unreachable (often the very failure being reported), record() logs a
warning and returns False, and fetch_run() returns [].
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


def current_run_id(env=os.environ) -> str:
    if env.get("PIPELINE_RUN_ID"):
        return env["PIPELINE_RUN_ID"]
    if env.get("GITHUB_RUN_ID"):
        return f"gh-{env['GITHUB_RUN_ID']}-{env.get('GITHUB_RUN_ATTEMPT', '1')}"
    return "local-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def record(url, *, run_id, step, status, started_at, finished_at,
           exit_code=None, rows_out=None, error=None, details=None) -> bool:
    try:
        conn = psycopg2.connect(url, connect_timeout=10)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ops.pipeline_runs
                       (run_id, step, status, exit_code, rows_out, started_at, finished_at, error, details)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (run_id, step, status, exit_code, rows_out, started_at, finished_at,
                     error, json.dumps(details or {})),
                )
        finally:
            conn.close()
        return True
    except Exception as exc:  # the ledger is best-effort by design
        logger.warning("ledger: could not record step %s (%s)", step, exc.__class__.__name__)
        return False


def fetch_run(url, run_id) -> list[dict]:
    try:
        conn = psycopg2.connect(url, connect_timeout=10)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT step, status, exit_code, rows_out, error, details
                       FROM ops.pipeline_runs WHERE run_id = %s ORDER BY started_at, id""",
                    (run_id,),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("ledger: could not read run %s (%s)", run_id, exc.__class__.__name__)
        return []
