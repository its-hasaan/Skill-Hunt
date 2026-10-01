"""
Job Script — Multi-Source Ingestion Orchestrator
=================================================
Runs every enabled connector (RemoteOK, WeWorkRemotely, Arbeitnow, Jobicy,
Himalayas, Jooble, The Muse, USAJobs, ...) and lands their jobs in `raw.jobs`
using the SAME contract as the Adzuna extractor, tagged with a `source`.

From there the existing pipeline takes over unchanged:
    raw.jobs -> transformer.py -> staging.* -> dbt -> marts.* -> API -> UI

Usage:
    python ingest_sources.py                      # all enabled sources
    python ingest_sources.py --source remoteok    # a single source
    python ingest_sources.py --source jooble       #   (keyed source)
    python ingest_sources.py --test               # tiny run, no-key sources
    python ingest_sources.py --dry-run            # fetch + print, no DB write

Then transform + rebuild marts as usual:
    python transformer.py --batch-size 500 --fast-only
    (dbt run happens in CI, or run it locally)
"""

from __future__ import annotations

import os
import sys
import json
import argparse
import logging
from uuid import uuid4
from pathlib import Path
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Make `from connectors import ...` work when run from etl/ or repo root.
sys.path.insert(0, str(Path(__file__).parent))
from connectors import CONNECTOR_REGISTRY  # noqa: E402
from connectors.utils import RoleMatcher  # noqa: E402
from ops import lifecycle  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("ingestion.log")],
)
logger = logging.getLogger("ingest")

load_dotenv()

DB_URL = os.getenv("SUPABASE_URL")
CONFIG_DIR = Path(__file__).parent / "config"
SOURCES_CONFIG_PATH = CONFIG_DIR / "sources_config.json"
# Sources that return a company's full open-job list (closed by absence);
# every other source is closed after FEED_STALE_DAYS without a sighting.
ATS_SOURCES = {"greenhouse", "lever", "ashby", "smartrecruiters"}
FEED_STALE_DAYS = 14


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_roles(sources_config: dict) -> list:
    roles_from = sources_config.get("roles_from", "extraction_config.json")
    path = CONFIG_DIR / roles_from
    try:
        return load_json(path).get("roles", [])
    except FileNotFoundError:
        logger.error("Roles config not found: %s", path)
        return []


def save_to_database(records: list, source: str, batch_id: str) -> int:
    """Upsert normalized jobs into raw.jobs and record the sighting.

    New jobs are inserted; jobs already known get last_seen_at = now() (and
    are re-opened if they had been closed). Returns the number of NEW jobs.
    """
    if not records:
        return 0
    rows = [
        (job.job_platform_id, job.search_role, job.country_code,
         json.dumps(job.to_raw_envelope()), batch_id, source)
        for job in records
    ]
    conn = psycopg2.connect(DB_URL)
    try:
        inserted, seen = lifecycle.save_jobs(conn, rows)
        logger.info("[%s] %d new, %d already known (sighting recorded)", source, inserted, seen - inserted)
        return inserted
    except Exception as e:  # noqa: BLE001
        logger.error("[%s] DB error: %s", source, e)
        return 0
    finally:
        conn.close()


def db_now():
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT now()")
            return cur.fetchone()[0]
    finally:
        conn.close()


def close_unseen_for(connector, source_key: str, since) -> None:
    """Company job boards return their FULL open list: jobs missing from a
    board fetched successfully this run are closed. Failed boards are not in
    seen_boards, so an outage closes nothing."""
    boards = getattr(connector, "seen_boards", None)
    if boards is None:
        return
    conn = psycopg2.connect(DB_URL)
    try:
        closed = lifecycle.close_unseen(conn, source_key, sorted(boards), since)
        logger.info("[%s] closed %d jobs no longer listed on %d fetched boards", source_key, closed, len(boards))
    finally:
        conn.close()


def build_connector(source_key: str, source_cfg: dict, roles: list, target_countries: list, role_matcher):
    connector_name = source_cfg.get("connector", source_key)
    cls = CONNECTOR_REGISTRY.get(connector_name)
    if cls is None:
        logger.warning("Unknown connector '%s' for source '%s' — skipping.", connector_name, source_key)
        return None
    # Inject shared context the keyed/search connectors need.
    cfg = dict(source_cfg)
    cfg.setdefault("roles", roles)
    cfg.setdefault("target_countries", target_countries)
    return cls(cfg, role_matcher, logging.getLogger(f"connector.{source_key}"))


