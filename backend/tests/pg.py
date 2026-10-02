"""Throwaway Postgres for backend tests (same approach as etl/tests/conftest.py).

TEST_DATABASE_URL (CI service container) or a docker container started once
per session; every test gets a fresh database with the stub auth/pipeline
schema and the copilot migration applied.
"""
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import psycopg2
import pytest

TESTS = Path(__file__).resolve().parent
MIGRATIONS = TESTS.parents[1] / "database" / "migrations"


def run_sql(url, sql, params=None):
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None
    finally:
        conn.close()


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


@pytest.fixture(scope="session")
def pg_server():
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        _wait_for(url)
        yield url
        return
    if not shutil.which("docker") or subprocess.run(["docker", "info"], capture_output=True).returncode:
        pytest.skip("Postgres tests need TEST_DATABASE_URL or a running docker daemon")
    name = f"jobwise-api-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_PASSWORD=test",
                    "-p", "55433:5432", "postgres:16-alpine"], check=True, capture_output=True)
    url = "postgresql://postgres:test@localhost:55433/postgres"
    try:
        _wait_for(url)
        yield url
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True)


@pytest.fixture
def pg_db(pg_server):
    name = f"api_{uuid.uuid4().hex[:12]}"
    admin = psycopg2.connect(pg_server)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{name}"')
    url = pg_server.rsplit("/", 1)[0] + "/" + name
    run_sql(url, (TESTS / "fixtures" / "copilot_schema.sql").read_text(encoding="utf-8"))
    run_sql(url, (MIGRATIONS / "015_copilot_user_tables.sql").read_text(encoding="utf-8"))
    try:
        yield url
    finally:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.close()
