"""
Stratified sample of feed jobs for the eligibility hand check (Phase 1 exit
criterion: >= 90% correct on 50 hand-checked jobs).

    python -m ops.eligibility_sample --n 50 --out docs/ops/eligibility-check-2026-10.md [--seed 1]

Remote jobs only (local onsite/hybrid jobs are labelled from their own
location). Strata: pk_yes (open to Pakistan), pk_no, unclear. Each job lists
its labels, the evidence they came from and the description sentences that
talk about place, so a reviewer can judge it from the posting alone and fill
in the verdict line.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

from enrich.gemini import excerpt
from ops.dbconfig import load_local_env, session_pooler_url

STRATA = {
    "pk_yes": "f.eligible_pk IS TRUE",
    "pk_no": "f.eligible_pk IS FALSE",
    "unclear": "f.eligible_pk IS NULL",
}
SHARE = {"pk_yes": 0.4, "pk_no": 0.4, "unclear": 0.2}

SAMPLE_SQL = """
    SELECT f.job_id, f.title, f.company_name, f.source, f.location_display, s.location_areas,
           f.eligible_pk, f.eligible_in, f.remote_scope, f.eligibility_confidence, f.eligibility_method,
           f.eligibility_evidence, f.apply_url, s.description
    FROM staging_marts.mart_job_feed f
    JOIN staging.stg_jobs s ON s.job_id = f.job_id
    WHERE f.workplace_type = 'remote' AND {condition}
    ORDER BY md5(f.job_id::text || %(seed)s)
    LIMIT %(limit)s
"""


def word(value) -> str:
    return {True: "yes", False: "no"}.get(value, "unclear")


def render(rows: list[dict], population: dict[str, int]) -> str:
    lines = ["# Eligibility hand check", "",
             "Each verdict judges the Pakistan and India labels against the posting text below.", "",
             "## Strata", ""]
    for stratum, size in population.items():
        sampled = sum(1 for r in rows if r["stratum"] == stratum)
        lines.append(f"- {stratum}: {sampled} sampled of {size}")
    lines += ["", "## Jobs", ""]
    for r in rows:
        locations = "; ".join(dict.fromkeys([r.get("location_display") or ""] + list(r.get("location_areas") or [])))
        lines += [
            f"### {r['job_id']}. {r['title']} — {r['company_name']} ({r['source']})",
            f"- Stratum: {r['stratum']}",
            f"- Locations: {locations}",
            f"- Labels: pk=**{word(r['eligible_pk'])}** in=**{word(r['eligible_in'])}** "
            f"scope={r['remote_scope']} confidence={r['eligibility_confidence']} method={r['eligibility_method']}",
            f"- Evidence: {r['eligibility_evidence'] or '(none)'}",
            f"- Posting (place sentences): {excerpt(r.get('description'))}",
            f"- Link: {r.get('apply_url') or ''}",
            "- Verdict: ",
            "",
        ]
    return "\n".join(lines)


def sample(conn, n: int, seed: str) -> tuple[list[dict], dict[str, int]]:
    rows, population = [], {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for stratum, condition in STRATA.items():
            cur.execute(f"SELECT count(*) AS n FROM staging_marts.mart_job_feed f "
                        f"WHERE f.workplace_type = 'remote' AND {condition}")
            population[stratum] = cur.fetchone()["n"]
            cur.execute(SAMPLE_SQL.format(condition=condition), {"seed": seed, "limit": round(n * SHARE[stratum])})
            rows += [{**r, "stratum": stratum} for r in cur.fetchall()]
    conn.rollback()
    return rows, population


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sample feed jobs for the eligibility hand check")
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", default="1")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    conn = psycopg2.connect(url)
    try:
        rows, population = sample(conn, args.n, args.seed)
    finally:
        conn.close()
    Path(args.out).write_text(render(rows, population), encoding="utf-8")
    print(f"wrote {len(rows)} jobs to {args.out}")
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