def apply_test_overrides(cfg: dict) -> dict:
    """Shrink a source's config for a quick smoke test."""
    cfg = dict(cfg)
    cfg["max_jobs"] = min(int(cfg.get("max_jobs", 15)), 15)
    cfg["max_pages"] = 1
    cfg["max_records"] = 20
    cfg["pages_per_query"] = 1
    cfg["count"] = 15
    return cfg


def run(source_filter: str = None, test_mode: bool = False, dry_run: bool = False):
    if not DB_URL and not dry_run:
        logger.error("SUPABASE_URL not set. Use --dry-run to test fetching without a DB.")
        sys.exit(1)

    sources_config = load_json(SOURCES_CONFIG_PATH)
    roles = load_roles(sources_config)
    target_countries = sources_config.get("target_local_countries", ["pk", "in"])
    role_matcher = RoleMatcher(roles)

    if not roles:
        logger.error("No roles loaded — aborting.")
        sys.exit(1)

    batch_id = str(uuid4())
    logger.info("=" * 60)
    logger.info("MULTI-SOURCE INGESTION — batch %s", batch_id)
    logger.info("Roles: %d | Local countries: %s | Test: %s | Dry-run: %s",
                len(roles), target_countries, test_mode, dry_run)
    logger.info("=" * 60)

    summary = {}
    grand_fetched = grand_inserted = 0

    for source_key, source_cfg in sources_config.get("sources", {}).items():
        if source_key.startswith("_"):
            continue  # commented-out example block
        if source_filter and source_key != source_filter:
            continue
        if not source_cfg.get("enabled") and not source_filter:
            continue

        cfg = apply_test_overrides(source_cfg) if test_mode else source_cfg
        connector = build_connector(source_key, cfg, roles, target_countries, role_matcher)
        if connector is None:
            continue
        if not connector.is_available():
            summary[source_key] = "skipped (unavailable)"
            continue

        logger.info("\n--- Source: %s ---", source_key)
        source_started = db_now() if not dry_run else None
        try:
            fetched = list(connector.fetch())
        except Exception as e:  # one bad source never kills the run
            logger.exception("[%s] fetch failed: %s", source_key, e)
            summary[source_key] = f"error: {e}"
            continue

        # Drop obviously-empty jobs (no title or no link).
        fetched = [j for j in fetched if j.title and j.redirect_url]

        # Backfill posting date so nothing is lost to dbt's 60-day window.
        now_iso = datetime.now(timezone.utc).isoformat()
        for j in fetched:
            if not j.job_posted_at:
                j.job_posted_at = now_iso

        grand_fetched += len(fetched)

        if dry_run:
            logger.info("[%s] DRY-RUN — %d jobs fetched (not written).", source_key, len(fetched))
            for j in fetched[:3]:
                logger.info("    %s | %s @ %s | %s", j.search_role, j.title, j.company_name, j.country_code)
            summary[source_key] = f"{len(fetched)} fetched (dry-run)"
            continue

        inserted = save_to_database(fetched, source_key, batch_id)
        close_unseen_for(connector, source_key, source_started)
        grand_inserted += inserted
        summary[source_key] = f"{len(fetched)} fetched / {inserted} new"
        logger.info("[%s] %d fetched, %d new inserted (dupes skipped).", source_key, len(fetched), inserted)

    if not dry_run and not source_filter:
        conn = psycopg2.connect(DB_URL)
        try:
            aged = lifecycle.age_out_feed_jobs(conn, FEED_STALE_DAYS, ATS_SOURCES)
            logger.info("Closed %d feed/search jobs unseen for %d days", aged, FEED_STALE_DAYS)
        finally:
            conn.close()

    logger.info("\n%s", "=" * 60)
    logger.info("INGESTION COMPLETE — batch %s", batch_id)
    for k, v in summary.items():
        logger.info("  %-16s %s", k, v)
    logger.info("  %-16s %d fetched / %d new", "TOTAL", grand_fetched, grand_inserted)
    logger.info("=" * 60)

    return {"batch_id": batch_id, "fetched": grand_fetched, "inserted": grand_inserted, "by_source": summary}


def main():
    parser = argparse.ArgumentParser(description="Ingest jobs from multiple sources into raw.jobs")
    parser.add_argument("--source", type=str, help="Run only this source key (also forces it on)")
    parser.add_argument("--test", action="store_true", help="Tiny smoke-test run")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print; do not write to DB")
    args = parser.parse_args()
    run(source_filter=args.source, test_mode=args.test, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
