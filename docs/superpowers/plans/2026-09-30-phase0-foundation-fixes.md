# Phase 0: Foundation Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily data pipeline that is diagnosable, alerts on failure, stays within the Supabase free tier, and is ready for the repo to go private.

**Architecture:** A new `etl/ops/` package holds the pipeline operations tooling. It contains:
- `dbconfig` (derives every connection setting from `SUPABASE_URL`)
- `preflight` (checks credentials and connectivity and names the fix)
- `migrate` (versioned SQL migrations)
- `ledger` and `run_step` (records each step in `ops.pipeline_runs`)
- `retention` (storage budget)
- `archive`
- `notify` (Resend email)

The ETL workflow becomes a single daily job: Adzuna runs weekly, sources run independently, and every step is recorded in the ledger. Keep-warm moves to a Cloudflare Worker. Resume uploads stop storing dead public URLs.

**Tech Stack:** Python 3.11, psycopg2, requests, pytest with a Postgres 16 container (Docker locally, a service container in CI), GitHub Actions, Cloudflare Workers (wrangler), Node 22 `node:test`, FastAPI + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-09-30-jobwise-product-roadmap-design.md` §5 (Phase 0), with §3 as the baseline facts.

## Global Constraints

- **One DB secret:** everything derives from `SUPABASE_URL` (pooler URL). The CI secrets `SUPABASE_HOST/USER/PASSWORD/DB` are no longer used.
- Long-running DB work (transform, dbt, retention, VACUUM) uses the **session pooler, port 5432**, via `ops.dbconfig.session_pooler_url`.
- DB size target: **under 350 MB** of the 500 MB free tier. Retention: **120 days** by `COALESCE(job_posted_at, extracted_at)`; strip `_raw` from processed rows after **7 days**.
- Schedule: daily `0 3 * * 0,2-6` for non-Adzuna sources; **weekly** `0 3 * * 1` including Adzuna.
- GitHub Actions budget after the repo goes private: **2,000 min/month**. The pipeline is **one job** (per-job setup overhead counts against the budget).
- Every migration file manages its own transaction (`BEGIN; … COMMIT;`) and is named `NNN_description.sql`.
- Never print secrets. Mask the DB password in Actions logs.
- Ledger writes must never break or change the outcome of a pipeline step.
- Git: commit and push each task to `main` once its tests pass. Messages are **5–8 words**, one line. **No `Co-Authored-By` or any Claude attribution.** Stage only the files you touched.

## Review Focus

1. **`SUPABASE_URL` secret points at the IPv6-only direct host, or has a stale password.** Expected: preflight fails with one line that names the fix, not a stack trace. Tests: Task 4 (`test_direct_host_is_rejected_with_fix`, `test_wrong_password_names_the_cause`).
2. **The ledger database is unreachable.** Expected: the wrapped step still runs and its exit code is preserved. Test: Task 3 (`test_unreachable_ledger_does_not_change_outcome`).
3. **The first retention run on production would delete far more rows than expected.** Expected: it aborts with no changes. Test: Task 5 (`test_refuses_when_expired_rows_exceed_max_delete`).
4. **DB down or Resend key missing when the pipeline fails.** Expected: the summary still prints, no crash, and the run is marked failed. Test: Task 6 (`test_main_without_resend_key_still_fails_run`).
5. **A migration file has CRLF line endings on a Windows checkout and LF in CI.** Expected: identical checksum, not reported as changed. Test: Task 2 (`test_checksum_ignores_line_endings`).

## Deliberately deferred (from spec §5)

- **Batched `stg_jobs` writes (PIPELINE_REVIEW #12).** Daily incremental volumes are a few thousand jobs (~10 min at 240 jobs/min). The ledger now records durations, so only build this if a daily run exceeds 25 min.
- **Signed resume URLs.** Nothing in the product reads resume files back yet. Task 9 stops storing the dead public URL; signed URLs arrive with the first feature that downloads a resume (Phase 2).

---

## File Structure

| File | Responsibility |
|---|---|
| `etl/ops/__init__.py` | Package marker |
| `etl/ops/dbconfig.py` | `session_pooler_url`, `dbt_env_vars`, `$GITHUB_ENV` writer |
| `etl/ops/migrate.py` | Discover/apply/baseline migrations; `ops.schema_migrations` |
| `etl/ops/ledger.py` | `record`, `fetch_run`, `current_run_id` for `ops.pipeline_runs` |
| `etl/ops/run_step.py` | Wraps a step subprocess: stream output, keep the tail, record to the ledger, preserve the exit code |
| `etl/ops/preflight.py` | URL diagnosis, DNS (IPv4), DB connect, Adzuna credential probe |
| `etl/ops/retention.py` | Strip payloads, delete expired jobs, VACUUM, size report |
| `etl/ops/archive.py` | Calls `archive_skill_demand()` |
| `etl/ops/notify.py` | Builds the run summary; sends a Resend email on failure |
| `etl/pytest.ini`, `etl/tests/__init__.py`, `etl/tests/conftest.py`, `etl/tests/dbutil.py`, `etl/tests/fixtures/pipeline_schema.sql` | Test harness |
| `etl/tests/test_*.py` | One test module per ops module |
| `etl/refresh_all.py` (modify) | Import from `ops.dbconfig`; record steps in the ledger |
| `database/migrations/007_ops_pipeline_runs.sql` | `ops.pipeline_runs` |
| `database/migrations/008_clear_resume_public_urls.sql` | Null out dead public resume URLs |
| `.github/workflows/etl_pipeline.yml` (rewrite) | Single daily job |
| `.github/workflows/migrate.yml` | Applies migrations on push |
| `.github/workflows/tests.yml` | pytest with a Postgres service |
| `infra/keepwarm/{worker.js,worker.test.js,package.json,wrangler.toml}` | Cloudflare cron keep-warm |
| `backend/app/storage.py`, `backend/app/routers/resume.py` (modify) | Return and store only the storage path |
| `backend/pytest.ini`, `backend/tests/{__init__,conftest,test_storage}.py` | Backend test harness |
| `docs/ops/adzuna-licence-request.md` | Draft email for the owner |
| `CLAUDE.md` (modify) | Phase status and manual steps |

Commands below assume the repo root `D:/Skill Hunt`, Git Bash, and the ETL virtualenv at `venv/`. On CI (Linux) replace `../venv/Scripts/python` with `python`.

---

### Task 1: Test harness + shared DB config

**Files:**
- Create: `etl/ops/__init__.py`, `etl/ops/dbconfig.py`, `etl/pytest.ini`, `etl/tests/__init__.py`, `etl/tests/conftest.py`, `etl/tests/dbutil.py`, `etl/tests/test_dbconfig.py`
- Modify: `etl/refresh_all.py` (delete its local `session_pooler_url`, lines 69–76; rewrite `dbt_env`, lines 115–130)

**Interfaces:**
- Produces: `ops.dbconfig.session_pooler_url(url: str | None) -> str | None`, `dbt_env_vars(url: str) -> dict[str, str]`, `write_github_env(url: str, env_file: str, out=sys.stdout) -> None`; fixtures `pg_url` (session) and `fresh_db` (per test, a URL to an empty database); helper `tests.dbutil.run_sql(url, sql, params=None) -> list | None`.

- [ ] **Step 1: Create the harness files**

`etl/pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
```

`etl/ops/__init__.py`:
```python
"""Pipeline operations tooling: config, preflight, migrations, ledger, retention, alerts."""
```

`etl/tests/__init__.py`: empty file.

`etl/tests/dbutil.py`:
```python
"""Small helpers for database-backed tests."""
import psycopg2


def run_sql(url, sql, params=None):
    """Execute one statement (or a script) in autocommit mode; return rows if any."""
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None
    finally:
        conn.close()
```

`etl/tests/conftest.py`:
```python
"""Shared fixtures.

Database tests run against a throwaway Postgres: TEST_DATABASE_URL when set
(CI service container), otherwise a docker container started once per test
session. Every test gets its own freshly created database.
"""
import os
import shutil
import subprocess
import time
import uuid

import psycopg2
import pytest


def _wait_for(url, timeout=90):
    deadline = time.time() + timeout
    while True:
        try:
            psycopg2.connect(url, connect_timeout=3).close()
            return
        except psycopg2.OperationalError:
            if time.time() > deadline:
                raise
            time.sleep(1)


def _docker_available():
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.fixture(scope="session")
def pg_url():
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        _wait_for(url)
        yield url
        return
    if not _docker_available():
        pytest.skip("Postgres tests need TEST_DATABASE_URL or a running docker daemon")
    name = f"jobwise-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name,
         "-e", "POSTGRES_PASSWORD=test", "-p", "55432:5432", "postgres:16-alpine"],
        check=True, capture_output=True,
    )
    url = "postgresql://postgres:test@localhost:55432/postgres"
    try:
        _wait_for(url)
        yield url
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True)


@pytest.fixture
def fresh_db(pg_url):
    name = f"t_{uuid.uuid4().hex[:12]}"
    admin = psycopg2.connect(pg_url)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{name}"')
    try:
        yield pg_url.rsplit("/", 1)[0] + "/" + name
    finally:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.close()
```

- [ ] **Step 2: Write the failing tests**

`etl/tests/test_dbconfig.py`:
```python
import io

from ops.dbconfig import dbt_env_vars, session_pooler_url, write_github_env
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


