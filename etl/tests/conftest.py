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
from pathlib import Path

import psycopg2
import pytest

from tests.dbutil import run_sql

_TESTS = Path(__file__).resolve().parent
_REPO = _TESTS.parents[1]


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


@pytest.fixture
def pipeline_db(fresh_db):
    """A database with the raw/staging tables the ops tools touch plus the ledger."""
    run_sql(fresh_db, (_TESTS / "fixtures" / "pipeline_schema.sql").read_text(encoding="utf-8"))
    run_sql(fresh_db, (_REPO / "database" / "migrations" / "007_ops_pipeline_runs.sql").read_text(encoding="utf-8"))
    return fresh_db
