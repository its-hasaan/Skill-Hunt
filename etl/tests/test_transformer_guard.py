import importlib
import sys

import psycopg2
import pytest

from tests.dbutil import run_sql


@pytest.fixture
def transformer(monkeypatch, tmp_path):
    import dotenv
    # transformer calls load_dotenv() on import, which would pull the
    # production SUPABASE_URL from etl/.env into the test process.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)  # it also opens transformation.log in the cwd
    sys.modules.pop("transformer", None)
    yield importlib.import_module("transformer")
    sys.modules.pop("transformer", None)


def test_stripped_payloads_are_never_picked_up_for_transform(pipeline_db, transformer):
    run_sql(pipeline_db, """INSERT INTO raw.jobs (job_platform_id, raw_data)
                            VALUES ('stub', '{"_stripped": true}'), ('live', '{"title": "x"}')""")
    conn = psycopg2.connect(pipeline_db)
    try:
        with conn.cursor() as cur:
            jobs = transformer.get_unprocessed_jobs(cur, batch_size=10)
    finally:
        conn.close()
    assert [j["job_platform_id"] for j in jobs] == ["live"]
