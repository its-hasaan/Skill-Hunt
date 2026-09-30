"""
Run one pipeline step as a subprocess and record it in the ledger.

    python -m ops.run_step --step ingest --metric raw_inserted_other -- python ingest_sources.py

Output streams live; the last lines are kept so a failure's cause reaches
the ledger (and the alert email). The child's exit code is returned
unchanged, so CI still sees the real result.
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import subprocess
import sys
import urllib.parse as urlparse
from datetime import datetime, timezone

import psycopg2

from ops import ledger
from ops.dbconfig import load_local_env, session_pooler_url

TAIL_LINES = 40

# Each metric is evaluated after the step; %(since)s is the DB clock when
# the step started (DB time, so runner clock skew doesn't matter).
METRICS = {
    "raw_inserted": "SELECT count(*) FROM raw.jobs WHERE extracted_at >= %(since)s",
    "raw_inserted_adzuna": "SELECT count(*) FROM raw.jobs WHERE extracted_at >= %(since)s AND source = 'adzuna'",
    "raw_inserted_other": "SELECT count(*) FROM raw.jobs WHERE extracted_at >= %(since)s AND source <> 'adzuna'",
    "stg_processed": "SELECT count(*) FROM staging.stg_jobs WHERE processed_at >= %(since)s",
    "db_size_bytes": "SELECT pg_database_size(current_database())",
}


# Env vars whose values must never reach the ledger or the alert email.
# GitHub masks secrets in its own log, but not in output we capture:
# Adzuna, for one, puts app_key in request URLs that end up in tracebacks.
SECRET_NAME = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|_URL|APP_ID)$")
MIN_SECRET_LEN = 6


def redact(text: str, env=os.environ) -> str:
    secrets = {v for k, v in env.items() if SECRET_NAME.search(k) and v and len(v) >= MIN_SECRET_LEN}
    db_url = env.get("SUPABASE_URL")
    if db_url:
        encoded = urlparse.urlparse(db_url).password or ""
        secrets |= {pw for pw in (encoded, urlparse.unquote(encoded)) if len(pw) >= MIN_SECRET_LEN}
    for secret in sorted(secrets, key=len, reverse=True):  # whole URL before its password
        text = text.replace(secret, "***")
    return text


def _query_one(url, sql, params=None):
    try:
        conn = psycopg2.connect(url, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return None


def _run(cmd) -> tuple[int, str]:
    tail = collections.deque(maxlen=TAIL_LINES)
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        tail.append(line.rstrip("\n"))
    return proc.wait(), "\n".join(tail)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run a pipeline step and record it")
    parser.add_argument("--step", required=True)
    parser.add_argument("--metric", choices=sorted(METRICS))
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        parser.error("missing command after --")

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    since = _query_one(url, "SELECT now()") if (url and args.metric) else None
    started = datetime.now(timezone.utc)
    exit_code, tail = _run(cmd)
    finished = datetime.now(timezone.utc)

    if url:
        value = _query_one(url, METRICS[args.metric], {"since": since}) if since is not None else None
        ledger.record(
            url, run_id=ledger.current_run_id(), step=args.step,
            status="success" if exit_code == 0 else "failure",
            started_at=started, finished_at=finished, exit_code=exit_code,
            rows_out=value, error=None if exit_code == 0 else redact(tail),
            details={"metric": args.metric} if args.metric else None,
        )
    return exit_code


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