def test_fresh_db_fixture_gives_an_empty_database(fresh_db):
    assert run_sql(fresh_db, "SELECT 1") == [(1,)]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd etl && ../venv/Scripts/python -m pytest tests/test_dbconfig.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'ops.dbconfig'`.

- [ ] **Step 4: Implement `etl/ops/dbconfig.py`**

```python
"""
Database connection settings derived from ONE secret: SUPABASE_URL.

Every pipeline step (ETL scripts, dbt, CI) derives what it needs from that
single URL, so a rotated password or a moved pooler host is fixed in exactly
one place.

CLI (used by CI to configure dbt):
    python -m ops.dbconfig --github-env
appends DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME and SUPABASE_SESSION_URL
to $GITHUB_ENV and masks the password in the Actions log.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.parse as urlparse

TRANSACTION_POOLER_PORT = 6543
SESSION_POOLER_PORT = 5432


def session_pooler_url(url: str | None) -> str | None:
    """Supabase's transaction pooler (6543) drops long-lived connections; the
    session pooler (5432, same host) keeps them. Long steps must use 5432."""
    if url and f":{TRANSACTION_POOLER_PORT}/" in url:
        return url.replace(f":{TRANSACTION_POOLER_PORT}/", f":{SESSION_POOLER_PORT}/")
    return url


def dbt_env_vars(url: str) -> dict[str, str]:
    """The DB_* variables dbt_project/profiles.yml reads, on the session pooler."""
    u = urlparse.urlparse(session_pooler_url(url))
    return {
        "DB_HOST": u.hostname or "",
        "DB_PORT": str(u.port or SESSION_POOLER_PORT),
        "DB_USER": urlparse.unquote(u.username or ""),
        "DB_PASSWORD": urlparse.unquote(u.password or ""),
        "DB_NAME": (u.path or "/postgres").lstrip("/") or "postgres",
    }


def write_github_env(url: str, env_file: str, out=sys.stdout) -> None:
    values = dbt_env_vars(url)
    values["SUPABASE_SESSION_URL"] = session_pooler_url(url)
    if values["DB_PASSWORD"]:
        print(f"::add-mask::{values['DB_PASSWORD']}", file=out)
    with open(env_file, "a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Derive DB settings from SUPABASE_URL")
    parser.add_argument("--github-env", action="store_true",
                        help="Append derived variables to $GITHUB_ENV")
    args = parser.parse_args(argv)
    url = os.getenv("SUPABASE_URL")
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    if args.github_env:
        env_file = os.getenv("GITHUB_ENV")
        if not env_file:
            print("GITHUB_ENV is not set (not running in GitHub Actions?)", file=sys.stderr)
            return 1
        write_github_env(url, env_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Point `refresh_all.py` at the shared module**

In `etl/refresh_all.py`, delete the local `session_pooler_url` function and replace `dbt_env` with:
```python
def dbt_env() -> dict:
    """Environment for dbt: DB_* derived from SUPABASE_URL on the session
    pooler (--full-refresh runs long CREATE TABLE AS statements that the
    transaction pooler would drop mid-build)."""
    env = dict(os.environ)
    env.update(dbt_env_vars(DB_URL))
    return env
```
Then add, after the `from dotenv import load_dotenv` import:
```python
from ops.dbconfig import dbt_env_vars, session_pooler_url
```
Finally, delete the now-unused `import urllib.parse as urlparse`.

- [ ] **Step 6: Start Docker Desktop if it isn't running, then run the tests**

Run: `docker info >/dev/null 2>&1 || "/c/Program Files/Docker/Docker/Docker Desktop.exe" &` then wait until `docker info` succeeds.
Run: `cd etl && ../venv/Scripts/python -m pytest -v` and `../venv/Scripts/python refresh_all.py --dry-run`
Expected: 5 passed; the dry run prints every step with `[dry-run] skipped`.

- [ ] **Step 7: Commit**

```bash
git add etl/pytest.ini etl/ops/__init__.py etl/ops/dbconfig.py etl/tests/__init__.py etl/tests/conftest.py etl/tests/dbutil.py etl/tests/test_dbconfig.py etl/refresh_all.py
git commit -m "Add ETL test harness and DB config"
git push origin main
```

---

### Task 2: Migration runner + `ops.pipeline_runs`

**Files:**
- Create: `etl/ops/migrate.py`, `database/migrations/007_ops_pipeline_runs.sql`, `etl/tests/test_migrate.py`

**Interfaces:**
- Consumes: `session_pooler_url` (Task 1), fixture `fresh_db`, `run_sql`.
- Produces: `ops.migrate.discover(directory) -> list[Path]`, `checksum(path) -> str`, `applied(conn) -> dict[str, str]`, `pending(conn, directory) -> list[Path]`, `changed(conn, directory) -> list[str]`, `up(conn, directory) -> list[str]`, `baseline(conn, through: str, directory) -> list[str]`, `connect(url)`; the table `ops.pipeline_runs(id, run_id, step, status, exit_code, rows_out, started_at, finished_at, error, details)`.

- [ ] **Step 1: Write the failing tests**

`etl/tests/test_migrate.py`:
```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd etl && ../venv/Scripts/python -m pytest tests/test_migrate.py -v`
Expected: `ImportError: cannot import name 'migrate' from 'ops'`.

- [ ] **Step 3: Write migration 007**

`database/migrations/007_ops_pipeline_runs.sql`:
```sql
-- ============================================================
-- MIGRATION 007 — Pipeline run ledger (ops.pipeline_runs)
-- ============================================================
-- One row per pipeline step (preflight, adzuna, ingest, transform, fx,
-- dbt, archive, retention), written by etl/ops/run_step.py and
-- refresh_all.py. Gives failure visibility beyond "read the log file"
-- and the numbers the failure email reports.
-- Idempotent.
-- ============================================================
BEGIN;

CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT        NOT NULL,   -- 'gh-<run id>-<attempt>' or 'local-<utc timestamp>'
    step        TEXT        NOT NULL,
    status      TEXT        NOT NULL CHECK (status IN ('success', 'failure')),
    exit_code   INTEGER,
    rows_out    BIGINT,                 -- value of the step's metric (see run_step.METRICS)
    started_at  TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    error       TEXT,                   -- last lines of output when the step failed
    details     JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS pipeline_runs_run_id_idx  ON ops.pipeline_runs (run_id);
CREATE INDEX IF NOT EXISTS pipeline_runs_started_idx ON ops.pipeline_runs (started_at DESC);

-- ops is internal: keep it away from Supabase's API roles (they only
-- exist on Supabase, hence the guard).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON SCHEMA ops FROM anon, authenticated';
    END IF;
END $$;

COMMIT;
```

- [ ] **Step 4: Implement `etl/ops/migrate.py`**

```python
"""
Versioned schema migrations.

Files in database/migrations named NNN_description.sql are applied in order
and recorded in ops.schema_migrations. Each file manages its own transaction
(BEGIN; ... COMMIT;) so a failure leaves nothing half-applied.

    python -m ops.migrate status
    python -m ops.migrate up
    python -m ops.migrate baseline 005   # mark 001..005 applied (run by hand earlier)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

import psycopg2

from ops.dbconfig import session_pooler_url

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
NAME_RE = re.compile(r"^(\d{3})_[\w-]+\.sql$")

TRACKING_DDL = """
CREATE SCHEMA IF NOT EXISTS ops;
CREATE TABLE IF NOT EXISTS ops.schema_migrations (
    filename   TEXT PRIMARY KEY,
    checksum   TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def connect(url: str):
    conn = psycopg2.connect(url)
    conn.autocommit = True  # each migration file controls its own transaction
    return conn


def checksum(path: Path) -> str:
    """SHA-256 of the file with line endings normalised (Windows checkouts use CRLF)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted((p for p in directory.iterdir() if NAME_RE.match(p.name)), key=lambda p: p.name)


def applied(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(TRACKING_DDL)
        cur.execute("SELECT filename, checksum FROM ops.schema_migrations")
        return dict(cur.fetchall())


def pending(conn, directory: Path = MIGRATIONS_DIR) -> list[Path]:
    done = applied(conn)
    return [p for p in discover(directory) if p.name not in done]


def changed(conn, directory: Path = MIGRATIONS_DIR) -> list[str]:
    done = applied(conn)
    return [p.name for p in discover(directory) if p.name in done and done[p.name] != checksum(p)]


def _record(conn, path: Path) -> None:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO ops.schema_migrations (filename, checksum) VALUES (%s, %s)",
                    (path.name, checksum(path)))


def up(conn, directory: Path = MIGRATIONS_DIR) -> list[str]:
    done = []
    for path in pending(conn, directory):
        try:
            with conn.cursor() as cur:
                cur.execute(path.read_text(encoding="utf-8"))
        except psycopg2.Error:
            with conn.cursor() as cur:
                cur.execute("ROLLBACK")  # leave no aborted transaction behind
            raise
        _record(conn, path)
        done.append(path.name)
    return done


