"""
Enrich feed jobs: eligibility for Pakistan/India, seniority, minimum years,
timezone overlap and USD salary, stored in staging.job_enrichment.

    python -m ops.enrich [--dedup] [--rules] [--llm] [--max-calls N]

With no step flags it runs --dedup --rules.

Feed candidates are open jobs (raw.jobs.closed_at IS NULL) that are remote
or located in Pakistan/India. A job is (re-)enriched by rules when it has
no row yet, its text changed (content_hash), or its row came from an older
RULES_VERSION. AI labels (method='llm') are kept until the text changes.
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

from enrich.attributes import min_years, salary_from_text, seniority, tz_overlap
from enrich.eligibility import RULES_VERSION, classify
from ops.dbconfig import load_local_env, session_pooler_url

CONTENT_HASH = ("md5(concat_ws('|', s.title, s.location_display, "
                "array_to_string(s.location_areas, ';'), s.description))")

FEED_CANDIDATE = """r.closed_at IS NULL
                    AND (s.workplace_type = 'remote' OR s.country_code IN ('pk', 'in'))"""

RULES_CANDIDATES_SQL = f"""
    SELECT s.job_id, s.title, s.description, s.location_display, s.location_areas, s.workplace_type,
           s.country_code, s.salary_min, s.salary_max, s.salary_currency, {CONTENT_HASH} AS content_hash
    FROM staging.stg_jobs s
    JOIN raw.jobs r ON r.id = s.raw_job_id
    LEFT JOIN staging.job_enrichment e ON e.job_id = s.job_id
    WHERE {FEED_CANDIDATE}
      AND s.job_id > %(after)s
      AND (e.job_id IS NULL
           OR e.content_hash <> {CONTENT_HASH}
           OR (e.method = 'rules' AND e.rules_version < %(rules_version)s))
    ORDER BY s.job_id
    LIMIT %(limit)s
"""

UPSERT_SQL = """
    INSERT INTO staging.job_enrichment (
        job_id, content_hash, rules_version, remote_scope, eligible_countries, eligible_regions,
        eligible_pk, eligible_in, eligibility_confidence, eligibility_evidence, seniority, min_years,
        tz_overlap, salary_min_usd, salary_max_usd, method, model, enriched_at)
    VALUES %s
    ON CONFLICT (job_id) DO UPDATE SET
        content_hash = EXCLUDED.content_hash, rules_version = EXCLUDED.rules_version,
        remote_scope = EXCLUDED.remote_scope, eligible_countries = EXCLUDED.eligible_countries,
        eligible_regions = EXCLUDED.eligible_regions, eligible_pk = EXCLUDED.eligible_pk,
        eligible_in = EXCLUDED.eligible_in, eligibility_confidence = EXCLUDED.eligibility_confidence,
        eligibility_evidence = EXCLUDED.eligibility_evidence, seniority = EXCLUDED.seniority,
        min_years = EXCLUDED.min_years, tz_overlap = EXCLUDED.tz_overlap,
        salary_min_usd = EXCLUDED.salary_min_usd, salary_max_usd = EXCLUDED.salary_max_usd,
        method = EXCLUDED.method, model = EXCLUDED.model, enriched_at = now()
