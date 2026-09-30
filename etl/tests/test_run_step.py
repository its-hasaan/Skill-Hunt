import sys

from ops import ledger, run_step
from tests.dbutil import run_sql


def ledger_rows(url):
    return run_sql(url, "SELECT step, status, exit_code, rows_out, error FROM ops.pipeline_runs ORDER BY id")


def test_current_run_id_prefers_explicit_then_github_then_local():
    assert ledger.current_run_id({"PIPELINE_RUN_ID": "x"}) == "x"
    assert ledger.current_run_id({"GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "2"}) == "gh-42-2"
    assert ledger.current_run_id({}).startswith("local-")


def test_success_is_recorded(pipeline_db, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", pipeline_db)
    monkeypatch.setenv("PIPELINE_RUN_ID", "t-1")
    assert run_step.main(["--step", "demo", "--", sys.executable, "-c", "print('hi')"]) == 0
    assert ledger_rows(pipeline_db) == [("demo", "success", 0, None, None)]


def test_failure_keeps_exit_code_and_output_tail(pipeline_db, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", pipeline_db)
    monkeypatch.setenv("PIPELINE_RUN_ID", "t-2")
    code = run_step.main(["--step", "demo", "--", sys.executable, "-c",
                          "import sys; print('boom happened'); sys.exit(3)"])
    assert code == 3
    (step, status, exit_code, _, error), = ledger_rows(pipeline_db)
    assert (status, exit_code) == ("failure", 3)
    assert "boom happened" in error


def test_metric_counts_rows_the_step_inserted(pipeline_db, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", pipeline_db)
    monkeypatch.setenv("PIPELINE_RUN_ID", "t-3")
    insert = (
        "import os, psycopg2; c = psycopg2.connect(os.environ['SUPABASE_URL']); "
        "c.autocommit = True; c.cursor().execute("
        "\"INSERT INTO raw.jobs (job_platform_id, raw_data) VALUES ('j1', '{}')\")"
    )
    assert run_step.main(["--step", "ingest", "--metric", "raw_inserted", "--",
                          sys.executable, "-c", insert]) == 0
    assert ledger_rows(pipeline_db)[0][3] == 1


def test_unreachable_ledger_does_not_change_outcome(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "postgresql://u:p@127.0.0.1:1/none")
    assert run_step.main(["--step", "demo", "--", sys.executable, "-c", "print('ok')"]) == 0
    assert run_step.main(["--step", "demo", "--", sys.executable, "-c", "raise SystemExit(5)"]) == 5


def test_fetch_run_returns_rows_for_one_run(pipeline_db, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", pipeline_db)
    monkeypatch.setenv("PIPELINE_RUN_ID", "t-4")
    run_step.main(["--step", "a", "--", sys.executable, "-c", "pass"])
    rows = ledger.fetch_run(pipeline_db, "t-4")
    assert [r["step"] for r in rows] == ["a"]
    assert ledger.fetch_run("postgresql://u:p@127.0.0.1:1/none", "t-4") == []


def test_redact_masks_secret_env_values_and_db_password():
    env = {
        "ADZUNA_APP_KEY": "adzkey-1234567890",
        "SUPABASE_URL": "postgresql://u:VeryS3cret%40Pw@h:5432/db",
        "PATH": "/usr/bin:/bin/something-long",
    }
    text = ("url https://api.adzuna.com/x?app_key=adzkey-1234567890 "
            "db postgresql://u:VeryS3cret%40Pw@h:5432/db pw VeryS3cret@Pw path /usr/bin:/bin/something-long")
    out = run_step.redact(text, env)
    assert "adzkey-1234567890" not in out
    assert "VeryS3cret" not in out
    assert "app_key=***" in out
    assert "/usr/bin:/bin/something-long" in out  # non-secret values untouched


def test_failure_tail_is_redacted_before_it_is_stored(pipeline_db, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", pipeline_db)
    monkeypatch.setenv("PIPELINE_RUN_ID", "t-5")
    monkeypatch.setenv("ADZUNA_APP_KEY", "adzkey-1234567890")
    code = run_step.main(["--step", "adzuna", "--", sys.executable, "-c",
                          "import sys; print('401 for url: https://api.adzuna.com/x?app_key=adzkey-1234567890'); sys.exit(1)"])
    assert code == 1
    (_, _, _, _, error), = ledger_rows(pipeline_db)
    assert "adzkey-1234567890" not in error
    assert "app_key=***" in error
