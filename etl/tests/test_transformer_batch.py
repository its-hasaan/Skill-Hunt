"""Batched transformer writes + reconnect-and-continue (PIPELINE_REVIEW Part 2 #12)."""
import importlib
import json
import sys

import psycopg2
import pytest

from tests.dbutil import run_sql


@pytest.fixture
def transformer(monkeypatch, tmp_path):
    import dotenv
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("transformer", None)
    yield importlib.import_module("transformer")
    sys.modules.pop("transformer", None)


def add_ats_job(url, pid, title, description="", company="Acme", salary_min=None, role="Data Engineer"):
    envelope = {"_source": "greenhouse", "_normalized": {
        "job_platform_id": pid, "title": title, "company_name": company,
        "description": description, "location_display": "Remote", "location_areas": ["Remote"],
        "salary_min": salary_min, "salary_currency": "USD", "redirect_url": f"https://x/{pid}",
        "job_posted_at": "2026-09-30T10:00:00Z", "workplace_type": "remote"}}
    (raw_id,), = run_sql(url, """INSERT INTO raw.jobs (job_platform_id, search_role, raw_data, source)
                                 VALUES (%s, %s, %s, 'greenhouse') RETURNING id""",
                         (pid, role, json.dumps(envelope)))
    return raw_id


def add_adzuna_job(url, pid, title):
    (raw_id,), = run_sql(url, """INSERT INTO raw.jobs (job_platform_id, raw_data, source)
                                 VALUES (%s, %s, 'adzuna') RETURNING id""",
                         (pid, json.dumps({"id": pid, "title": title, "description": "x"})))
    return raw_id


class FakeExtractor:
    """Python/SQL keyword matcher; can run a hook on the Nth call."""

    def __init__(self, on_call=None):
        self.calls = 0
        self.on_call = on_call or {}

    def extract_skills(self, text, context=""):
        self.calls += 1
        if self.calls in self.on_call:
            self.on_call[self.calls]()
        found = []
        if "Python" in text:
            found.append({"skill_name": "Python", "category": "Programming Language", "mention_count": 2})
            found.append({"skill_name": "Python", "category": "Programming Language", "mention_count": 1})
        if "SQL" in text:
            found.append({"skill_name": "SQL", "category": "Database", "mention_count": 1})
        return found

    def get_stats(self):
        return {}


def connector(url, log):
    def connect():
        c = psycopg2.connect(url)
        log.append(c)
        return c
    return connect


def kill(url, log):
    """Terminate the backend of the most recent transformer connection."""
    def _kill():
        run_sql(url, "SELECT pg_terminate_backend(%s)", (log[-1].get_backend_pid(),))
    return _kill


def test_batched_transform_loads_jobs_and_skills(pipeline_db, transformer):
    for i in range(4):
        add_ats_job(pipeline_db, f"greenhouse:acme:{i}", f"Data Engineer {i}", "Python and SQL")
    skipped = add_adzuna_job(pipeline_db, "az1", "Warehouse Operative")
    conns = []

    result = transformer.transform_and_load(batch_size=2, fast_only=True,
                                            connect=connector(pipeline_db, conns), extractor=FakeExtractor())

    assert result["jobs_processed"] == 4 and result["jobs_skipped"] == 1 and result["jobs_failed"] == 0
    rows = run_sql(pipeline_db, """SELECT title, company_name, workplace_type, location_areas, salary_currency
                                   FROM staging.stg_jobs ORDER BY title""")
    assert rows[0] == ("Data Engineer 0", "Acme", "remote", ["Remote"], "USD")
    assert len(rows) == 4
    # duplicate skill hits within one job collapse to one row
    assert run_sql(pipeline_db, "SELECT count(*) FROM staging.stg_job_skills") == [(8,)]
    assert run_sql(pipeline_db, "SELECT skill_name FROM staging.dim_skills ORDER BY 1") == [("Python",), ("SQL",)]
    assert run_sql(pipeline_db, "SELECT skip_reason FROM raw.jobs WHERE id = %s", (skipped,)) == [("role_mismatch",)]


def test_transform_reconnects_after_dropped_connection(pipeline_db, transformer):
    for i in range(4):
        add_ats_job(pipeline_db, f"greenhouse:acme:{i}", f"Data Engineer {i}", "Python")
    conns, sleeps = [], []
    extractor = FakeExtractor(on_call={3: kill(pipeline_db, conns)})  # dies inside batch 2

    result = transformer.transform_and_load(batch_size=2, fast_only=True, connect=connector(pipeline_db, conns),
                                            extractor=extractor, sleep=sleeps.append)

    assert run_sql(pipeline_db, "SELECT count(*) FROM staging.stg_jobs") == [(4,)]
    assert run_sql(pipeline_db, "SELECT count(*) FROM staging.stg_job_skills") == [(4,)]
    assert result["reconnects"] == 1 and len(conns) == 2 and len(sleeps) == 1


def test_transform_gives_up_after_repeated_connection_failures(pipeline_db, transformer):
    add_ats_job(pipeline_db, "greenhouse:acme:1", "Data Engineer", "Python")
    conns, sleeps = [], []

    def connect():
        if conns:
            raise psycopg2.OperationalError("could not translate host name")
        return connector(pipeline_db, conns)()

    with pytest.raises(psycopg2.OperationalError):
        transformer.transform_and_load(batch_size=2, fast_only=True, connect=connect,
                                       extractor=FakeExtractor(on_call={1: kill(pipeline_db, conns)}),
                                       sleep=sleeps.append, max_reconnects=3)
    assert len(sleeps) == 3 and sleeps == sorted(sleeps)  # backs off between attempts


def test_bad_row_is_isolated_and_leaves_the_queue(pipeline_db, transformer):
    add_ats_job(pipeline_db, "greenhouse:acme:1", "Data Engineer A", "Python")
    bad = add_ats_job(pipeline_db, "greenhouse:acme:2", "Data Engineer B", "Python", salary_min="not-a-number")
    add_ats_job(pipeline_db, "greenhouse:acme:3", "Data Engineer C", "Python")

    result = transformer.transform_and_load(batch_size=10, fast_only=True,
                                            connect=connector(pipeline_db, []), extractor=FakeExtractor())

    assert result["jobs_processed"] == 2 and result["jobs_failed"] == 1
    assert run_sql(pipeline_db, "SELECT title FROM staging.stg_jobs ORDER BY 1") == [("Data Engineer A",), ("Data Engineer C",)]
    assert run_sql(pipeline_db, "SELECT skip_reason FROM raw.jobs WHERE id = %s", (bad,)) == [("transform_error",)]
