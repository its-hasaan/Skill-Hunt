from datetime import datetime, timedelta, timezone

from ops import marts_guard
from tests.dbutil import run_sql


def add_jobs(url, n, days_ago):
    posted = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
    for i in range(n):
        run_sql(url, "INSERT INTO staging.stg_jobs (job_platform_id, job_posted_at) VALUES (%s, %s)",
                (f"j{days_ago}-{i}", posted))


def test_counts_only_jobs_in_the_mart_window(pipeline_db):
    add_jobs(pipeline_db, 3, days_ago=5)
    add_jobs(pipeline_db, 2, days_ago=90)
    assert marts_guard.fresh_job_count(pipeline_db) == 3


def test_blocks_rebuild_on_thin_data(pipeline_db, monkeypatch, capsys):
    add_jobs(pipeline_db, 3, days_ago=5)
    monkeypatch.setenv("SUPABASE_URL", pipeline_db)
    assert marts_guard.main(["--min-jobs", "3"]) == 0
    assert marts_guard.main(["--min-jobs", "4"]) == 1
    assert "keeping the existing marts" in capsys.readouterr().out
