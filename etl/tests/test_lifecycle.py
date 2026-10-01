import json

import psycopg2
import pytest

from ops import lifecycle
from tests.dbutil import run_sql


def row(pid, source="greenhouse", country="remote"):
    return (pid, "Data Engineer", country, json.dumps({"_source": source}), None, source)


@pytest.fixture
def conn(pipeline_db):
    c = psycopg2.connect(pipeline_db)
    yield c
    c.close()


def db_now(url):
    return run_sql(url, "SELECT now()")[0][0]


def test_new_rows_insert_and_seen_rows_bump_last_seen(pipeline_db, conn):
    rows = [row("greenhouse:acme:1"), row("greenhouse:acme:2")]
    assert lifecycle.save_jobs(conn, rows) == (2, 2)
    run_sql(pipeline_db, "UPDATE raw.jobs SET last_seen_at = now() - interval '3 days'")
    assert lifecycle.save_jobs(conn, rows) == (0, 2)
    assert run_sql(pipeline_db, "SELECT count(*) FROM raw.jobs WHERE last_seen_at > now() - interval '1 hour'") == [(2,)]


def test_close_unseen_only_for_fetched_boards(pipeline_db, conn):
    lifecycle.save_jobs(conn, [row("greenhouse:a:1"), row("greenhouse:a:2"), row("greenhouse:b:1")])
    run_sql(pipeline_db, "UPDATE raw.jobs SET last_seen_at = now() - interval '1 day'")
    since = db_now(pipeline_db)
    lifecycle.save_jobs(conn, [row("greenhouse:a:1")])           # board a re-fetched without a:2
    assert lifecycle.close_unseen(conn, "greenhouse", ["a"], since) == 1
    closed = run_sql(pipeline_db, "SELECT job_platform_id FROM raw.jobs WHERE closed_at IS NOT NULL")
    assert closed == [("greenhouse:a:2",)]


def test_failed_board_closes_nothing(pipeline_db, conn):
    lifecycle.save_jobs(conn, [row("greenhouse:a:1")])
    run_sql(pipeline_db, "UPDATE raw.jobs SET last_seen_at = now() - interval '1 day'")
    assert lifecycle.close_unseen(conn, "greenhouse", [], db_now(pipeline_db)) == 0


def test_reseen_job_reopens(pipeline_db, conn):
    lifecycle.save_jobs(conn, [row("lever:x:9")])
    run_sql(pipeline_db, "UPDATE raw.jobs SET closed_at = now() - interval '2 days'")
    assert lifecycle.save_jobs(conn, [row("lever:x:9")]) == (0, 1)
    assert run_sql(pipeline_db, "SELECT closed_at IS NULL, count(*) FROM raw.jobs GROUP BY 1") == [(True, 1)]


def test_age_out_feed_jobs(pipeline_db, conn):
    lifecycle.save_jobs(conn, [row("remoteok:1", source="remoteok"), row("greenhouse:a:1")])
    run_sql(pipeline_db, "UPDATE raw.jobs SET last_seen_at = now() - interval '15 days'")
    assert lifecycle.age_out_feed_jobs(conn, days=14, exclude_sources={"greenhouse"}) == 1
    assert run_sql(pipeline_db, "SELECT source FROM raw.jobs WHERE closed_at IS NOT NULL") == [("remoteok",)]


def test_duplicate_keys_in_one_batch_are_collapsed(pipeline_db, conn):
    # Feeds sometimes list the same job twice in one fetch (seen on Himalayas).
    rows = [row("himalayas:1", source="himalayas"), row("himalayas:1", source="himalayas"),
            row("himalayas:2", source="himalayas")]
    assert lifecycle.save_jobs(conn, rows) == (2, 2)
    assert run_sql(pipeline_db, "SELECT count(*) FROM raw.jobs") == [(2,)]