def baseline(conn, through: str, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Record migrations numbered <= `through` as applied without running them."""
    limit = through.zfill(3)
    done = applied(conn)
    marked = []
    for path in discover(directory):
        if NAME_RE.match(path.name).group(1) > limit:
            break
        if path.name not in done:
            _record(conn, path)
            marked.append(path.name)
    return marked


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Apply database migrations")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("up")
    base = sub.add_parser("baseline")
    base.add_argument("through", help="last migration number already applied by hand, e.g. 005")
    args = parser.parse_args(argv)

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    conn = connect(url)
    try:
        if args.command == "status":
            done = applied(conn)
            for path in discover():
                print(f"  {'applied' if path.name in done else 'PENDING'}  {path.name}")
            for name in changed(conn):
                print(f"  WARNING: {name} changed after it was applied")
        elif args.command == "baseline":
            for name in baseline(conn, args.through):
                print(f"  baselined {name}")
        else:
            try:
                names = up(conn)
            except psycopg2.Error as exc:
                print(f"Migration failed: {exc}", file=sys.stderr)
                return 1
            print("\n".join(f"  applied {n}" for n in names) or "  nothing to apply")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd etl && ../venv/Scripts/python -m pytest -v`
Expected: all pass (7 new).

- [ ] **Step 6: Commit (the runner only; no CI workflow yet)**

```bash
git add etl/ops/migrate.py etl/tests/test_migrate.py database/migrations/007_ops_pipeline_runs.sql
git commit -m "Add migration runner and pipeline ledger table"
git push origin main
```

- [ ] **Step 7: Baseline production, then apply pending migrations (ask the owner first)**

Run: `cd etl && ../venv/Scripts/python -m ops.migrate status`, then `../venv/Scripts/python -m ops.migrate baseline 005`
Expected: 001–005 baselined. 006, 007 PENDING.

**STOP: ask the owner** whether to run 006 (it permanently deletes the 20 anonymous resume rows; the matching 20 storage files are removed through the Supabase Storage API with the service key). If yes: `../venv/Scripts/python -m ops.migrate up` applies 006 and 007, and then the 20 objects listed by 006's step-1 query are removed from the `resumes` bucket. If no: leave 006 out of the repo's pending set by moving it to `database/migrations/manual/` (not matched by the runner) and run `up` for 007.

Run afterwards: `../venv/Scripts/python -m ops.migrate status`
Expected: no PENDING lines.

---

### Task 3: Run ledger + step wrapper

**Files:**
- Create: `etl/ops/ledger.py`, `etl/ops/run_step.py`, `etl/tests/fixtures/pipeline_schema.sql`, `etl/tests/test_run_step.py`
- Modify: `etl/tests/conftest.py` (add the `pipeline_db` fixture), `etl/refresh_all.py` (record each step in the ledger)

**Interfaces:**
- Consumes: `session_pooler_url`, migration 007, `fresh_db`, `run_sql`.
- Produces: `ops.ledger.current_run_id(env=os.environ) -> str`, `record(url, *, run_id, step, status, started_at, finished_at, exit_code=None, rows_out=None, error=None, details=None) -> bool`, `fetch_run(url, run_id) -> list[dict]` (keys: step, status, exit_code, rows_out, error, details); `ops.run_step.METRICS: dict[str, str]`, `run_step.main(argv) -> int`; fixture `pipeline_db` (a URL whose database has `raw.jobs`, `staging.stg_jobs`, `staging.stg_job_skills`, and `ops.pipeline_runs`).

- [ ] **Step 1: Add the pipeline schema fixture**

`etl/tests/fixtures/pipeline_schema.sql` (the subset of `database/schema.sql` the ops tools touch, with identical column types):
```sql
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE raw.jobs (
    id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    search_role TEXT NOT NULL DEFAULT 'Data Engineer',
    country_code TEXT NOT NULL DEFAULT 'remote',
    raw_data JSONB NOT NULL,
    source TEXT NOT NULL DEFAULT 'adzuna',
    extracted_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT raw_jobs_unique UNIQUE (job_platform_id, country_code)
);

CREATE TABLE staging.stg_jobs (
    job_id SERIAL PRIMARY KEY,
    job_platform_id TEXT NOT NULL,
    search_role TEXT NOT NULL DEFAULT 'Data Engineer',
    country_code TEXT NOT NULL DEFAULT 'remote',
    title TEXT,
    job_posted_at TIMESTAMP,
    extracted_at TIMESTAMP,
    processed_at TIMESTAMP DEFAULT NOW(),
    raw_job_id INTEGER REFERENCES raw.jobs(id),
    source TEXT NOT NULL DEFAULT 'adzuna',
    CONSTRAINT stg_jobs_unique UNIQUE (job_platform_id, country_code)
);

CREATE TABLE staging.stg_job_skills (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES staging.stg_jobs(job_id) ON DELETE CASCADE,
    skill_id INTEGER,
    skill_name TEXT NOT NULL,
    mention_count INTEGER DEFAULT 1
);
```

Append to `etl/tests/conftest.py`:
```python
from pathlib import Path

from tests.dbutil import run_sql

_TESTS = Path(__file__).resolve().parent
_REPO = _TESTS.parents[1]


@pytest.fixture
def pipeline_db(fresh_db):
    run_sql(fresh_db, (_TESTS / "fixtures" / "pipeline_schema.sql").read_text(encoding="utf-8"))
    run_sql(fresh_db, (_REPO / "database" / "migrations" / "007_ops_pipeline_runs.sql").read_text(encoding="utf-8"))
    return fresh_db
```

- [ ] **Step 2: Write the failing tests**

`etl/tests/test_run_step.py`:
```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd etl && ../venv/Scripts/python -m pytest tests/test_run_step.py -v`
Expected: `ImportError: cannot import name 'ledger' from 'ops'`.

- [ ] **Step 4: Implement `etl/ops/ledger.py`**

```python
"""
Pipeline run ledger: one row per pipeline step in ops.pipeline_runs.

Writing to the ledger must never break the pipeline. When the database is
unreachable (often the very failure being reported), record() logs a
warning and returns False, and fetch_run() returns [].
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


def current_run_id(env=os.environ) -> str:
    if env.get("PIPELINE_RUN_ID"):
        return env["PIPELINE_RUN_ID"]
    if env.get("GITHUB_RUN_ID"):
        return f"gh-{env['GITHUB_RUN_ID']}-{env.get('GITHUB_RUN_ATTEMPT', '1')}"
    return "local-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def record(url, *, run_id, step, status, started_at, finished_at,
           exit_code=None, rows_out=None, error=None, details=None) -> bool:
    try:
        conn = psycopg2.connect(url, connect_timeout=10)
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ops.pipeline_runs
                       (run_id, step, status, exit_code, rows_out, started_at, finished_at, error, details)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (run_id, step, status, exit_code, rows_out, started_at, finished_at,
                     error, json.dumps(details or {})),
                )
        finally:
            conn.close()
        return True
    except Exception as exc:  # the ledger is best-effort by design
        logger.warning("ledger: could not record step %s (%s)", step, exc.__class__.__name__)
        return False


def fetch_run(url, run_id) -> list[dict]:
    try:
        conn = psycopg2.connect(url, connect_timeout=10)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT step, status, exit_code, rows_out, error, details
                       FROM ops.pipeline_runs WHERE run_id = %s ORDER BY started_at, id""",
                    (run_id,),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("ledger: could not read run %s (%s)", run_id, exc.__class__.__name__)
        return []
```

- [ ] **Step 5: Implement `etl/ops/run_step.py`**

```python
"""
Run one pipeline step as a subprocess and record it in the ledger.

    python -m ops.run_step --step ingest --metric raw_inserted_other -- python ingest_sources.py

