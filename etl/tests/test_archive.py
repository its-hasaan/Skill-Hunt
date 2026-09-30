from ops import archive
from tests.dbutil import run_sql


def test_archive_calls_the_snapshot_function(fresh_db, monkeypatch):
    run_sql(fresh_db, """
        CREATE TABLE calls (at timestamptz DEFAULT now());
        CREATE FUNCTION archive_skill_demand() RETURNS void AS $$
            INSERT INTO calls DEFAULT VALUES;
        $$ LANGUAGE sql;
    """)
    monkeypatch.setenv("SUPABASE_URL", fresh_db)
    assert archive.main() == 0
    assert run_sql(fresh_db, "SELECT count(*) FROM calls") == [(1,)]
