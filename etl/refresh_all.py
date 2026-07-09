"""
Job Script — Full Refresh Orchestrator
=======================================
Runs the entire pipeline end-to-end so the dashboard reflects the LATEST data
across ALL sources (Adzuna + the multi-source connectors), then rebuilds the
analytical marts.

Sequence:
  0. SNAPSHOT  current marts -> archive.skill_demand_history  (preserve history)
  1. EXTRACT   fresh Adzuna postings (last N days)            -> raw.jobs
  2. INGEST    multi-source connectors (Jooble, RemoteOK, ...) -> raw.jobs
  3. TRANSFORM new raw jobs -> staging.stg_jobs (+ skills)
  4. FX RATES  fetch live currency -> USD rates (staging.currency_rates)
  5. DBT       rebuild marts (staging_marts.*) with --full-refresh
  6. SNAPSHOT  again (captures the fresh state for the trend history)

Step 4 keeps salary comparisons correct: every mart groups salary by
(role, country) so it's currency-safe within a row, but the API blends rows
ACROSS countries for the "All Countries" view — without a fresh conversion
table that blend would average raw numbers in different currencies (e.g. an
INR salary of millions against a USD salary of thousands) and produce
wildly inflated "average salaries". Rates are fetched live every run, not
hardcoded, so they never go stale.

Why this order: dbt's intermediate model keeps only jobs posted in the last
60 days, so the marts MUST be rebuilt AFTER fresh data lands or they'd go
empty. The pre-run snapshot guarantees the current insights are preserved in
the archive no matter what the rebuild produces.

Usage:
    python refresh_all.py                 # full refresh
    python refresh_all.py --skip-adzuna   # only multi-source + transform + dbt
    python refresh_all.py --skip-dbt      # data only, rebuild marts yourself
    python refresh_all.py --days 90       # widen the Adzuna freshness window
    python refresh_all.py --dry-run       # print the plan, run nothing

dbt connection: DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME are derived
automatically from SUPABASE_URL, so no separate dbt env setup is needed.
"""

from __future__ import annotations

import os
import sys
import argparse
import logging
import subprocess
import urllib.parse as urlparse
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("refresh.log")],
)
logger = logging.getLogger("refresh")

ETL_DIR = Path(__file__).parent
REPO_ROOT = ETL_DIR.parent
DBT_DIR = REPO_ROOT / "dbt_project"

load_dotenv(ETL_DIR / ".env")
DB_URL = os.getenv("SUPABASE_URL")


def session_pooler_url(url: str) -> str:
    """Supabase's transaction pooler (port 6543) kills long-lived connections,
    which breaks the multi-minute transform. The session pooler (port 5432,
    same host) keeps the connection alive for the whole session. Rewrite 6543
    -> 5432 so the long-running steps don't get dropped mid-run."""
    if url and ":6543/" in url:
        return url.replace(":6543/", ":5432/")
    return url


def run_step(name: str, cmd: list, cwd: Path, env: dict = None, dry_run: bool = False) -> bool:
    """Run a subprocess step, streaming output. Returns True on success."""
    logger.info("=" * 64)
    logger.info("STEP: %s", name)
    logger.info("  $ %s   (cwd=%s)", " ".join(cmd), cwd)
    logger.info("=" * 64)
    if dry_run:
        logger.info("  [dry-run] skipped")
        return True
    result = subprocess.run(cmd, cwd=str(cwd), env=env)
    if result.returncode != 0:
        logger.error("STEP FAILED: %s (exit %d)", name, result.returncode)
        return False
    logger.info("STEP OK: %s", name)
    return True


def snapshot(label: str, dry_run: bool = False) -> None:
    """Snapshot current marts into archive.skill_demand_history (idempotent/day)."""
    logger.info("=" * 64)
    logger.info("STEP: SNAPSHOT (%s)", label)
    logger.info("=" * 64)
    if dry_run:
        logger.info("  [dry-run] skipped")
        return
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute("SELECT archive_skill_demand()")
        cur.execute("SELECT COUNT(*) FROM archive.skill_demand_history WHERE snapshot_date = CURRENT_DATE")
        logger.info("  archive rows for today: %s", cur.fetchone()[0])
    finally:
        conn.close()


