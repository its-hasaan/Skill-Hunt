import psycopg2
import pytest

from ops import reextract
from tests.dbutil import run_sql

TAXONOMY = [
    {"name": "Python", "category": "Programming Language", "aliases": []},
    {"name": "Go", "category": "Programming Language", "aliases": ["golang"], "case_sensitive": ["Go"],
     "not_followed_by": r"[\s\-]+(?:to|further)\b"},
    {"name": "Figma", "category": "Design", "aliases": []},
]


def add(url, pid, source, role, title, description=""):
    (raw_id,), = run_sql(url, "INSERT INTO raw.jobs (job_platform_id, raw_data, source) VALUES (%s, '{}', %s) RETURNING id",
                         (pid, source))
    (job_id,), = run_sql(url, """INSERT INTO staging.stg_jobs (job_platform_id, search_role, title, description, raw_job_id, source)
                                  VALUES (%s, %s, %s, %s, %s, %s) RETURNING job_id""",
                         (pid, role, title, description, raw_id, source))
    return job_id, raw_id


@pytest.fixture
def conn(pipeline_db):
    c = psycopg2.connect(pipeline_db)
    yield c
    c.close()


@pytest.fixture
def seeded(pipeline_db):
    add(pipeline_db, "a1", "adzuna", "Data Engineer", "Senior Data Engineer", "we go further with Python")
    add(pipeline_db, "a2", "adzuna", "Data Engineer", "Senior Data Scientist", "Go and Python")
    add(pipeline_db, "a3", "adzuna", "Data Engineer", "Warehouse Operative", "lifting")
    add(pipeline_db, "r1", "remoteok", "Data Engineer", "Warehouse Operative", "golang")
    return pipeline_db


def test_plan_counts_retag_and_drop(seeded, conn):
    assert reextract.plan(conn, reextract.load_matcher()) == {"total": 4, "keep": 2, "retag": 1, "drop": 1}


def test_apply_retags_drops_and_reextracts(seeded, conn):
    reextract.apply(conn, reextract.load_matcher(), TAXONOMY)
    roles = dict(run_sql(seeded, "SELECT job_platform_id, search_role FROM staging.stg_jobs"))
    assert roles == {"a1": "Data Engineer", "a2": "Data Scientist", "r1": "Data Engineer"}
    assert run_sql(seeded, "SELECT job_platform_id FROM raw.jobs WHERE skip_reason = 'role_mismatch'") == [("a3",)]
    skills = run_sql(seeded, """SELECT s.job_platform_id, k.skill_name FROM staging.stg_job_skills k
                                JOIN staging.stg_jobs s USING (job_id) ORDER BY 1, 2""")
    assert skills == [("a1", "Python"), ("a2", "Go"), ("a2", "Python"), ("r1", "Go")]


def test_reextract_is_idempotent(seeded, conn):
    reextract.apply(conn, reextract.load_matcher(), TAXONOMY)
    first = run_sql(seeded, "SELECT count(*) FROM staging.stg_job_skills")
    reextract.apply(conn, reextract.load_matcher(), TAXONOMY)
    assert run_sql(seeded, "SELECT count(*) FROM staging.stg_job_skills") == first


def test_sync_dim_skills_adds_updates_and_removes_unused(pipeline_db, conn):
    run_sql(pipeline_db, """INSERT INTO staging.dim_skills (skill_name, skill_category) VALUES
                            ('Python', 'Old Category'), ('adjoe', 'Cloud Platform')""")
    result = reextract.sync_dim_skills(conn, TAXONOMY)
    reextract.delete_stale_skills(conn, TAXONOMY)
    rows = dict(run_sql(pipeline_db, "SELECT skill_name, skill_category FROM staging.dim_skills"))
    assert rows == {"Python": "Programming Language", "Go": "Programming Language", "Figma": "Design"}
    assert result == {"upserted": 3}


def test_cli_refuses_large_drop(seeded, monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", seeded)
    assert reextract.main(["--apply", "--max-drop-pct", "10"]) == 1
    assert "refusing" in capsys.readouterr().out.lower()
    assert run_sql(seeded, "SELECT count(*) FROM staging.stg_jobs") == [(4,)]
