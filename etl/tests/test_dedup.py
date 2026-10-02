import json
from pathlib import Path

import psycopg2
import pytest

from enrich.fingerprint import SOURCE_PRIORITY
from ops import dedup
from tests.dbutil import run_sql

MIGRATION = Path(__file__).resolve().parents[2] / "database" / "migrations" / "013_dedup_enrichment.sql"


@pytest.fixture
def db(pipeline_db):
    run_sql(pipeline_db, MIGRATION.read_text(encoding="utf-8"))
    return pipeline_db


@pytest.fixture
def conn(db):
    c = psycopg2.connect(db)
    yield c
    c.close()


def add(url, pid, source, company, title, location, closed=False, seen_days_ago=0):
    (raw_id,), = run_sql(url, """INSERT INTO raw.jobs (job_platform_id, raw_data, source, last_seen_at, closed_at)
                                 VALUES (%s, '{}', %s, now() - make_interval(days => %s),
                                         CASE WHEN %s THEN now() END) RETURNING id""",
                         (pid, source, seen_days_ago, closed))
    (job_id,), = run_sql(url, """INSERT INTO staging.stg_jobs (job_platform_id, title, company_name, location_display,
                                     location_areas, raw_job_id, source)
                                 VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING job_id""",
                         (pid, title, company, location, [location], raw_id, source))
    return job_id


def canon(url):
    return dict(run_sql(url, "SELECT job_id, canonical_job_id FROM staging.stg_jobs"))


def test_fill_fingerprints_only_new_rows(db, conn):
    add(db, "a", "greenhouse", "Acme", "Data Engineer", "Remote")
    assert dedup.fill_fingerprints(conn) == 1
    assert dedup.fill_fingerprints(conn) == 0
    add(db, "b", "lever", "Beta", "Data Analyst", "Remote")
    assert dedup.fill_fingerprints(conn) == 1
    assert dedup.fill_fingerprints(conn, recompute=True) == 2
    assert run_sql(db, "SELECT fingerprint FROM staging.stg_jobs WHERE job_platform_id = 'a'") == \
        [("acme|data engineer|",)]


def test_cross_source_duplicate_prefers_company_board(db, conn):
    hm = add(db, "hm", "himalayas", "GitLab", "Senior Backend Engineer", "Worldwide")
    gh = add(db, "gh", "greenhouse", "gitlab", "Senior Backend Engineer (Remote)", "Remote", seen_days_ago=2)
    az = add(db, "az", "adzuna", "GitLab Inc.", "Senior Backend Engineer", "Remote")
    dedup.fill_fingerprints(conn)
    assert dedup.assign_canonical(conn) == 3
    assert canon(db) == {hm: gh, gh: gh, az: gh}


def test_closed_jobs_do_not_win(db, conn):
    hm = add(db, "hm", "himalayas", "GitLab", "Senior Backend Engineer", "Worldwide")
    add(db, "gh", "greenhouse", "gitlab", "Senior Backend Engineer", "Remote", closed=True)
    dedup.fill_fingerprints(conn)
    dedup.assign_canonical(conn)
    assert canon(db)[hm] == hm


def test_unique_jobs_are_their_own_canonical(db, conn):
    a = add(db, "a", "greenhouse", "Acme", "Data Engineer", "Remote")
    b = add(db, "b", "greenhouse", "Acme", "Data Engineer", "Remote - Canada")
    dedup.fill_fingerprints(conn)
    dedup.assign_canonical(conn)
    assert canon(db) == {a: a, b: b}
    assert dedup.assign_canonical(conn) == 0  # nothing changes on a re-run


def test_sql_priority_matches_python_priority():
    for source in SOURCE_PRIORITY:
        if source != "default":
            assert f"'{source}'" in dedup.CANONICAL_SQL