def dbt_env() -> dict:
    """Build the environment dbt needs, deriving DB_* from SUPABASE_URL.

    Uses the SESSION pooler port (5432) regardless of what the URL says:
    --full-refresh runs long CREATE TABLE AS statements, and the transaction
    pooler (6543) drops long-lived connections mid-build (same failure mode
    as the transform step — see session_pooler_url). CI already builds dbt
    on 5432 for this reason."""
    env = dict(os.environ)
    u = urlparse.urlparse(session_pooler_url(DB_URL))
    env["DB_HOST"] = u.hostname or ""
    env["DB_PORT"] = str(u.port or 5432)
    env["DB_USER"] = u.username or ""
    env["DB_PASSWORD"] = urlparse.unquote(u.password or "")
    env["DB_NAME"] = (u.path or "/postgres").lstrip("/")
    return env


def main():
    parser = argparse.ArgumentParser(description="Full refresh: extract + ingest + transform + dbt")
    parser.add_argument("--days", type=int, default=60, help="Adzuna freshness window (days)")
    parser.add_argument("--pages", type=int, default=3, help="Adzuna max pages per role/country")
    parser.add_argument("--skip-adzuna", action="store_true", help="Skip the Adzuna extract step")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip the multi-source ingest step")
    parser.add_argument("--skip-transform", action="store_true", help="Skip the transform step")
    parser.add_argument("--skip-fx", action="store_true", help="Skip the currency-rate fetch step")
    parser.add_argument("--skip-dbt", action="store_true", help="Skip the dbt rebuild step")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan; run nothing")
    args = parser.parse_args()

    if not DB_URL:
        logger.error("SUPABASE_URL not set in etl/.env")
        sys.exit(1)

    py = sys.executable
    ok = True

    # 0. Preserve current insights before anything changes.
    snapshot("pre-refresh", args.dry_run)

    # 1. Fresh Adzuna postings.
    if ok and not args.skip_adzuna:
        ok = run_step(
            "Extract (Adzuna)",
            [py, "extractor.py", "--days", str(args.days), "--pages", str(args.pages), "--delay", "1.5"],
            cwd=ETL_DIR, dry_run=args.dry_run,
        )

    # 2. Multi-source connectors.
    if ok and not args.skip_ingest:
        ok = run_step(
            "Ingest (multi-source)",
            [py, "ingest_sources.py"],
            cwd=ETL_DIR, dry_run=args.dry_run,
        )

    # 3. Transform new raw jobs -> staging + skills (taxonomy fast path).
    #    Uses the session pooler (5432) so the long run isn't dropped.
    if ok and not args.skip_transform:
        transform_env = dict(os.environ)
        transform_env["SUPABASE_URL"] = session_pooler_url(DB_URL)
        ok = run_step(
            "Transform",
            [py, "transformer.py", "--batch-size", "500", "--fast-only"],
            cwd=ETL_DIR, env=transform_env, dry_run=args.dry_run,
        )

    # 4. Fetch live currency->USD rates for salary normalization.
    if ok and not args.skip_fx:
        ok = run_step(
            "Fetch currency rates",
            [py, "fetch_currency_rates.py"],
            cwd=ETL_DIR, dry_run=args.dry_run,
        )

    # 5. Rebuild marts. target=dev -> schema 'staging' + model 'marts' config
    #    => staging_marts.* (exactly what the API reads).
    if ok and not args.skip_dbt:
        ok = run_step(
            "dbt (rebuild marts)",
            ["dbt", "run", "--profiles-dir", ".", "--target", "dev", "--full-refresh"],
            cwd=DBT_DIR, env=dbt_env(), dry_run=args.dry_run,
        )

    # 6. Snapshot the fresh state too (starts the next trend point).
    #    archive_skill_demand() REPLACES any same-day snapshot (migration 005),
    #    so this post-refresh call supersedes the pre-refresh one taken in
    #    step 0 and today's archived trend point reflects the FRESH marts.
    #    (Before 005 the function was once-per-day, which silently made this
    #    call a no-op and archived stale pre-refresh data instead.)
    if ok:
        snapshot("post-refresh", args.dry_run)

    logger.info("=" * 64)
    logger.info("REFRESH %s", "COMPLETE" if ok else "FAILED — see refresh.log")
    logger.info("=" * 64)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
