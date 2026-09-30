from pathlib import Path

import psycopg2
import pytest

from ops import migrate
from tests.dbutil import run_sql

REAL_MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations"


def write(directory, name, sql):
    path = directory / name
    path.write_text(sql, encoding="utf-8")
    return path


@pytest.fixture
def mig_dir(tmp_path):
    write(tmp_path, "001_first.sql", "BEGIN; CREATE TABLE a (id int); COMMIT;")
    write(tmp_path, "002_second.sql", "BEGIN; CREATE TABLE b (id int); COMMIT;")
    write(tmp_path, "notes.txt", "ignored")
    return tmp_path


@pytest.fixture
def conn(fresh_db):
    c = migrate.connect(fresh_db)
    yield c
    c.close()


def test_discover_returns_numbered_sql_files_in_order(mig_dir):
    assert [p.name for p in migrate.discover(mig_dir)] == ["001_first.sql", "002_second.sql"]


def test_up_applies_pending_once(conn, mig_dir, fresh_db):
    assert migrate.up(conn, mig_dir) == ["001_first.sql", "002_second.sql"]
    assert migrate.up(conn, mig_dir) == []
    assert run_sql(fresh_db, "SELECT count(*) FROM ops.schema_migrations") == [(2,)]
    assert run_sql(fresh_db, "SELECT to_regclass('public.b') IS NOT NULL") == [(True,)]


def test_baseline_marks_without_running(conn, mig_dir, fresh_db):
    assert migrate.baseline(conn, "1", mig_dir) == ["001_first.sql"]
    assert run_sql(fresh_db, "SELECT to_regclass('public.a') IS NULL") == [(True,)]
    assert [p.name for p in migrate.pending(conn, mig_dir)] == ["002_second.sql"]


def test_failed_migration_is_not_recorded(conn, mig_dir):
    write(mig_dir, "003_broken.sql", "BEGIN; CREATE TABLE c (id int); SELECT no_such_fn(); COMMIT;")
    with pytest.raises(psycopg2.Error):
        migrate.up(conn, mig_dir)
    assert "003_broken.sql" not in migrate.applied(conn)
    assert [p.name for p in migrate.pending(conn, mig_dir)] == ["003_broken.sql"]


def test_checksum_ignores_line_endings(tmp_path):
    lf = write(tmp_path, "001_lf.sql", "SELECT 1;\nSELECT 2;\n")
    crlf = tmp_path / "002_crlf.sql"
    crlf.write_bytes(b"SELECT 1;\r\nSELECT 2;\r\n")
    assert migrate.checksum(lf) == migrate.checksum(crlf)


def test_changed_reports_edited_applied_files(conn, mig_dir):
    migrate.up(conn, mig_dir)
    write(mig_dir, "001_first.sql", "BEGIN; CREATE TABLE a (id bigint); COMMIT;")
    assert migrate.changed(conn, mig_dir) == ["001_first.sql"]


def test_real_007_is_idempotent_and_creates_ledger(fresh_db):
    sql = (REAL_MIGRATIONS / "007_ops_pipeline_runs.sql").read_text(encoding="utf-8")
    run_sql(fresh_db, sql)
    run_sql(fresh_db, sql)
    run_sql(fresh_db, """INSERT INTO ops.pipeline_runs (run_id, step, status, started_at, finished_at)
                         VALUES ('r', 's', 'success', now(), now())""")
    assert run_sql(fresh_db, "SELECT count(*) FROM ops.pipeline_runs") == [(1,)]