"""
UPSERT_TEMPLATE = "(" + ", ".join(["%s"] * 17) + ", now())"


def load_rates(conn) -> dict[str, float]:
    with conn.cursor() as cur:
        cur.execute("SELECT currency_code, rate_to_usd FROM staging.currency_rates")
        rates = {code: float(rate) for code, rate in cur.fetchall()}
    conn.rollback()
    rates.setdefault("USD", 1.0)
    return rates


def usd_salary(job: dict, rates: dict[str, float]):
    """Structured salary converted to USD; else an annual range in the text."""
    low, high, currency = job.get("salary_min"), job.get("salary_max"), job.get("salary_currency") or "USD"
    if low is None and high is None:
        parsed = salary_from_text(job.get("description"))
        if not parsed:
            return None, None
        low, high, currency = parsed
    rate = rates.get(currency)
    if not rate:
        return None, None
    convert = (lambda v: round(float(v) / rate, 2) if v is not None else None)
    return convert(low), convert(high)


def rules_row(job: dict, rates: dict[str, float], rules_version: int) -> tuple:
    label = classify(job)
    years = min_years(job.get("description"))
    salary_min_usd, salary_max_usd = usd_salary(job, rates)
    return (
        job["job_id"], job["content_hash"], rules_version, label.remote_scope,
        label.eligible_countries, label.eligible_regions, label.eligible_pk, label.eligible_in,
        label.confidence, label.evidence, seniority(job.get("title"), years), years,
        tz_overlap(job.get("description")), salary_min_usd, salary_max_usd, "rules", None,
    )


def upsert(conn, rows: list[tuple]) -> None:
    if rows:
        with conn, conn.cursor() as cur:
            execute_values(cur, UPSERT_SQL, rows, template=UPSERT_TEMPLATE, page_size=500)


def enrich_rules(conn, rates: dict[str, float], rules_version: int = RULES_VERSION,
                 batch_size: int = 500) -> dict:
    """Label every feed candidate that needs it. Keyset-paginated by job_id,
    so each candidate is visited once per run."""
    after, enriched = 0, 0
    while True:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(RULES_CANDIDATES_SQL, {"after": after, "rules_version": rules_version,
                                               "limit": batch_size})
            jobs = cur.fetchall()
        conn.rollback()
        if not jobs:
            break
        upsert(conn, [rules_row(job, rates, rules_version) for job in jobs])
        enriched += len(jobs)
        after = jobs[-1]["job_id"]
        print(f"  rules: {enriched} jobs labelled", flush=True)
    return {"enriched": enriched}


LLM_CANDIDATES_SQL = f"""
    SELECT s.job_id, s.title, s.company_name, s.location_display, s.location_areas, s.description,
           e.content_hash, e.eligible_pk, e.eligible_in, e.eligibility_evidence, e.remote_scope
    FROM staging.stg_jobs s
    JOIN raw.jobs r ON r.id = s.raw_job_id
    JOIN staging.job_enrichment e ON e.job_id = s.job_id
    WHERE {FEED_CANDIDATE}
      AND s.canonical_job_id = s.job_id
      AND e.method = 'rules'
      AND e.remote_scope NOT IN ('onsite', 'hybrid')
      AND (e.eligible_pk IS NULL OR e.eligible_in IS NULL)
      AND s.job_id > %(after)s
    ORDER BY s.job_id
    LIMIT %(limit)s
"""

LLM_UPDATE_SQL = """
    UPDATE staging.job_enrichment e SET
        eligible_pk = v.pk, eligible_in = v.inn, eligibility_evidence = v.evidence,
        eligibility_confidence = v.confidence, remote_scope = v.scope,
        method = 'llm', model = v.model, enriched_at = now()
    FROM (VALUES %s) AS v(job_id, content_hash, pk, inn, evidence, confidence, scope, model)
    WHERE e.job_id = v.job_id AND e.content_hash = v.content_hash
