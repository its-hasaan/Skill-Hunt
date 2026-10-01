"""
Re-apply roles and skills to jobs already in staging.

Run after any taxonomy or role-rule change (first used for Phase 1a):
  1. Roles: for keyword-searched sources the TITLE decides the role. Jobs
     are retagged, or dropped when the title matches no tracked role (their
     raw row gets skip_reason='role_mismatch' so the transformer skips it).
  2. dim_skills: upsert every taxonomy skill (category, subcategory, aliases).
  3. Skills: re-extract every job's skills from title + description with
     the current shared matcher, replacing the stored rows.
  4. Delete dim_skills rows the taxonomy no longer has (now unreferenced).
Idempotent. The marts pick the changes up on the next dbt build.

    python -m ops.reextract --dry-run
    python -m ops.reextract --apply [--max-drop-pct 25]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from ops.dbconfig import load_local_env, session_pooler_url

ETL_DIR = Path(__file__).resolve().parents[1]
if str(ETL_DIR) not in sys.path:
    sys.path.insert(0, str(ETL_DIR))
from connectors.utils import RoleMatcher  # noqa: E402
from skill_extractor.fast_path import FastPathExtractor  # noqa: E402

TAXONOMY_PATH = ETL_DIR / "config" / "skills_taxonomy.json"
CONFIG_PATH = ETL_DIR / "config" / "extraction_config.json"
# Mirrors transformer.KEYWORD_SOURCES; not imported because importing the
# transformer loads .env and opens its log file.
KEYWORD_SOURCES = {"adzuna", "jooble"}
BATCH = 2000


def load_matcher() -> RoleMatcher:
    return RoleMatcher(json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["roles"])


def load_taxonomy() -> list[dict]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))["skills"]


def _classify(conn, matcher):
    with conn.cursor() as cur:
        cur.execute("SELECT job_id, raw_job_id, source, search_role, title FROM staging.stg_jobs")
        rows = cur.fetchall()
    conn.rollback()
    retag, drop, keep = [], [], 0
    for job_id, raw_job_id, source, role, title in rows:
        if source not in KEYWORD_SOURCES:
            keep += 1
            continue
        new_role = matcher.match(title or "")
        if new_role is None:
            drop.append((job_id, raw_job_id))
        elif new_role != role:
            retag.append((job_id, new_role))
        else:
            keep += 1
    return len(rows), keep, retag, drop


def plan(conn, matcher) -> dict:
    total, keep, retag, drop = _classify(conn, matcher)
    return {"total": total, "keep": keep, "retag": len(retag), "drop": len(drop)}


def apply_roles(conn, matcher) -> dict:
    total, keep, retag, drop = _classify(conn, matcher)
    with conn, conn.cursor() as cur:
        if retag:
            execute_values(cur, """UPDATE staging.stg_jobs s SET search_role = v.role
                                   FROM (VALUES %s) AS v(job_id, role) WHERE s.job_id = v.job_id""",
                           retag, page_size=5000)
        if drop:
            cur.execute("UPDATE raw.jobs SET skip_reason = 'role_mismatch' WHERE id = ANY(%s)",
                        ([raw_id for _, raw_id in drop if raw_id is not None],))
            cur.execute("DELETE FROM staging.stg_jobs WHERE job_id = ANY(%s)", ([j for j, _ in drop],))
    return {"total": total, "keep": keep, "retag": len(retag), "drop": len(drop)}


def sync_dim_skills(conn, taxonomy: list[dict]) -> dict:
    rows = [(s["name"], s.get("category"), s.get("subcategory") or (s.get("category") or "").lower(),
             s.get("aliases", [])) for s in taxonomy]
    with conn, conn.cursor() as cur:
        execute_values(cur, """INSERT INTO staging.dim_skills (skill_name, skill_category, skill_subcategory, aliases)
                               VALUES %s
                               ON CONFLICT (skill_name) DO UPDATE SET
                                   skill_category = EXCLUDED.skill_category,
                                   skill_subcategory = EXCLUDED.skill_subcategory,
                                   aliases = EXCLUDED.aliases,
                                   updated_at = now()""", rows, page_size=1000)
    return {"upserted": len(rows)}


def delete_stale_skills(conn, taxonomy: list[dict]) -> int:
    with conn, conn.cursor() as cur:
        cur.execute("""DELETE FROM staging.dim_skills d
                       WHERE NOT (d.skill_name = ANY(%s))
                         AND NOT EXISTS (SELECT 1 FROM staging.stg_job_skills k WHERE k.skill_id = d.skill_id)""",
                    ([s["name"] for s in taxonomy],))
        return cur.rowcount


def reextract_skills(conn, taxonomy: list[dict], batch: int = BATCH) -> dict:
    extractor = FastPathExtractor(taxonomy_data={"skills": taxonomy})
    with conn.cursor() as cur:
        cur.execute("SELECT skill_name, skill_id FROM staging.dim_skills")
        skill_ids = dict(cur.fetchall())
    conn.rollback()
    last_id, jobs, skill_rows = 0, 0, 0
    while True:
        with conn.cursor() as cur:
            cur.execute("""SELECT job_id, COALESCE(title, ''), COALESCE(description, '')
                           FROM staging.stg_jobs WHERE job_id > %s ORDER BY job_id LIMIT %s""", (last_id, batch))
            chunk = cur.fetchall()
        if not chunk:
            conn.rollback()
            break
        rows = []
        for job_id, title, description in chunk:
            for skill in extractor.extract_skills(f"{title} {description}"):
                sid = skill_ids.get(skill["skill_name"])
                if sid is not None:
                    rows.append((job_id, sid, skill["skill_name"], skill["mention_count"]))
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM staging.stg_job_skills WHERE job_id = ANY(%s)", ([c[0] for c in chunk],))
            if rows:
                execute_values(cur, """INSERT INTO staging.stg_job_skills (job_id, skill_id, skill_name, mention_count)
                                       VALUES %s""", rows, page_size=5000)
        jobs += len(chunk)
        skill_rows += len(rows)
        last_id = chunk[-1][0]
        print(f"  re-extracted {jobs} jobs ({skill_rows} skill rows)", flush=True)
    return {"jobs": jobs, "skill_rows": skill_rows}


def apply(conn, matcher, taxonomy: list[dict]) -> dict:
    roles = apply_roles(conn, matcher)
    sync_dim_skills(conn, taxonomy)
    skills = reextract_skills(conn, taxonomy)
    stale = delete_stale_skills(conn, taxonomy)
    return {**roles, **skills, "stale_skills_deleted": stale}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Re-apply roles and skills to staging")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--max-drop-pct", type=float, default=25.0)
    args = parser.parse_args(argv)

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    matcher = load_matcher()
    conn = psycopg2.connect(url)
    try:
        counts = plan(conn, matcher)
        drop_pct = 100.0 * counts["drop"] / counts["total"] if counts["total"] else 0.0
        print(f"roles: {counts} (drop {drop_pct:.1f}%)")
        if args.dry_run:
            return 0
        if drop_pct > args.max_drop_pct:
            print(f"Refusing: {drop_pct:.1f}% of jobs would be dropped (limit {args.max_drop_pct}%).")
            return 1
        print(f"applied: {apply(conn, matcher, load_taxonomy())}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