Output streams live; the last lines are kept so a failure's cause reaches
the ledger (and the alert email). The child's exit code is returned
unchanged, so CI still sees the real result.
"""
from __future__ import annotations

import argparse
import collections
import os
import subprocess
import sys
from datetime import datetime, timezone

import psycopg2

from ops import ledger
from ops.dbconfig import session_pooler_url

TAIL_LINES = 40

# Each metric is evaluated after the step; %(since)s is the DB clock when
# the step started (DB time, so runner clock skew doesn't matter).
METRICS = {
    "raw_inserted": "SELECT count(*) FROM raw.jobs WHERE extracted_at >= %(since)s",
    "raw_inserted_adzuna": "SELECT count(*) FROM raw.jobs WHERE extracted_at >= %(since)s AND source = 'adzuna'",
    "raw_inserted_other": "SELECT count(*) FROM raw.jobs WHERE extracted_at >= %(since)s AND source <> 'adzuna'",
    "stg_processed": "SELECT count(*) FROM staging.stg_jobs WHERE processed_at >= %(since)s",
    "db_size_bytes": "SELECT pg_database_size(current_database())",
}


def _query_one(url, sql, params=None):
    try:
        conn = psycopg2.connect(url, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return None


def _run(cmd) -> tuple[int, str]:
    tail = collections.deque(maxlen=TAIL_LINES)
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        tail.append(line.rstrip("\n"))
    return proc.wait(), "\n".join(tail)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run a pipeline step and record it")
    parser.add_argument("--step", required=True)
    parser.add_argument("--metric", choices=sorted(METRICS))
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        parser.error("missing command after --")

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    since = _query_one(url, "SELECT now()") if (url and args.metric) else None
    started = datetime.now(timezone.utc)
    exit_code, tail = _run(cmd)
    finished = datetime.now(timezone.utc)

    if url:
        value = _query_one(url, METRICS[args.metric], {"since": since}) if since is not None else None
        ledger.record(
            url, run_id=ledger.current_run_id(), step=args.step,
            status="success" if exit_code == 0 else "failure",
            started_at=started, finished_at=finished, exit_code=exit_code,
            rows_out=value, error=None if exit_code == 0 else tail,
            details={"metric": args.metric} if args.metric else None,
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Record `refresh_all.py` steps in the ledger**

In `etl/refresh_all.py`:
- Add the imports `from datetime import datetime, timezone` and `from ops import ledger`.
- Add `os.environ.setdefault("PIPELINE_RUN_ID", ledger.current_run_id())` as the first line of `main()` after argument parsing.
- Replace `run_step` with:
```python
def run_step(name: str, cmd: list, cwd: Path, env: dict = None, dry_run: bool = False) -> bool:
    """Run a subprocess step, streaming output, and record it in the ledger."""
    logger.info("=" * 64)
    logger.info("STEP: %s", name)
    logger.info("  $ %s   (cwd=%s)", " ".join(cmd), cwd)
    logger.info("=" * 64)
    if dry_run:
        logger.info("  [dry-run] skipped")
        return True
    started = datetime.now(timezone.utc)
    result = subprocess.run(cmd, cwd=str(cwd), env=env)
    ledger.record(
        session_pooler_url(DB_URL), run_id=os.environ["PIPELINE_RUN_ID"], step=name,
        status="success" if result.returncode == 0 else "failure",
        started_at=started, finished_at=datetime.now(timezone.utc),
        exit_code=result.returncode,
        error=None if result.returncode == 0 else f"exit {result.returncode}; see refresh.log",
    )
    if result.returncode != 0:
        logger.error("STEP FAILED: %s (exit %d)", name, result.returncode)
        return False
    logger.info("STEP OK: %s", name)
    return True
```

- [ ] **Step 7: Run all tests; verify refresh_all still plans correctly**

Run: `cd etl && ../venv/Scripts/python -m pytest -v && ../venv/Scripts/python refresh_all.py --dry-run`
Expected: all pass; the dry run lists the steps.

- [ ] **Step 8: Commit**

```bash
git add etl/ops/ledger.py etl/ops/run_step.py etl/tests/fixtures/pipeline_schema.sql etl/tests/test_run_step.py etl/tests/conftest.py etl/refresh_all.py
git commit -m "Record pipeline steps in run ledger"
git push origin main
```

---

### Task 4: Preflight check

**Files:**
- Create: `etl/ops/preflight.py`, `etl/tests/test_preflight.py`

**Interfaces:**
- Consumes: `fresh_db`.
- Produces: `ops.preflight.Check(name, ok, detail)`, `diagnose_db_url(url) -> list[str]`, `check_dns(host) -> Check`, `check_db(url) -> Check`, `check_adzuna(app_id, app_key, http=requests) -> Check`, `run_checks(url, adzuna, env=os.environ) -> list[Check]`, `main(argv=None) -> int` (exit 1 on any non-Adzuna failure).

- [ ] **Step 1: Write the failing tests**

`etl/tests/test_preflight.py`:
```python
from ops import preflight

POOLER = "postgresql://postgres.ref:pw@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"


class FakeResp:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeHttp:
    def __init__(self, status_code):
        self.status_code = status_code
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append(params)
        return FakeResp(self.status_code)


def test_pooler_url_has_no_static_problems():
    assert preflight.diagnose_db_url(POOLER) == []


def test_direct_host_is_rejected_with_fix():
    problems = preflight.diagnose_db_url("postgresql://postgres:pw@db.abcd.supabase.co:5432/postgres")
    assert any("IPv6" in p and "pooler" in p for p in problems)


def test_missing_url_and_password_are_reported():
    assert preflight.diagnose_db_url(None) == ["SUPABASE_URL is empty or not set. Add it as a repository secret."]
    assert any("no password" in p for p in preflight.diagnose_db_url(POOLER.replace(":pw@", "@")))


def test_dns_check():
    assert preflight.check_dns("localhost").ok
    assert not preflight.check_dns("no-such-host.invalid").ok


def test_db_check_connects(fresh_db):
    assert preflight.check_db(fresh_db).ok


def test_wrong_password_names_the_cause(fresh_db):
    bad = fresh_db.replace(":test@", ":wrong@")
    check = preflight.check_db(bad)
    assert not check.ok
    assert "password" in check.detail.lower()
    assert "wrong" not in check.detail  # never echo credentials


def test_adzuna_check_outcomes():
    assert preflight.check_adzuna("id", "key", http=FakeHttp(200)).ok
    rejected = preflight.check_adzuna("id", "key", http=FakeHttp(401))
    assert not rejected.ok and "rejected" in rejected.detail
    assert "quota" in preflight.check_adzuna("id", "key", http=FakeHttp(429)).detail
    assert not preflight.check_adzuna(None, None, http=FakeHttp(200)).ok


def test_static_problems_skip_network_checks():
    checks = preflight.run_checks("postgresql://postgres:pw@db.abcd.supabase.co:5432/postgres", adzuna=False)
    assert [c.name for c in checks] == ["database url"]


def test_main_exit_codes(fresh_db, monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", fresh_db)
    assert preflight.main([]) == 0
    monkeypatch.setenv("SUPABASE_URL", "postgresql://postgres:pw@db.abcd.supabase.co:5432/postgres")
    assert preflight.main([]) == 1
    assert "IPv6" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd etl && ../venv/Scripts/python -m pytest tests/test_preflight.py -v`
Expected: `ImportError: cannot import name 'preflight' from 'ops'`.

- [ ] **Step 3: Implement `etl/ops/preflight.py`**

```python
"""
Pipeline preflight: verify credentials and connectivity BEFORE any step
runs, and say exactly what to fix. The scheduled pipeline failed for
months with the cause buried in a stack trace inside the first step; this
turns it into one readable line.

    python -m ops.preflight            # database checks (fatal)
    python -m ops.preflight --adzuna   # + Adzuna credential probe (warning only)
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import urllib.parse as urlparse
from dataclasses import dataclass

import psycopg2
import requests

ADZUNA_PROBE = "https://api.adzuna.com/v1/api/jobs/gb/search/1"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def diagnose_db_url(url: str | None) -> list[str]:
    """Problems visible in the URL itself, without touching the network."""
    if not url:
        return ["SUPABASE_URL is empty or not set. Add it as a repository secret."]
    problems = []
    u = urlparse.urlparse(url)
    if u.scheme not in ("postgres", "postgresql"):
        problems.append(f"URL scheme is '{u.scheme}', expected 'postgresql'.")
    host = u.hostname or ""
    if not host:
        problems.append("SUPABASE_URL has no host.")
    elif host.startswith("db.") and host.endswith(".supabase.co"):
        problems.append(
            f"{host} is Supabase's direct connection, which is IPv6-only, and GitHub "
            "Actions runners have no IPv6. Use the pooler connection string "
            "(host ends in .pooler.supabase.com) from Supabase > Connect."
        )
    try:
        port = u.port
    except ValueError:
        port = None
        problems.append("SUPABASE_URL has an invalid port.")
    if "supabase" in host and port not in (None, 5432, 6543):
        problems.append(f"Port {port} is unusual for Supabase (expected 5432 or 6543).")
    if not u.password:
        problems.append("SUPABASE_URL has no password.")
    return problems


def check_dns(host: str) -> Check:
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET)
    except socket.gaierror:
        return Check("dns", False, f"{host} has no IPv4 address.")
    return Check("dns", True, f"{host} resolves to {infos[0][4][0]}")


def check_db(url: str) -> Check:
    host = urlparse.urlparse(url).hostname
    try:
        conn = psycopg2.connect(url, connect_timeout=15)
    except psycopg2.OperationalError as exc:
        text = str(exc).lower()
        if "password authentication failed" in text:
            cause = "password authentication failed; the password in SUPABASE_URL is wrong (was it reset?)"
        elif "tenant or user not found" in text:
            cause = "the pooler user (postgres.<project-ref>) or the region host is wrong"
        elif "timeout" in text or "timed out" in text:
            cause = "connection timed out; is the Supabase project paused?"
        else:
            cause = "connection refused or rejected"
        return Check("database", False, f"Cannot connect to {host}: {cause}.")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()
    return Check("database", True, f"Connected to {host}")


def check_adzuna(app_id, app_key, http=requests) -> Check:
    if not app_id or not app_key:
        return Check("adzuna", False, "ADZUNA_APP_ID / ADZUNA_APP_KEY are not set.")
    try:
        resp = http.get(ADZUNA_PROBE, params={"app_id": app_id, "app_key": app_key,
                                              "results_per_page": 1, "what": "engineer"}, timeout=30)
    except requests.RequestException as exc:
        return Check("adzuna", False, f"Adzuna unreachable ({exc.__class__.__name__}).")
    if resp.status_code == 200:
        return Check("adzuna", True, "Adzuna credentials accepted")
    if resp.status_code in (401, 403):
        return Check("adzuna", False, f"Adzuna rejected the credentials (HTTP {resp.status_code}).")
    if resp.status_code == 429:
        return Check("adzuna", False, "Adzuna rate limit hit (HTTP 429); the daily/monthly quota may be used up.")
    return Check("adzuna", False, f"Adzuna returned HTTP {resp.status_code}.")


def run_checks(url, adzuna: bool, env=os.environ) -> list[Check]:
    problems = diagnose_db_url(url)
    checks = [Check("database url", not problems, " ".join(problems) or "Supabase URL looks valid")]
    if not problems:
        dns = check_dns(urlparse.urlparse(url).hostname)
        checks.append(dns)
        if dns.ok:
            checks.append(check_db(url))
    if adzuna:
        checks.append(check_adzuna(env.get("ADZUNA_APP_ID"), env.get("ADZUNA_APP_KEY")))
    return checks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check pipeline credentials and connectivity")
    parser.add_argument("--adzuna", action="store_true", help="also probe the Adzuna credentials")
    args = parser.parse_args(argv)
    checks = run_checks(os.getenv("SUPABASE_URL"), args.adzuna)
    for c in checks:
        print(f"[{'OK' if c.ok else 'FAIL':>4}] {c.name}: {c.detail}")
    fatal = [c for c in checks if not c.ok and c.name != "adzuna"]
    if any(not c.ok and c.name == "adzuna" for c in checks):
        print("::warning::Adzuna check failed; the Adzuna step will fail, other sources continue.")
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd etl && ../venv/Scripts/python -m pytest -v`
Expected: all pass.

- [ ] **Step 5: Run preflight against production (read-only)**

Run: `cd etl && ../venv/Scripts/python -m ops.preflight --adzuna`
Expected: every line `[  OK]`. This confirms the local `etl/.env` URL is the value the GitHub secret needs.

- [ ] **Step 6: Commit**

```bash
git add etl/ops/preflight.py etl/tests/test_preflight.py
git commit -m "Add pipeline preflight credential checks"
git push origin main
```

---

### Task 5: Storage retention

**Files:**
- Create: `etl/ops/retention.py`, `etl/tests/test_retention.py`

**Interfaces:**
- Consumes: `pipeline_db`, `run_sql`, `session_pooler_url`.
- Produces: `ops.retention.RETENTION_DAYS = 120`, `STRIP_AFTER_DAYS = 7`, `MAX_DELETE = 100_000`, `RetentionResult(stripped, deleted_stg, deleted_raw)`, `RetentionLimitExceeded`, `count_candidates(conn, days, strip_days) -> dict`, `apply(conn, days, strip_days, max_delete) -> RetentionResult`, `vacuum(url, full: bool) -> None`, `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing tests**

