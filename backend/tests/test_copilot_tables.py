import uuid

import psycopg2
import pytest

from tests.pg import MIGRATIONS, pg_db, pg_server, run_sql  # noqa: F401  (fixtures)

MIGRATION = (MIGRATIONS / "015_copilot_user_tables.sql").read_text(encoding="utf-8")


def test_migration_is_idempotent_and_cascades(pg_db):
    run_sql(pg_db, MIGRATION)  # second application is a no-op
    user = str(uuid.uuid4())
    run_sql(pg_db, "INSERT INTO auth.users (id, email) VALUES (%s, 'a@x.io')", (user,))
    run_sql(pg_db, "INSERT INTO public.user_job_profiles (user_id, target_roles, country) VALUES (%s, %s, 'pk')",
            (user, ["Data Engineer"]))
    run_sql(pg_db, "INSERT INTO public.applications (user_id, job_id, title) VALUES (%s, 1, 'Data Engineer')",
            (user,))
    run_sql(pg_db, "INSERT INTO public.job_feedback (user_id, job_id) VALUES (%s, 2)", (user,))
    run_sql(pg_db, "INSERT INTO public.digest_log (user_id, job_ids) VALUES (%s, '{1,2}')", (user,))

    run_sql(pg_db, "DELETE FROM auth.users WHERE id = %s", (user,))

    for table in ("user_job_profiles", "applications", "job_feedback", "digest_log"):
        assert run_sql(pg_db, f"SELECT count(*) FROM public.{table}") == [(0,)]


def test_constraints(pg_db):
    user = str(uuid.uuid4())
    run_sql(pg_db, "INSERT INTO auth.users (id) VALUES (%s)", (user,))
    with pytest.raises(psycopg2.Error):
        run_sql(pg_db, "INSERT INTO public.user_job_profiles (user_id, target_roles) VALUES (%s, %s)",
                (user, ["a", "b", "c", "d"]))
    with pytest.raises(psycopg2.Error):
        run_sql(pg_db, "INSERT INTO public.applications (user_id, title, status) VALUES (%s, 't', 'ghosted')",
                (user,))
    run_sql(pg_db, "INSERT INTO public.applications (user_id, job_id, title) VALUES (%s, 5, 't')", (user,))
    with pytest.raises(psycopg2.Error):
        run_sql(pg_db, "INSERT INTO public.applications (user_id, job_id, title) VALUES (%s, 5, 't')", (user,))


def test_rls_is_enabled(pg_db):
    rows = run_sql(pg_db, """SELECT relname, relrowsecurity FROM pg_class
                             WHERE relname IN ('user_job_profiles', 'applications', 'job_feedback', 'digest_log')""")
    assert sorted(rows) == [("applications", True), ("digest_log", True), ("job_feedback", True),
                            ("user_job_profiles", True)]
