import io

from ops.dbconfig import dbt_env_vars, load_local_env, session_pooler_url, write_github_env
from tests.dbutil import run_sql

URL = "postgresql://postgres.abc:p%40ss@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"


def test_session_pooler_url_rewrites_transaction_port():
    assert session_pooler_url(URL).endswith("pooler.supabase.com:5432/postgres")


def test_session_pooler_url_leaves_other_urls_alone():
    session = URL.replace(":6543/", ":5432/")
    assert session_pooler_url(session) == session
    assert session_pooler_url(None) is None


def test_dbt_env_vars_decode_credentials_and_use_session_port():
    assert dbt_env_vars(URL) == {
        "DB_HOST": "aws-1-ap-south-1.pooler.supabase.com",
        "DB_PORT": "5432",
        "DB_USER": "postgres.abc",
        "DB_PASSWORD": "p@ss",
        "DB_NAME": "postgres",
    }


def test_write_github_env_masks_password_and_appends(tmp_path):
    env_file = tmp_path / "github_env"
    env_file.write_text("EXISTING=1\n")
    out = io.StringIO()
    write_github_env(URL, str(env_file), out=out)
    assert out.getvalue().strip() == "::add-mask::p@ss"
    lines = env_file.read_text().splitlines()
    assert lines[0] == "EXISTING=1"
    assert "DB_PORT=5432" in lines
    assert any(l.startswith("SUPABASE_SESSION_URL=") and ":5432/" in l for l in lines)


def test_load_local_env_fills_missing_vars_without_overriding(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("JOBWISE_TEST_A=from-file\nJOBWISE_TEST_B=from-file\n")
    monkeypatch.delenv("JOBWISE_TEST_A", raising=False)
    monkeypatch.setenv("JOBWISE_TEST_B", "from-shell")
    load_local_env(env_file)
    import os
    assert os.environ["JOBWISE_TEST_A"] == "from-file"
    assert os.environ["JOBWISE_TEST_B"] == "from-shell"
    monkeypatch.delenv("JOBWISE_TEST_A")


def test_fresh_db_fixture_gives_an_empty_database(fresh_db):
    assert run_sql(fresh_db, "SELECT 1") == [(1,)]