`etl/tests/test_retention.py`:
```python
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


def test_deletes_expired_jobs_with_skills_and_raw_rows(pipeline_db, conn):
    add_job(pipeline_db, "old", posted_days=200, extracted_days=5, skills=3)
    add_job(pipeline_db, "new", posted_days=30, extracted_days=5, skills=2)
    result = retention.apply(conn)
    assert (result.deleted_stg, result.deleted_raw) == (1, 1)
    assert count(pipeline_db, "staging.stg_jobs") == 1
    assert count(pipeline_db, "staging.stg_job_skills") == 2
    assert count(pipeline_db, "raw.jobs") == 1


def test_uses_extracted_at_when_posting_date_missing(pipeline_db, conn):
    add_job(pipeline_db, "undated-old", posted_days=None, extracted_days=150)
    add_job(pipeline_db, "undated-new", posted_days=None, extracted_days=10)
    assert retention.apply(conn).deleted_stg == 1


def test_deletes_old_orphan_raw_rows_only(pipeline_db, conn):
    add_job(pipeline_db, "orphan-old", extracted_days=130, processed=False)
    add_job(pipeline_db, "orphan-new", extracted_days=3, processed=False)
    assert retention.apply(conn).deleted_raw == 1
    assert run_sql(pipeline_db, "SELECT job_platform_id FROM raw.jobs") == [("orphan-new",)]


def test_refuses_when_expired_rows_exceed_max_delete(pipeline_db, conn):
    for i in range(3):
        add_job(pipeline_db, f"old{i}", posted_days=200, extracted_days=10)
    with pytest.raises(retention.RetentionLimitExceeded):
        retention.apply(conn, max_delete=2)
    assert count(pipeline_db, "staging.stg_jobs") == 3
    assert all(has_raw_payload(pipeline_db, rid) for (rid,) in run_sql(pipeline_db, "SELECT id FROM raw.jobs"))


def test_count_candidates_changes_nothing(pipeline_db, conn):
    add_job(pipeline_db, "old", posted_days=200, extracted_days=10)
    counts = retention.count_candidates(conn, retention.RETENTION_DAYS, retention.STRIP_AFTER_DAYS)
    assert counts == {"strip": 1, "expired_jobs": 1, "orphan_raw": 0}
    assert count(pipeline_db, "staging.stg_jobs") == 1


def test_main_dry_run_and_real_run(pipeline_db, monkeypatch, capsys):
    add_job(pipeline_db, "old", posted_days=200, extracted_days=10)
    monkeypatch.setenv("SUPABASE_URL", pipeline_db)
    assert retention.main(["--dry-run"]) == 0
    assert count(pipeline_db, "staging.stg_jobs") == 1
    assert retention.main([]) == 0
    assert count(pipeline_db, "staging.stg_jobs") == 0
    assert "db size" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd etl && ../venv/Scripts/python -m pytest tests/test_retention.py -v`
Expected: `ImportError: cannot import name 'retention' from 'ops'`.

- [ ] **Step 3: Implement `etl/ops/retention.py`**

```python
"""
Storage retention for the Supabase free tier (500 MB).

1. Strip the original source payload (`_raw`) from processed connector
   envelopes older than STRIP_AFTER_DAYS; stg_jobs already holds the
   cleaned copy.
2. Delete jobs older than RETENTION_DAYS (by posting date) from staging and
   raw, plus old raw rows that never transformed. Monthly trends survive in
   archive.skill_demand_history.
3. VACUUM so freed space is reused (VACUUM FULL returns it; run weekly).

    python -m ops.retention --dry-run
    python -m ops.retention [--vacuum-full] [--max-delete N]

Known Phase-0 limitation: a feed that keeps listing a job posted >120 days
ago re-ingests it daily (the raw row is gone). Phase 1's job lifecycle
(first/last seen) replaces this rule.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import psycopg2

from ops.dbconfig import session_pooler_url

RETENTION_DAYS = 120
STRIP_AFTER_DAYS = 7
MAX_DELETE = 100_000

STRIP_WHERE = """r.raw_data ? '_raw'
    AND r.extracted_at < now() - make_interval(days => %(strip_days)s)
    AND EXISTS (SELECT 1 FROM staging.stg_jobs s WHERE s.raw_job_id = r.id)"""
EXPIRED_WHERE = "COALESCE(s.job_posted_at, s.extracted_at) < now() - make_interval(days => %(days)s)"
ORPHAN_WHERE = """r.extracted_at < now() - make_interval(days => %(days)s)
    AND NOT EXISTS (SELECT 1 FROM staging.stg_jobs s WHERE s.raw_job_id = r.id)"""


@dataclass
class RetentionResult:
    stripped: int
    deleted_stg: int
    deleted_raw: int


class RetentionLimitExceeded(RuntimeError):
    pass


def count_candidates(conn, days: int, strip_days: int) -> dict:
    params = {"days": days, "strip_days": strip_days}
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM raw.jobs r WHERE {STRIP_WHERE}", params)
        strip = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM staging.stg_jobs s WHERE {EXPIRED_WHERE}", params)
        expired = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM raw.jobs r WHERE {ORPHAN_WHERE}", params)
        orphans = cur.fetchone()[0]
    conn.rollback()
    return {"strip": strip, "expired_jobs": expired, "orphan_raw": orphans}


def apply(conn, days: int = RETENTION_DAYS, strip_days: int = STRIP_AFTER_DAYS,
          max_delete: int = MAX_DELETE) -> RetentionResult:
    """All changes in one transaction: either everything or nothing."""
    params = {"days": days, "strip_days": strip_days}
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM staging.stg_jobs s WHERE {EXPIRED_WHERE}", params)
            expired = cur.fetchone()[0]
            if expired > max_delete:
                raise RetentionLimitExceeded(
                    f"{expired} expired jobs exceeds --max-delete {max_delete}; "
                    "check the counts with --dry-run, then rerun with a higher limit."
                )
            cur.execute(f"UPDATE raw.jobs r SET raw_data = r.raw_data - '_raw' WHERE {STRIP_WHERE}", params)
            stripped = cur.rowcount
            cur.execute(f"""CREATE TEMP TABLE expired_jobs ON COMMIT DROP AS
                            SELECT s.job_id, s.raw_job_id FROM staging.stg_jobs s WHERE {EXPIRED_WHERE}""", params)
            cur.execute("DELETE FROM staging.stg_jobs s USING expired_jobs e WHERE s.job_id = e.job_id")
            deleted_stg = cur.rowcount
            cur.execute("DELETE FROM raw.jobs r USING expired_jobs e WHERE r.id = e.raw_job_id")
            deleted_raw = cur.rowcount
            cur.execute(f"DELETE FROM raw.jobs r WHERE {ORPHAN_WHERE}", params)
            deleted_raw += cur.rowcount
    return RetentionResult(stripped, deleted_stg, deleted_raw)


def vacuum(url: str, full: bool) -> None:
    conn = psycopg2.connect(url)
    conn.autocommit = True  # VACUUM cannot run inside a transaction
    try:
        with conn.cursor() as cur:
            options = "FULL, ANALYZE" if full else "ANALYZE"
            cur.execute(f"VACUUM ({options}) raw.jobs, staging.stg_jobs, staging.stg_job_skills")
    finally:
        conn.close()


def db_size_mb(conn) -> float:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database())")
        size = cur.fetchone()[0]
    conn.rollback()
    return round(size / 1024 / 1024, 1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Apply storage retention")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--vacuum-full", action="store_true")
    parser.add_argument("--days", type=int, default=RETENTION_DAYS)
    parser.add_argument("--max-delete", type=int, default=MAX_DELETE)
    args = parser.parse_args(argv)

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    conn = psycopg2.connect(url)
    try:
        if args.dry_run:
            print(f"would change: {count_candidates(conn, args.days, STRIP_AFTER_DAYS)}")
            print(f"db size: {db_size_mb(conn)} MB")
            return 0
        try:
            result = apply(conn, args.days, STRIP_AFTER_DAYS, args.max_delete)
        except RetentionLimitExceeded as exc:
            print(f"Retention refused: {exc}", file=sys.stderr)
            return 1
        print(f"stripped payloads: {result.stripped}, deleted jobs: {result.deleted_stg}, "
              f"deleted raw rows: {result.deleted_raw}")
    finally:
        conn.close()
    vacuum(url, full=args.vacuum_full)
    conn = psycopg2.connect(url)
    try:
        print(f"db size: {db_size_mb(conn)} MB")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd etl && ../venv/Scripts/python -m pytest -v`
Expected: all pass.

- [ ] **Step 5: Dry run against production (read-only)**

Run: `cd etl && ../venv/Scripts/python -m ops.retention --dry-run`
Expected: counts printed and db size ≈ 241 MB. Record the counts in the task report. If `expired_jobs` > 100,000, raise it with the owner before CI runs retention.

- [ ] **Step 6: Commit**

```bash
git add etl/ops/retention.py etl/tests/test_retention.py
git commit -m "Add storage retention for free tier"
git push origin main
```

---

### Task 6: Archive step + failure notification

**Files:**
- Create: `etl/ops/archive.py`, `etl/ops/notify.py`, `etl/tests/test_archive.py`, `etl/tests/test_notify.py`

