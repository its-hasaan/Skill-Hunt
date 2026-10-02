import json
from pathlib import Path

import psycopg2
import pytest

from ops import career_sites
from tests.dbutil import run_sql

MIGRATION = Path(__file__).resolve().parents[2] / "database" / "migrations" / "014_career_sites.sql"


@pytest.fixture
def conn(fresh_db):
    run_sql(fresh_db, MIGRATION.read_text(encoding="utf-8"))
    c = psycopg2.connect(fresh_db)
    yield c
    c.close()


def domains(conn, limit=10):
    return [s["domain"] for s in career_sites.sites_to_crawl(conn, limit)]


def test_seed_is_idempotent(conn, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"sites": [{"domain": "acme.example", "careers_url": "https://acme.example/jobs"},
                                          {"domain": "Beta.example"}]}), encoding="utf-8")
    assert career_sites.seed(conn, seed) == 2
    assert career_sites.seed(conn, seed) == 0
    sites = {s["domain"]: s for s in career_sites.sites_to_crawl(conn, 10)}
    assert sites["acme.example"]["careers_url"] == "https://acme.example/jobs"
    assert sites["beta.example"]["careers_url"] is None


def test_sites_to_crawl_skips_ats_blocked_and_failing(conn, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"sites": [{"domain": d} for d in ("a.ex", "b.ex", "c.ex", "d.ex", "e.ex")]}))
    career_sites.seed(conn, seed)
    career_sites.record_crawl(conn, "a.ex", "ats", ats="greenhouse", board_token="a")
    career_sites.record_crawl(conn, "b.ex", "blocked")
    for _ in range(3):
        career_sites.record_crawl(conn, "c.ex", None, failed=True)
    career_sites.record_crawl(conn, "d.ex", "jsonld", jobs_found=4)
    assert domains(conn) == ["e.ex", "d.ex"]  # never crawled first
    assert domains(conn, limit=1) == ["e.ex"]


def test_empty_sites_are_retried_weekly(conn, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"sites": [{"domain": "a.ex"}]}))
    career_sites.seed(conn, seed)
    career_sites.record_crawl(conn, "a.ex", "empty")
    assert domains(conn) == []
    run_sql_conn(conn, "UPDATE ops.career_sites SET last_crawled_at = now() - interval '8 days'")
    assert domains(conn) == ["a.ex"]


def test_record_crawl_counts_failures_and_resets(conn, tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"sites": [{"domain": "a.ex"}]}))
    career_sites.seed(conn, seed)
    career_sites.record_crawl(conn, "a.ex", None, failed=True)
    career_sites.record_crawl(conn, "a.ex", "jsonld", jobs_found=3, etag='"v1"', last_modified="Tue, 01 Oct 2026")
    with conn.cursor() as cur:
        cur.execute("SELECT status, fail_count, jobs_found, etag FROM ops.career_sites")
        assert cur.fetchone() == ("jsonld", 0, 3, '"v1"')
    conn.rollback()
    career_sites.record_crawl(conn, "a.ex", "jsonld")  # 304: keep what we knew
    with conn.cursor() as cur:
        cur.execute("SELECT jobs_found, etag FROM ops.career_sites")
        assert cur.fetchone() == (3, '"v1"')
    conn.rollback()


def run_sql_conn(conn, sql):
    with conn, conn.cursor() as cur:
        cur.execute(sql)
