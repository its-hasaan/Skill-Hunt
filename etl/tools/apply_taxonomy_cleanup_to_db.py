"""
Apply the taxonomy cleanup (REMOVE / MERGE / RENAME) to the LIVE database.

`clean_taxonomy.py` fixes the taxonomy JSON (so future extraction is clean).
This script applies the SAME rules — imported from clean_taxonomy, so there's
a single source of truth — to the already-extracted data in
`staging.dim_skills` + `staging.stg_job_skills`, so the current dashboard is
fixed WITHOUT a full re-extraction:

  REMOVE  -> delete the skill's stg_job_skills rows, then its dim_skills row
  MERGE   -> repoint each variant's stg_job_skills to the canonical skill
             (dedup per job), delete leftover variant rows + the variant's
             dim_skills row (canonical's count absorbs the variant's jobs)
  RENAME  -> rename the dim_skills row (+ denormalized stg_job_skills.skill_name)

After running, rebuild the marts:  cd dbt_project && dbt run --profiles-dir . --target dev --full-refresh
(or just run `python etl/refresh_all.py --skip-adzuna --skip-ingest --skip-transform`).

Usage:
    python etl/tools/apply_taxonomy_cleanup_to_db.py            # apply
    python etl/tools/apply_taxonomy_cleanup_to_db.py --dry-run  # report only
"""

import os
import sys
import argparse
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_taxonomy import REMOVE, MERGE, RENAME  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
DB_URL = os.getenv("SUPABASE_URL")


def name_to_id(cur) -> dict:
    cur.execute("SELECT skill_name, skill_id FROM staging.dim_skills")
    return {n: i for n, i in cur.fetchall()}


def jobs_for_skill(cur, skill_id: int) -> int:
    cur.execute("SELECT COUNT(*) FROM staging.stg_job_skills WHERE skill_id = %s", (skill_id,))
    return cur.fetchone()[0]


def fold_into(cur, src_id: int, canon_id: int, canon_name: str):
    """Repoint src's job-skill rows to the canonical skill (dedup per job),
    drop leftovers, and delete the src dim_skills row. Returns (reassigned,
    deleted) row counts."""
    cur.execute(
        """
        UPDATE staging.stg_job_skills js
        SET skill_id = %s, skill_name = %s
        WHERE js.skill_id = %s
          AND NOT EXISTS (
            SELECT 1 FROM staging.stg_job_skills j2
            WHERE j2.job_id = js.job_id AND j2.skill_id = %s)
        """,
        (canon_id, canon_name, src_id, canon_id),
    )
    reassigned = cur.rowcount
    cur.execute("DELETE FROM staging.stg_job_skills WHERE skill_id = %s", (src_id,))
    deleted = cur.rowcount
    cur.execute("DELETE FROM staging.dim_skills WHERE skill_id = %s", (src_id,))
    return reassigned, deleted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Report the plan; change nothing")
    args = ap.parse_args()

    if not DB_URL:
        print("SUPABASE_URL not set"); sys.exit(1)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    ids = name_to_id(cur)

    removed_skills = merged_pairs = renamed = 0
    reassigned_rows = deleted_rows = 0

    # ---- REMOVE ---------------------------------------------------------
    remove_present = [n for n in REMOVE if n in ids]
    for name in remove_present:
        sid = ids[name]
        n = jobs_for_skill(cur, sid)
        print(f"REMOVE  {name!r} (skill_id={sid}, {n} job-skill rows)")
        if not args.dry_run:
            cur.execute("DELETE FROM staging.stg_job_skills WHERE skill_id = %s", (sid,))
            deleted_rows += cur.rowcount
            cur.execute("DELETE FROM staging.dim_skills WHERE skill_id = %s", (sid,))
        removed_skills += 1

    # ---- MERGE (variant -> canonical) -----------------------------------
    for canon, variants in MERGE.items():
        canon_id = ids.get(canon)
        for variant in variants:
            var_id = ids.get(variant)
            if var_id is None:
                continue  # variant never made it into the DB — nothing to do
            if canon_id is None:
                # Canonical row doesn't exist yet: promote this variant to it.
                print(f"MERGE   {variant!r} -> {canon!r} (rename; canonical absent)")
                if not args.dry_run:
                    cur.execute(
                        "UPDATE staging.dim_skills SET skill_name = %s WHERE skill_id = %s",
                        (canon, var_id),
                    )
                    cur.execute(
                        "UPDATE staging.stg_job_skills SET skill_name = %s WHERE skill_id = %s",
                        (canon, var_id),
                    )
                canon_id = var_id
                ids[canon] = canon_id
                merged_pairs += 1
                continue

            before = jobs_for_skill(cur, var_id)
            print(f"MERGE   {variant!r} (id={var_id}, {before} rows) -> {canon!r} (id={canon_id})")
            if not args.dry_run:
                r, d = fold_into(cur, var_id, canon_id, canon)
                reassigned_rows += r
                deleted_rows += d
            merged_pairs += 1

    # ---- RENAME ---------------------------------------------------------
    # Refresh the name->id map (MERGE deleted variant rows).
    if not args.dry_run:
        ids = name_to_id(cur)
    for src, dst in RENAME.items():
        sid = ids.get(src)
        if sid is None:
            continue
        dst_id = ids.get(dst)
        if dst_id is not None and dst_id != sid:
            # Target name already exists -> fold source into it (a rename would
            # violate the unique skill_name constraint).
            print(f"RENAME  {src!r} -> {dst!r} (target exists; folding in)")
            if not args.dry_run:
                r, d = fold_into(cur, sid, dst_id, dst)
                reassigned_rows += r
                deleted_rows += d
        else:
            print(f"RENAME  {src!r} -> {dst!r}")
            if not args.dry_run:
                cur.execute("UPDATE staging.dim_skills SET skill_name = %s WHERE skill_id = %s", (dst, sid))
                cur.execute("UPDATE staging.stg_job_skills SET skill_name = %s WHERE skill_id = %s", (dst, sid))
        renamed += 1

    if args.dry_run:
        conn.rollback()
        print("\n[dry-run] no changes committed")
    else:
        conn.commit()
        print(f"\nCOMMITTED: removed {removed_skills} skills, merged {merged_pairs} variants, "
              f"renamed {renamed}; reassigned {reassigned_rows} rows, deleted {deleted_rows} rows.")
        print("NEXT: rebuild marts -> cd dbt_project && dbt run --profiles-dir . --target dev --full-refresh")
    conn.close()


if __name__ == "__main__":
    main()
