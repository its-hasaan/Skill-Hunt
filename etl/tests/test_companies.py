from pathlib import Path

import psycopg2
import pytest

from ops import companies
from tests.dbutil import run_sql

MIGRATION = Path(__file__).resolve().parents[2] / "database" / "migrations" / "012_ats_companies.sql"


@pytest.fixture
def conn(fresh_db):
    run_sql(fresh_db, MIGRATION.read_text(encoding="utf-8"))
    c = psycopg2.connect(fresh_db)
    yield c
    c.close()


def test_upsert_candidates_is_idempotent(conn):
    assert companies.upsert_candidates(conn, "greenhouse", ["gitlab", "figma"], "seed") == 2
    assert companies.upsert_candidates(conn, "greenhouse", ["gitlab", "stripe"], "commoncrawl") == 1


def test_validate_marks_live_boards_active(conn):
    companies.upsert_candidates(conn, "greenhouse", ["gitlab"], "seed")
    result = companies.validate(conn, probe=lambda ats, token: 12)
    assert result == {"checked": 1, "active": 1, "failed": 0}
    assert companies.active_boards(conn, "greenhouse") == ["gitlab"]


def test_validate_marks_dead_boards_inactive(conn):
    companies.upsert_candidates(conn, "lever", ["gone"], "seed")
    for _ in range(2):
        companies.validate(conn, probe=lambda ats, token: None)
    assert companies.active_boards(conn, "lever") == []
    with conn.cursor() as cur:
        cur.execute("SELECT active, fail_count FROM ops.companies WHERE board_token = 'gone'")
        assert cur.fetchone() == (None, 2)  # not yet given up
    companies.validate(conn, probe=lambda ats, token: None)
    with conn.cursor() as cur:
        cur.execute("SELECT active, fail_count FROM ops.companies WHERE board_token = 'gone'")
        assert cur.fetchone() == (False, 3)
    companies.record_check(conn, "lever", "gone", ok=True, job_count=4)
    assert companies.active_boards(conn, "lever") == ["gone"]


def test_active_boards_only_returns_active(conn):
    companies.upsert_candidates(conn, "ashby", ["a", "b"], "seed")
    companies.record_check(conn, "ashby", "a", ok=True, job_count=3)
    assert companies.active_boards(conn, "ashby") == ["a"]


def test_validate_skips_inactive_and_respects_limit(conn):
    companies.upsert_candidates(conn, "greenhouse", ["a", "b", "c"], "seed")
    calls = []
    companies.validate(conn, probe=lambda ats, token: calls.append(token) or 1, limit=2)
    assert len(calls) == 2


def test_interpret_probe_responses():
    # Unknown boards: 404 on Greenhouse/Lever/Ashby, but 200 + empty list on
    # SmartRecruiters, so an empty SmartRecruiters board counts as missing.
    assert companies.interpret("greenhouse", 404, None) is None
    assert companies.interpret("greenhouse", 200, {"jobs": []}) == 0
    assert companies.interpret("lever", 200, [{"id": 1}]) == 1
    assert companies.interpret("smartrecruiters", 200, {"content": [], "totalFound": 0}) is None
    assert companies.interpret("smartrecruiters", 200, {"content": [{"id": 1}], "totalFound": 1}) == 1
    assert companies.interpret("ashby", 200, {"error": "x"}) is None


def test_active_boards_rotate_least_recently_checked_first(conn):
    companies.upsert_candidates(conn, "greenhouse", ["a", "b", "c"], "seed")
    for token in ("a", "b", "c"):
        companies.record_check(conn, "greenhouse", token, ok=True, job_count=1)
    with conn, conn.cursor() as cur:
        cur.execute("UPDATE ops.companies SET last_checked_at = now() - interval '1 day' WHERE board_token = 'c'")
    assert companies.active_boards(conn, "greenhouse")[0] == "c"
    companies.record_check(conn, "greenhouse", "c", ok=True, job_count=1)  # fetched today: goes to the back
    assert companies.active_boards(conn, "greenhouse")[-1] == "c"


def test_probe_urls_skip_descriptions():
    from connectors.ats_endpoints import list_url, probe_url
    assert "content=true" not in probe_url("greenhouse", "acme")
    assert probe_url("workable", "acme") == "https://apply.workable.com/api/v1/widget/accounts/acme"
    assert probe_url("lever", "acme").endswith("&limit=1")
    assert probe_url("ashby", "acme") == list_url("ashby", "acme")