**Interfaces:**
- Consumes: `ledger.fetch_run`, `ledger.current_run_id`, `session_pooler_url`, `fresh_db`.
- Produces: `ops.archive.archive(url) -> None`, `archive.main() -> int`; `ops.notify.FAILED_OUTCOMES = {"failure", "cancelled"}`, `parse_results(text) -> dict[str, str]`, `build_summary(results, ledger_rows, run_url=None) -> tuple[str, str, bool]`, `send_via_resend(api_key, to, subject, text, http=requests, sender=DEFAULT_SENDER) -> None`, `main(argv=None, env=None) -> int`.

- [ ] **Step 1: Write the failing tests**

`etl/tests/test_archive.py`:
```python
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
```

`etl/tests/test_notify.py`:
```python
import pytest

from ops import notify

ROWS = [
    {"step": "ingest", "status": "success", "exit_code": 0, "rows_out": 412,
     "error": None, "details": {"metric": "raw_inserted_other"}},
    {"step": "adzuna", "status": "failure", "exit_code": 1, "rows_out": 0,
     "error": "Traceback...\nHTTPError: 401 Unauthorized", "details": {"metric": "raw_inserted_adzuna"}},
]


def test_parse_results():
    assert notify.parse_results("a=success, b=failure,") == {"a": "success", "b": "failure"}
    with pytest.raises(ValueError):
        notify.parse_results("broken")


def test_summary_all_ok():
    subject, body, failed = notify.build_summary({"ingest": "success", "adzuna": "skipped"}, ROWS[:1])
    assert subject == "[Jobwise pipeline] OK"
    assert failed is False
    assert "ingest: raw_inserted_other=412" in body


def test_summary_failure_includes_error_tail_and_link():
    subject, body, failed = notify.build_summary(
        {"adzuna": "failure", "ingest": "success", "dbt": "cancelled"}, ROWS, "https://gh/run/1")
    assert failed is True
    assert subject == "[Jobwise pipeline] FAILED: adzuna, dbt"
    assert "401 Unauthorized" in body
    assert "https://gh/run/1" in body


def test_send_via_resend_posts_payload():
    sent = {}

    class Resp:
        def raise_for_status(self):
            pass

    class Http:
        def post(self, url, json, headers, timeout):
            sent.update(url=url, json=json, headers=headers)
            return Resp()

    notify.send_via_resend("key", "me@example.com", "subj", "body", http=Http())
    assert sent["url"] == notify.RESEND_ENDPOINT
    assert sent["json"]["to"] == ["me@example.com"]
    assert sent["headers"]["Authorization"] == "Bearer key"


def test_main_without_resend_key_still_fails_run(capsys):
    code = notify.main(["--results", "preflight=failure"], env={})
    out = capsys.readouterr().out
    assert code == 1
    assert "FAILED: preflight" in out
    assert "RESEND_API_KEY" in out


def test_main_sends_on_failure(monkeypatch):
    captured = []
    monkeypatch.setattr(notify, "send_via_resend", lambda *a, **k: captured.append(a))
    env = {"RESEND_API_KEY": "k", "ALERT_EMAIL": "me@example.com"}
    assert notify.main(["--results", "ingest=failure"], env=env) == 1
    assert captured and captured[0][2].startswith("[Jobwise pipeline] FAILED")
    captured.clear()
    assert notify.main(["--results", "ingest=success"], env=env) == 0
    assert captured == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd etl && ../venv/Scripts/python -m pytest tests/test_archive.py tests/test_notify.py -v`
Expected: `ImportError` for `archive` and `notify`.

- [ ] **Step 3: Implement `etl/ops/archive.py`**

```python
"""Snapshot today's skill demand into archive.skill_demand_history.

archive_skill_demand() replaces a same-day snapshot (migration 005), so
running it after every successful mart rebuild keeps today's point fresh.
"""
import os
import sys

import psycopg2

from ops.dbconfig import session_pooler_url


def archive(url: str) -> None:
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT archive_skill_demand()")
    finally:
        conn.close()


def main() -> int:
    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    archive(url)
    print("Archived today's skill-demand snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Implement `etl/ops/notify.py`**

```python
"""
Pipeline summary + failure alert email (Resend free tier).

    python -m ops.notify --results "preflight=success,adzuna=skipped,ingest=failure,..."

--results comes from the workflow's step outcomes, so the alert still goes
out when the database itself is down (the ledger then can't be read).
Without a verified domain, Resend's onboarding@resend.dev sender can only
deliver to the Resend account's own email, which is what ALERT_EMAIL is.
Exits 1 when any step failed so the workflow run shows as failed.
"""
from __future__ import annotations

import argparse
import os
import sys

import requests

from ops import ledger
from ops.dbconfig import session_pooler_url

RESEND_ENDPOINT = "https://api.resend.com/emails"
DEFAULT_SENDER = "Jobwise Pipeline <onboarding@resend.dev>"
FAILED_OUTCOMES = {"failure", "cancelled"}
ERROR_CHARS = 3000


def parse_results(text: str) -> dict[str, str]:
    results = {}
    for piece in filter(None, (p.strip() for p in text.split(","))):
        step, sep, outcome = piece.partition("=")
        if not sep or not step:
            raise ValueError(f"bad --results entry: {piece!r} (expected step=outcome)")
        results[step.strip()] = outcome.strip() or "skipped"
    return results


def build_summary(results, ledger_rows, run_url=None):
    failed = [step for step, outcome in results.items() if outcome in FAILED_OUTCOMES]
    subject = "[Jobwise pipeline] " + ("FAILED: " + ", ".join(failed) if failed else "OK")
    lines = ["Step outcomes:"]
    lines += [f"  {step:<10} {outcome}" for step, outcome in results.items()]
    metrics = [r for r in ledger_rows if r.get("rows_out") is not None]
    if metrics:
        lines += ["", "Metrics:"]
        lines += [f"  {r['step']}: {(r.get('details') or {}).get('metric', 'rows')}={r['rows_out']}"
                  for r in metrics]
    errors = {r["step"]: r["error"] for r in ledger_rows if r.get("error")}
    for step in failed:
        if step in errors:
            lines += ["", f"--- {step}: last output ---", errors[step][-ERROR_CHARS:]]
    if run_url:
        lines += ["", f"Run: {run_url}"]
    return subject, "\n".join(lines), bool(failed)