"""
LLM_UPDATE_TEMPLATE = "(%s::int, %s::text, %s::boolean, %s::boolean, %s::text, %s::numeric, %s::text, %s::text)"


def llm_row(job: dict, label, model: str) -> tuple:
    """Rules answers that were already decided are kept; the AI fills the gaps."""
    pk = job["eligible_pk"] if job["eligible_pk"] is not None else label.eligible_pk
    inn = job["eligible_in"] if job["eligible_in"] is not None else label.eligible_in
    filled = (job["eligible_pk"] is None and label.eligible_pk is not None) or \
             (job["eligible_in"] is None and label.eligible_in is not None)
    evidence = label.evidence if filled else job["eligibility_evidence"]
    scope = label.remote_scope if filled and label.remote_scope != "unclear" else job["remote_scope"]
    confidence = label.confidence if filled else 0.3
    return (job["job_id"], job["content_hash"], pk, inn, evidence, confidence, scope, model)


def enrich_llm(conn, client, max_calls: int, batch_size: int = 20) -> dict:
    """Send unclear canonical feed jobs to the AI, `batch_size` per call.

    Every answered job is stored as method='llm' (even "unclear"), so it
    isn't re-sent until its text changes. A batch whose answer can't be
    parsed is left as it was and retried on a later run."""
    from enrich.gemini import QuotaExhausted

    result = {"calls": 0, "labelled": 0, "decided": 0, "stopped": None}
    after = 0
    while result["calls"] < max_calls:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(LLM_CANDIDATES_SQL, {"after": after, "limit": batch_size})
            jobs = cur.fetchall()
        conn.rollback()
        if not jobs:
            break
        after = jobs[-1]["job_id"]
        result["calls"] += 1
        try:
            labels = client.label(jobs)
        except QuotaExhausted:
            result["stopped"] = "quota"
            break
        rows = [llm_row(job, labels[job["job_id"]], client.model) for job in jobs if job["job_id"] in labels]
        if rows:
            with conn, conn.cursor() as cur:
                execute_values(cur, LLM_UPDATE_SQL, rows, template=LLM_UPDATE_TEMPLATE)
        result["labelled"] += len(rows)
        result["decided"] += sum(1 for job in jobs if job["job_id"] in labels and
                                 (labels[job["job_id"]].eligible_pk is not None or
                                  labels[job["job_id"]].eligible_in is not None))
        print(f"  llm: {result['calls']} calls, {result['labelled']} labelled", flush=True)
    else:
        result["stopped"] = "max_calls"
    return result


def summary(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT count(*) AS open_feed_jobs,
                   count(*) FILTER (WHERE s.workplace_type = 'remote') AS remote,
                   count(*) FILTER (WHERE e.eligible_pk) AS eligible_pk,
                   count(*) FILTER (WHERE e.eligible_in) AS eligible_in,
                   count(*) FILTER (WHERE e.eligible_pk IS NULL OR e.eligible_in IS NULL) AS unclear,
                   count(*) FILTER (WHERE e.method = 'llm') AS llm
            FROM staging.stg_jobs s
            JOIN raw.jobs r ON r.id = s.raw_job_id
            JOIN staging.job_enrichment e ON e.job_id = s.job_id
            WHERE {FEED_CANDIDATE} AND s.canonical_job_id = s.job_id""")
        names = [d[0] for d in cur.description]
        result = dict(zip(names, cur.fetchone()))
    conn.rollback()
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Enrich feed jobs with eligibility and attributes")
    parser.add_argument("--dedup", action="store_true", help="fingerprint + canonical jobs first")
    parser.add_argument("--rules", action="store_true", help="rule-based labels")
    parser.add_argument("--llm", action="store_true", help="AI labels for unclear jobs (needs GEMINI_API_KEY)")
    parser.add_argument("--max-calls", type=int, default=150, help="AI calls per run (20 jobs each)")
    args = parser.parse_args(argv)
    if not (args.dedup or args.rules or args.llm):
        args.dedup = args.rules = True

    api_key = os.getenv("GEMINI_API_KEY")
    if args.llm and not api_key:
        print("GEMINI_API_KEY is not set: skipping the AI eligibility pass; unclear jobs stay unclear.",
              flush=True)
        args.llm = False
        if not (args.dedup or args.rules):
            return 0

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    conn = psycopg2.connect(url)
    try:
        if args.dedup:
            from ops import dedup
            print(f"dedup: {dedup.run(conn)}", flush=True)
        if args.rules:
            print(f"rules: {enrich_rules(conn, load_rates(conn))}", flush=True)
        if args.llm:
            from enrich.gemini import DEFAULT_MODEL, GeminiClient
            client = GeminiClient(api_key, os.getenv("GEMINI_MODEL") or DEFAULT_MODEL)
            print(f"llm: {enrich_llm(conn, client, args.max_calls)}", flush=True)
        print(f"feed: {summary(conn)}", flush=True)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
