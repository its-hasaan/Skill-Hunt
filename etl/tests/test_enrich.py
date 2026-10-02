from pathlib import Path

import psycopg2
import pytest

from ops import enrich
from tests.dbutil import run_sql

MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations"


@pytest.fixture
def db(pipeline_db):
    for name in ("004_currency_rates.sql", "013_dedup_enrichment.sql"):
        run_sql(pipeline_db, (MIGRATIONS / name).read_text(encoding="utf-8"))
    run_sql(pipeline_db, "INSERT INTO staging.currency_rates (currency_code, rate_to_usd) VALUES ('INR', 80) "
                         "ON CONFLICT (currency_code) DO UPDATE SET rate_to_usd = 80")
    return pipeline_db


@pytest.fixture
def conn(db):
    c = psycopg2.connect(db)
    yield c
    c.close()


def add(url, pid, location="Remote - United States", description="Python and SQL.", workplace="remote",
        country="remote", source="greenhouse", closed=False, title="Senior Data Engineer",
        salary=(None, None, "USD")):
    (raw_id,), = run_sql(url, """INSERT INTO raw.jobs (job_platform_id, raw_data, source, closed_at)
                                 VALUES (%s, '{}', %s, CASE WHEN %s THEN now() END) RETURNING id""",
                         (pid, source, closed))
    (job_id,), = run_sql(url, """INSERT INTO staging.stg_jobs (job_platform_id, title, description, location_display,
                                     location_areas, workplace_type, country_code, raw_job_id, source,
                                     salary_min, salary_max, salary_currency)
                                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING job_id""",
                         (pid, title, description, location, [location], workplace, country, raw_id, source,
                          *salary))
    return job_id


def enrichment(url, job_id):
    rows = run_sql(url, """SELECT remote_scope, eligible_pk, eligible_in, eligibility_evidence, seniority,
                                  min_years, tz_overlap, salary_min_usd, salary_max_usd, method, rules_version
                           FROM staging.job_enrichment WHERE job_id = %s""", (job_id,))
    return rows[0] if rows else None


def test_rules_pass_enriches_open_feed_candidates_only(db, conn):
    remote = add(db, "a")
    local = add(db, "b", location="Lahore, Pakistan", workplace="onsite", country="pk")
    closed = add(db, "c", closed=True)
    adzuna_gb = add(db, "d", location="London", workplace=None, country="gb", source="adzuna")

    result = enrich.enrich_rules(conn, enrich.load_rates(conn))

    assert result["enriched"] == 2
    assert enrichment(db, remote)[:5] == ("countries", False, False, "Remote - United States", "senior")
    assert enrichment(db, local)[:3] == ("onsite", True, False)
    assert enrichment(db, closed) is None and enrichment(db, adzuna_gb) is None
    assert enrichment(db, remote)[9:] == ("rules", enrich.RULES_VERSION)


def test_attributes_are_stored(db, conn):
    job = add(db, "a", description="You need 4+ years of experience. Overlap with EST hours daily.")
    enrich.enrich_rules(conn, enrich.load_rates(conn))
    assert enrichment(db, job)[5:7] == (4, "americas")


def test_reenrich_only_when_content_or_rules_change(db, conn):
    a = add(db, "a")
    b = add(db, "b", location="Remote")
    rates = enrich.load_rates(conn)
    assert enrich.enrich_rules(conn, rates)["enriched"] == 2
    assert enrich.enrich_rules(conn, rates)["enriched"] == 0

    run_sql(db, "UPDATE staging.stg_jobs SET description = 'You must be based in India.' WHERE job_id = %s", (a,))
    assert enrich.enrich_rules(conn, rates)["enriched"] == 1
    assert enrichment(db, a)[1:3] == (False, True)

    # an AI label with unchanged text survives a rules upgrade
    run_sql(db, "UPDATE staging.job_enrichment SET method = 'llm', eligible_pk = TRUE WHERE job_id = %s", (b,))
    assert enrich.enrich_rules(conn, rates, rules_version=enrich.RULES_VERSION + 1)["enriched"] == 1
    assert enrichment(db, b)[1] is True and enrichment(db, b)[9] == "llm"
    assert enrichment(db, a)[10] == enrich.RULES_VERSION + 1

    # ...but not a change to its text
    run_sql(db, "UPDATE staging.stg_jobs SET title = 'Data Engineer' WHERE job_id = %s", (b,))
    assert enrich.enrich_rules(conn, rates, rules_version=enrich.RULES_VERSION + 1)["enriched"] == 1
    assert enrichment(db, b)[9] == "rules"


def test_salary_converted_to_usd(db, conn):
    inr = add(db, "a", location="Bengaluru", workplace="onsite", country="in",
              salary=(2_400_000, 3_200_000, "INR"))
    text = add(db, "b", description="The range is $120K - $150K per year.")
    unknown = add(db, "c", salary=(50_000, 60_000, "XYZ"))
    enrich.enrich_rules(conn, enrich.load_rates(conn))
    assert enrichment(db, inr)[7:9] == (30000, 40000)
    assert enrichment(db, text)[7:9] == (120000, 150000)
    assert enrichment(db, unknown)[7:9] == (None, None)


def test_batches_cover_every_candidate(db, conn):
    for i in range(7):
        add(db, f"j{i}")
    assert enrich.enrich_rules(conn, enrich.load_rates(conn), batch_size=3)["enriched"] == 7