def send_via_resend(api_key, to, subject, text, http=requests, sender=DEFAULT_SENDER):
    resp = http.post(RESEND_ENDPOINT, json={"from": sender, "to": [to], "subject": subject, "text": text},
                     headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    resp.raise_for_status()


def main(argv=None, env=None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Summarise a pipeline run; email on failure")
    parser.add_argument("--results", required=True, help="comma-separated step=outcome pairs")
    parser.add_argument("--always", action="store_true", help="email even when every step passed")
    args = parser.parse_args(argv)

    results = parse_results(args.results)
    url = session_pooler_url(env.get("SUPABASE_URL"))
    rows = ledger.fetch_run(url, ledger.current_run_id(env)) if url else []
    run_url = None
    if env.get("GITHUB_RUN_ID"):
        run_url = f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/{env.get('GITHUB_REPOSITORY')}/actions/runs/{env['GITHUB_RUN_ID']}"
    subject, body, has_failure = build_summary(results, rows, run_url)
    print(subject)
    print(body)

    if has_failure or args.always:
        key, to = env.get("RESEND_API_KEY"), env.get("ALERT_EMAIL")
        if key and to:
            try:
                send_via_resend(key, to, subject, body)
            except requests.RequestException as exc:
                print(f"::warning::Alert email failed: {exc.__class__.__name__}")
        else:
            print("::warning::RESEND_API_KEY / ALERT_EMAIL not set; no email sent")
    return 1 if has_failure else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd etl && ../venv/Scripts/python -m pytest -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add etl/ops/archive.py etl/ops/notify.py etl/tests/test_archive.py etl/tests/test_notify.py
git commit -m "Add archive step and failure email alerts"
git push origin main
```

---

### Task 7: CI workflows (daily pipeline, migrations, tests)

**Files:**
- Rewrite: `.github/workflows/etl_pipeline.yml`
- Create: `.github/workflows/migrate.yml`, `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: every `ops` CLI above; the secrets `SUPABASE_URL`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_API_KEY`, `THEMUSE_API_KEY`, `USAJOBS_API_KEY`, `USAJOBS_USER_AGENT`, `RESEND_API_KEY`, `ALERT_EMAIL`.
- Produces: the daily run, the migration run on push, and tests on push.

- [ ] **Step 1: Confirm the flags the workflow passes exist**

Run: `cd etl && ../venv/Scripts/python extractor.py --help && ../venv/Scripts/python ingest_sources.py --help`
Expected: both list `--test`; the extractor lists `--days`, `--pages`, `--delay`. If `ingest_sources.py` lacks `--test`, drop `$TEST_FLAG` from the ingest step below.

- [ ] **Step 2: Rewrite `.github/workflows/etl_pipeline.yml`**

```yaml
name: ETL Pipeline

# One job, many steps: per-job setup counts against the 2,000 Actions
# minutes a private repo gets, and steps can gate each other on outcome.
on:
  schedule:
    - cron: '0 3 * * 1'        # Monday: everything incl. Adzuna (weekly, fits its quota)
    - cron: '0 3 * * 0,2-6'    # Other days: every non-Adzuna source
  workflow_dispatch:
    inputs:
      adzuna:
        description: 'Include Adzuna extraction'
        type: boolean
        default: false
      test_mode:
        description: 'Test mode (limited data)'
        type: boolean
        default: false
      vacuum_full:
        description: 'VACUUM FULL after retention'
        type: boolean
        default: false

concurrency:
  group: etl-pipeline
  cancel-in-progress: false

env:
  PYTHON_VERSION: '3.11'
  PYTHONUNBUFFERED: '1'
  SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
  ADZUNA_APP_ID: ${{ secrets.ADZUNA_APP_ID }}
  ADZUNA_APP_KEY: ${{ secrets.ADZUNA_APP_KEY }}
  JOOBLE_API_KEY: ${{ secrets.JOOBLE_API_KEY }}
  THEMUSE_API_KEY: ${{ secrets.THEMUSE_API_KEY }}
  USAJOBS_API_KEY: ${{ secrets.USAJOBS_API_KEY }}
  USAJOBS_USER_AGENT: ${{ secrets.USAJOBS_USER_AGENT }}
  RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
  ALERT_EMAIL: ${{ secrets.ALERT_EMAIL }}

jobs:
  pipeline:
    name: Daily pipeline
    runs-on: ubuntu-latest
    timeout-minutes: 120
    defaults:
      run:
        working-directory: etl
    env:
      WEEKLY: ${{ github.event.schedule == '0 3 * * 1' || github.event.inputs.adzuna == 'true' }}
      TEST_FLAG: ${{ github.event.inputs.test_mode == 'true' && '--test' || '' }}
      FULL_VACUUM: ${{ (github.event.schedule == '0 3 * * 1' || github.event.inputs.vacuum_full == 'true') && '--vacuum-full' || '' }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Preflight (credentials + connectivity)
        id: preflight
        run: python -m ops.run_step --step preflight -- python -m ops.preflight ${{ env.WEEKLY == 'true' && '--adzuna' || '' }}

      - name: Extract (Adzuna, weekly)
        id: adzuna
        if: steps.preflight.outcome == 'success' && env.WEEKLY == 'true'
        continue-on-error: true
        run: python -m ops.run_step --step adzuna --metric raw_inserted_adzuna -- python extractor.py --days 60 --pages 3 --delay 1.5 $TEST_FLAG

      - name: Ingest (remote boards, Jooble, ...)
        id: ingest
        if: steps.preflight.outcome == 'success'
        continue-on-error: true
        run: python -m ops.run_step --step ingest --metric raw_inserted_other -- python ingest_sources.py $TEST_FLAG

      - name: Transform (taxonomy skill extraction)
        id: transform
        if: steps.adzuna.outcome == 'success' || steps.ingest.outcome == 'success'
        run: |
          export SUPABASE_URL="$(python -c 'import os; from ops.dbconfig import session_pooler_url; print(session_pooler_url(os.environ["SUPABASE_URL"]))')"
          python -m ops.run_step --step transform --metric stg_processed -- python transformer.py --batch-size 500 --fast-only

      - name: Currency rates
        id: fx
        if: steps.transform.outcome == 'success'
        continue-on-error: true
        run: python -m ops.run_step --step fx -- python fetch_currency_rates.py

      - name: Configure dbt connection
        if: steps.preflight.outcome == 'success' && steps.transform.outcome != 'failure'
        run: python -m ops.dbconfig --github-env

      - name: Build marts (dbt)
        id: dbt
        if: steps.preflight.outcome == 'success' && steps.transform.outcome != 'failure'
        working-directory: dbt_project
        env:
          PYTHONPATH: ../etl
        run: |
          dbt deps --profiles-dir .
          python -m ops.run_step --step dbt -- dbt run --profiles-dir . --target dev --full-refresh
          python -m ops.run_step --step dbt_test -- dbt test --profiles-dir . --target dev

      - name: Archive skill-demand snapshot
        id: archive
        if: steps.dbt.outcome == 'success' && github.event_name == 'schedule'
        run: python -m ops.run_step --step archive -- python -m ops.archive

      - name: Retention (storage budget)
        id: retention
        if: steps.preflight.outcome == 'success' && steps.transform.outcome != 'failure'
        continue-on-error: true
        run: python -m ops.run_step --step retention --metric db_size_bytes -- python -m ops.retention $FULL_VACUUM

      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: pipeline-logs
          path: etl/*.log
          retention-days: 7

      - name: Summary and failure alert
        if: always()
        run: >-
          python -m ops.notify --results
          "preflight=${{ steps.preflight.outcome }},adzuna=${{ steps.adzuna.outcome }},ingest=${{ steps.ingest.outcome }},transform=${{ steps.transform.outcome }},fx=${{ steps.fx.outcome }},dbt=${{ steps.dbt.outcome }},archive=${{ steps.archive.outcome }},retention=${{ steps.retention.outcome }}"
```

- [ ] **Step 3: Create `.github/workflows/migrate.yml`**

```yaml
name: Database migrations

on:
  push:
    branches: [main]
    paths: ['database/migrations/**']
  workflow_dispatch:

concurrency:
  group: db-migrations
  cancel-in-progress: false

jobs:
  migrate:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: etl
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install psycopg2-binary
      - run: python -m ops.preflight
      - run: python -m ops.migrate status
      - run: python -m ops.migrate up
```

- [ ] **Step 4: Create `.github/workflows/tests.yml`**

```yaml
name: Tests

on:
  push:
    branches: [main]
    paths: ['etl/**', 'backend/**', 'database/**', '.github/workflows/tests.yml']
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 10
    env:
      TEST_DATABASE_URL: postgresql://postgres:test@localhost:5432/postgres
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r etl/requirements.txt -r backend/requirements.txt
      - name: ETL tests
        working-directory: etl
        run: python -m pytest -q
      - name: Backend tests
        working-directory: backend
        run: python -m pytest -q
```
Until Task 9 adds `backend/tests`, pytest exits 5 ("no tests collected"). Add `|| [ $? -eq 5 ]` after `python -m pytest -q` in the backend step for now, and remove it in Task 9.

- [ ] **Step 5: Lint the workflows**

Run: `docker run --rm -v "$(pwd -W 2>/dev/null || pwd)":/repo -w /repo rhysd/actionlint:latest -color`
Expected: no errors. (Warnings about shellcheck style in inline scripts may be fixed or left alone; errors must be zero.)

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/etl_pipeline.yml .github/workflows/migrate.yml .github/workflows/tests.yml
git commit -m "Daily decoupled pipeline with alerts and tests"
git push origin main
```
Expected after the push: the `Tests` workflow runs green. `ETL Pipeline` and `Database migrations` keep failing at preflight until the owner updates the `SUPABASE_URL` secret. The preflight output line says exactly that.

---

### Task 8: Keep-warm on Cloudflare Workers

**Files:**
- Create: `infra/keepwarm/worker.js`, `infra/keepwarm/worker.test.js`, `infra/keepwarm/package.json`, `infra/keepwarm/wrangler.toml`

**Interfaces:**
- Produces: `ping(env, fetchImpl = fetch) -> Promise<{ok, status?, error?, ms}>`; a default export with a `scheduled(event, env, ctx)` handler.

- [ ] **Step 1: Write the failing test**

`infra/keepwarm/package.json`:
```json
{
  "name": "jobwise-keepwarm",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test",
    "deploy": "npx wrangler deploy"
  }
}
```

`infra/keepwarm/worker.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, { ping } from './worker.js';

test('ping reports a healthy endpoint', async () => {
  const calls = [];
  const fakeFetch = async (url) => { calls.push(url); return { ok: true, status: 200 }; };
  const result = await ping({ HEALTH_URL: 'https://api.example.com/health' }, fakeFetch);
  assert.equal(result.ok, true);
  assert.equal(result.status, 200);
  assert.deepEqual(calls, ['https://api.example.com/health']);
});

test('ping reports failure instead of throwing', async () => {
  const result = await ping({ HEALTH_URL: 'https://x.test' }, async () => { throw new Error('boom'); });
  assert.equal(result.ok, false);
  assert.match(result.error, /boom/);
});

test('scheduled handler hands the ping to waitUntil', async () => {
  let waited;
  globalThis.fetch = async () => ({ ok: true, status: 200 });
  await worker.scheduled({}, { HEALTH_URL: 'https://x.test' }, { waitUntil: (p) => { waited = p; } });
  assert.equal((await waited).ok, true);
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd infra/keepwarm && node --test`
Expected: FAIL, `Cannot find module ... worker.js`.

- [ ] **Step 3: Implement the worker and its config**

`infra/keepwarm/worker.js`:
```js
// Pings the API's /health on a cron so Render's free instance never sleeps
// (it spins down after 15 idle minutes). Replaces the GitHub Actions
// keep-warm, which would burn ~8,600 of a private repo's 2,000 monthly minutes.
export async function ping(env, fetchImpl = fetch) {
  const started = Date.now();
  try {
    const res = await fetchImpl(env.HEALTH_URL, { signal: AbortSignal.timeout(60_000) });
    return { ok: res.ok, status: res.status, ms: Date.now() - started };
  } catch (err) {
    return { ok: false, error: String(err), ms: Date.now() - started };
  }
}

export default {
  async scheduled(event, env, ctx) {
    const result = ping(env).then((r) => {
      console.log(JSON.stringify({ keepwarm: r }));
      return r;
    });
    ctx.waitUntil(result);
  },
};
```

`infra/keepwarm/wrangler.toml`:
```toml
name = "jobwise-keepwarm"
main = "worker.js"
compatibility_date = "2026-09-01"

[triggers]
crons = ["*/10 * * * *"]  # Render sleeps after 15 idle minutes

[vars]
HEALTH_URL = "https://skill-hunt.onrender.com/health"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd infra/keepwarm && node --test`
Expected: 3 passing.

- [ ] **Step 5: Commit**

```bash
git add infra/keepwarm
git commit -m "Add Cloudflare Worker keep-warm cron"
git push origin main
```
`.github/workflows/keep_warm.yml` stays until the owner deploys the Worker (`cd infra/keepwarm && npx wrangler login && npx wrangler deploy`). Delete it after that, **before** the repo goes private.

---

### Task 9: Stop storing dead public resume URLs

**Files:**
- Modify: `backend/app/storage.py:52-82`, `backend/app/routers/resume.py:263-270`
- Create: `database/migrations/008_clear_resume_public_urls.sql`, `backend/pytest.ini`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_storage.py`
- Modify: `.github/workflows/tests.yml` (remove the exit-5 allowance)

**Interfaces:**
- Produces: `app.storage.upload_resume_file(file_bytes: bytes, original_filename: str) -> str` (storage path only).

- [ ] **Step 1: Backend test harness**

`backend/pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
asyncio_mode = auto
```
`backend/tests/__init__.py`: empty.
`backend/tests/conftest.py`:
```python
import os

# Settings requires a DB URL at import time; tests never connect with it.
os.environ.setdefault("SUPABASE_URL", "postgresql://test:test@localhost:5432/test")
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_storage.py`:
```python
import re

from app import storage


class FakeBucket:
    def __init__(self):
        self.uploads = []

    def upload(self, path, data, options):
        self.uploads.append((path, data, options))

    def get_public_url(self, path):
        raise AssertionError("resumes live in a private bucket; never build public URLs")


class FakeClient:
    def __init__(self):
        self.bucket = FakeBucket()
        self.storage = self

    def from_(self, name):
        assert name == "resumes"
        return self.bucket


async def test_upload_returns_only_the_storage_path(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(storage, "_get_client", lambda: client)
    path = await storage.upload_resume_file(b"%PDF-1.7", "cv.pdf")
    assert re.fullmatch(r"\d{4}/\d{2}/[0-9a-f-]{36}_cv\.pdf", path)
    (_, data, options), = client.bucket.uploads
    assert data == b"%PDF-1.7"
    assert options["content-type"] == "application/pdf"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd backend && ./venv/Scripts/python -m pytest -v`
Expected: FAIL with `AssertionError: resumes live in a private bucket...` (raised by `get_public_url`).

- [ ] **Step 4: Implement**

In `backend/app/storage.py`, replace `_do_upload` and `upload_resume_file` with:
```python
def _do_upload(file_bytes: bytes, storage_path: str, content_type: str) -> None:
    """Blocking upload — always run via asyncio.to_thread."""
    client = _get_client()
    # file_options values become HTTP headers, so they must be strings
    # ("upsert": False would raise inside the header encoder).
    client.storage.from_(BUCKET_NAME).upload(
        storage_path,
        file_bytes,
        {"content-type": content_type, "upsert": "false"},
    )


async def upload_resume_file(file_bytes: bytes, original_filename: str) -> str:
    """
    Upload a resume to the PRIVATE `resumes` bucket and return its storage
    path. No URL is returned: public URLs don't work on a private bucket,
    and any future download must use a short-lived signed URL instead.
    """
    from pathlib import Path
    ext = Path(original_filename).suffix.lower()
    content_type = MIME_TYPES.get(ext, "application/octet-stream")

    date_prefix = datetime.utcnow().strftime("%Y/%m")
    storage_path = f"{date_prefix}/{uuid.uuid4()}_{original_filename}"

    await asyncio.to_thread(_do_upload, file_bytes, storage_path, content_type)
    return storage_path
```
Remove `Tuple` from the `typing` import if it becomes unused.

In `backend/app/routers/resume.py` `_persist_analysis`:
- Delete the line `storage_url = None`.
- Change the upload line to `storage_path = await upload_resume_file(file_bytes, filename)`.
- In the INSERT argument list, replace `storage_path, storage_url, user_id,` with `storage_path, None, user_id,`. The column stays in place; it is always NULL from now on.

`database/migrations/008_clear_resume_public_urls.sql`:
```sql
-- ============================================================
-- MIGRATION 008 — Clear dead public resume URLs
-- ============================================================
-- The `resumes` bucket is private, so the public URLs stored in
-- resume_uploads.storage_url never worked (HTTP 400/403) and must not be
-- handed out. The API stops writing them (backend/app/storage.py); this
-- clears the old ones. storage_path remains the reference to the file.
-- Idempotent.
-- ============================================================
BEGIN;
UPDATE public.resume_uploads SET storage_url = NULL WHERE storage_url IS NOT NULL;
COMMIT;
```

In `.github/workflows/tests.yml`, change the backend step's run line back to `python -m pytest -q`.

- [ ] **Step 5: Run the tests and check the app imports**

Run: `cd backend && ./venv/Scripts/python -m pytest -v && ./venv/Scripts/python -c "import app.main"`
Expected: 1 passed; the import succeeds.

- [ ] **Step 6: Apply 008 to production and commit**

Run: `cd etl && ../venv/Scripts/python -m ops.migrate up`
Expected: `applied 008_clear_resume_public_urls.sql`. When pushed, the migrate workflow finds nothing pending, or fails at preflight until the secret is fixed; both are harmless.

```bash
git add backend/app/storage.py backend/app/routers/resume.py backend/pytest.ini backend/tests database/migrations/008_clear_resume_public_urls.sql .github/workflows/tests.yml
git commit -m "Stop storing dead public resume URLs"
git push origin main
```

---

### Task 10: Owner hand-off: Adzuna draft, CLAUDE.md, manual steps

**Files:**
- Create: `docs/ops/adzuna-licence-request.md`
- Modify: `CLAUDE.md` (Roadmap status, Architecture, Conventions, Pending manual steps)

- [ ] **Step 1: Write `docs/ops/adzuna-licence-request.md`**

It contains a short cover note (send from the owner's email to Adzuna's API/partnership contact listed on developer.adzuna.com) and this draft:

```text
Subject: Commercial / publisher licence for the Adzuna API — Jobwise

Hello Adzuna team,

I'm the developer of Jobwise (working name), a job-search product for software
and data professionals in Pakistan and India who look for remote roles. We
currently use the Adzuna API (app id <ADZUNA_APP_ID>) to show job listings and
to compute aggregate skill-demand statistics (e.g. "Python appears in 62% of
Data Engineer postings in the UK").

We're preparing to launch paid plans and want to make sure our use is properly
licensed. Could you let me know:

1. Whether you offer a commercial or publisher licence that covers showing
   Adzuna listings (with the "Jobs by Adzuna" attribution and links back) inside
   a paid product, and deriving aggregate, non-identifying statistics from them;
2. The terms, costs, and any traffic or attribution requirements; and
3. Whether higher rate limits are available (we currently make roughly 800
   requests per week across 17 countries).

Happy to share more detail or a demo.

Best regards,
<Your name>
<Product URL, once live>
```

- [ ] **Step 2: Update `CLAUDE.md`**

- Roadmap row 0: `**In progress**`. Add a sub-list of completed pieces (ops package, migrations 007–008, daily workflow, keep-warm Worker, resume URL cleanup).
- Architecture: add `etl/ops/` (preflight, migrate, ledger/run_step, retention, archive, notify), the `ops` schema (`schema_migrations`, `pipeline_runs`), and `infra/keepwarm/`.
- Conventions: "New migrations: `database/migrations/NNN_name.sql`, wrapped in BEGIN/COMMIT, applied by `python -m ops.migrate up` (CI does it on push). Tests: `cd etl && ../venv/Scripts/python -m pytest` (Docker Desktop must be running)."
- Pending manual steps, **in this order**:
  1. GitHub → Settings → Secrets → Actions: set `SUPABASE_URL` to the exact value in `etl/.env` (the `aws-1-ap-south-1.pooler.supabase.com` URL). The old `SUPABASE_HOST/USER/PASSWORD/DB` secrets can be deleted.
  2. Create a Resend account (free), make an API key, and add the secrets `RESEND_API_KEY` and `ALERT_EMAIL` (the same email you signed up to Resend with).
  3. Actions → ETL Pipeline → Run workflow with **adzuna = true** (the first run must include Adzuna, or the marts rebuild on thin data), and check that it goes green.
  4. `cd infra/keepwarm && npx wrangler login && npx wrangler deploy` (free Cloudflare account). Then ask Claude to delete `keep_warm.yml`.
  5. Only after step 4: make the GitHub repo private.
  6. Send the Adzuna email from `docs/ops/adzuna-licence-request.md`.

- [ ] **Step 3: Update memory**

Edit `sellable-product-planning.md` in the memory directory: Phase 0 code complete, which manual steps are outstanding, and the Phase 1 plan is next.

- [ ] **Step 4: Commit**

```bash
git add docs/ops/adzuna-licence-request.md CLAUDE.md
git commit -m "Add Adzuna draft and Phase 0 handoff"
git push origin main
```

---

## Self-review notes

- **Spec coverage (§5):**
  - 5.1: diagnose (Task 4 preflight + Task 10 secret step), decouple (Task 7), schedule (Task 7), ledger (Tasks 2–3), failure alert (Task 6), throughput (explicitly deferred, reason above).
  - 5.2: strip `_raw`, 120-day retention, VACUUM, size logging (Task 5 + the Task 7 metric).
  - 5.3: resume URLs (Task 9; signed-URL generation deferred), keep-warm (Task 8), repo private (Task 10 manual), secrets check (`frontend/.env` is already untracked; only `.env.example` files are tracked), migration runner + baseline (Task 2), Adzuna email (Task 10).
  - 5.4: tests for source isolation (Task 7's `continue-on-error` gating is covered by `run_step` exit-code tests; there is no connector-level change), retention (Task 5), storage (Task 9).
- **Type consistency:** `run_step.METRICS` keys used in the workflow (`raw_inserted_adzuna`, `raw_inserted_other`, `stg_processed`, `db_size_bytes`) all exist. `ledger.fetch_run` row keys match `notify.build_summary`. `retention.apply` signature matches its tests.
