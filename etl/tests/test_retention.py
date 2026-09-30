import json
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest

from ops import retention
from tests.dbutil import run_sql


def ago(days):
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)


def add_job(url, pid, *, posted_days=None, extracted_days=0, envelope=True, processed=True, skills=1):
    raw = ({"_source": "remoteok", "_normalized": {"title": "t"}, "_raw": {"html": "x" * 100}}
           if envelope else {"title": "adzuna native"})
    (raw_id,), = run_sql(url, """INSERT INTO raw.jobs (job_platform_id, raw_data, source, extracted_at)
                                  VALUES (%s, %s, %s, %s) RETURNING id""",
                         (pid, json.dumps(raw), "remoteok" if envelope else "adzuna", ago(extracted_days)))
    if not processed:
        return raw_id
    posted = ago(posted_days) if posted_days is not None else None
    (job_id,), = run_sql(url, """INSERT INTO staging.stg_jobs (job_platform_id, job_posted_at, extracted_at, raw_job_id)
                                  VALUES (%s, %s, %s, %s) RETURNING job_id""",
                         (pid, posted, ago(extracted_days), raw_id))
    for i in range(skills):
        run_sql(url, "INSERT INTO staging.stg_job_skills (job_id, skill_id, skill_name) VALUES (%s, %s, 's')",
                (job_id, i))
    return raw_id


def has_raw_payload(url, raw_id):
    return run_sql(url, "SELECT raw_data ? '_raw' FROM raw.jobs WHERE id = %s", (raw_id,))[0][0]


def count(url, table):
    return run_sql(url, f"SELECT count(*) FROM {table}")[0][0]


@pytest.fixture
def conn(pipeline_db):
    c = psycopg2.connect(pipeline_db)
    yield c
    c.close()


def test_strips_payload_only_from_processed_rows_past_threshold(pipeline_db, conn):
    old = add_job(pipeline_db, "a", posted_days=10, extracted_days=10)
    recent = add_job(pipeline_db, "b", posted_days=2, extracted_days=2)
    unprocessed = add_job(pipeline_db, "c", extracted_days=10, processed=False)
    result = retention.apply(conn)
    assert result.stripped == 1
    assert has_raw_payload(pipeline_db, old) is False
    assert has_raw_payload(pipeline_db, recent) is True
    assert has_raw_payload(pipeline_db, unprocessed) is True


def test_keeps_thirteen_months_for_the_trend_chart(pipeline_db, conn):
    add_job(pipeline_db, "ten-months", posted_days=300, extracted_days=300)
    assert retention.apply(conn).deleted_stg == 0


def test_replaces_processed_native_payload_with_stub(pipeline_db, conn):
    native = add_job(pipeline_db, "adz", posted_days=10, extracted_days=10, envelope=False)
    fresh_native = add_job(pipeline_db, "adz-new", posted_days=2, extracted_days=2, envelope=False)
    assert retention.apply(conn).stripped == 1
    assert run_sql(pipeline_db, "SELECT raw_data FROM raw.jobs WHERE id = %s", (native,)) == [({"_stripped": True},)]
    assert run_sql(pipeline_db, "SELECT raw_data ? 'title' FROM raw.jobs WHERE id = %s", (fresh_native,)) == [(True,)]


def test_stripping_is_idempotent(pipeline_db, conn):
    add_job(pipeline_db, "env", posted_days=10, extracted_days=10)
    add_job(pipeline_db, "adz", posted_days=10, extracted_days=10, envelope=False)
    assert retention.apply(conn).stripped == 2
    assert retention.apply(conn).stripped == 0


def test_deletes_expired_jobs_with_skills_and_raw_rows(pipeline_db, conn):
    add_job(pipeline_db, "old", posted_days=500, extracted_days=5, skills=3)
    add_job(pipeline_db, "new", posted_days=30, extracted_days=5, skills=2)
    result = retention.apply(conn)
    assert (result.deleted_stg, result.deleted_raw) == (1, 1)
    assert count(pipeline_db, "staging.stg_jobs") == 1
    assert count(pipeline_db, "staging.stg_job_skills") == 2
    assert count(pipeline_db, "raw.jobs") == 1


def test_uses_extracted_at_when_posting_date_missing(pipeline_db, conn):
    add_job(pipeline_db, "undated-old", posted_days=None, extracted_days=450)
    add_job(pipeline_db, "undated-new", posted_days=None, extracted_days=10)
    assert retention.apply(conn).deleted_stg == 1


def test_deletes_old_orphan_raw_rows_only(pipeline_db, conn):
    add_job(pipeline_db, "orphan-old", extracted_days=450, processed=False)
    add_job(pipeline_db, "orphan-new", extracted_days=3, processed=False)
    assert retention.apply(conn).deleted_raw == 1
    assert run_sql(pipeline_db, "SELECT job_platform_id FROM raw.jobs") == [("orphan-new",)]


def test_refuses_when_expired_rows_exceed_max_delete(pipeline_db, conn):
    for i in range(3):
        add_job(pipeline_db, f"old{i}", posted_days=500, extracted_days=10)
    with pytest.raises(retention.RetentionLimitExceeded):
        retention.apply(conn, max_delete=2)
    assert count(pipeline_db, "staging.stg_jobs") == 3
    assert all(has_raw_payload(pipeline_db, rid) for (rid,) in run_sql(pipeline_db, "SELECT id FROM raw.jobs"))


def test_count_candidates_changes_nothing(pipeline_db, conn):
    add_job(pipeline_db, "old", posted_days=500, extracted_days=10)
    counts = retention.count_candidates(conn, retention.RETENTION_DAYS, retention.STRIP_AFTER_DAYS)
    assert counts == {"strip": 1, "expired_jobs": 1, "orphan_raw": 0}
    assert count(pipeline_db, "staging.stg_jobs") == 1


def test_main_dry_run_and_real_run(pipeline_db, monkeypatch, capsys):
    add_job(pipeline_db, "old", posted_days=500, extracted_days=10)
    monkeypatch.setenv("SUPABASE_URL", pipeline_db)
    assert retention.main(["--dry-run"]) == 0
    assert count(pipeline_db, "staging.stg_jobs") == 1
    assert retention.main([]) == 0
    assert count(pipeline_db, "staging.stg_jobs") == 0
    assert "db size" in capsys.readouterr().out
