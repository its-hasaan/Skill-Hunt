import json
from pathlib import Path

import psycopg2
import pytest

from enrich import gemini
from ops import enrich
from tests.dbutil import run_sql

MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations"


def job(job_id, description="", location="Remote", title="Data Engineer"):
    return {"job_id": job_id, "title": title, "company_name": "Acme", "location_display": location,
            "location_areas": [location], "description": description}


class Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


def answer(items):
    return Resp(200, {"candidates": [{"content": {"parts": [{"text": json.dumps({"jobs": items})}]}}]})


class FakePost:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.responses.pop(0)


def client(post):
    return gemini.GeminiClient("secret-key", "gemini-test", post=post, sleep=lambda s: None)


def test_build_prompt_keeps_location_sentences_only():
    prompt = gemini.build_prompt([job(7, "We love Python. You must be based in the US. Great snacks.")])
    assert "id=7" in prompt and "must be based in the US" in prompt
    assert "We love Python" not in prompt and "Great snacks" not in prompt
    fallback = gemini.build_prompt([job(8, "We love Python and great snacks.")])
    assert "We love Python and great snacks." in fallback


def test_parse_labels_maps_answers():
    jobs = [job(1, "This role is open to candidates anywhere in APAC."), job(2, "Must live in Canada.")]
    text = json.dumps({"jobs": [
        {"id": 1, "remote_scope": "regions", "eligible_pk": "yes", "eligible_in": "yes",
         "evidence": "open to candidates anywhere in APAC"},
        {"id": 2, "remote_scope": "countries", "eligible_pk": "no", "eligible_in": "no",
         "evidence": "Must live in Canada."},
        {"id": 99, "remote_scope": "worldwide", "eligible_pk": "yes", "eligible_in": "yes", "evidence": "x"},
    ]})
    labels = gemini.parse_labels(text, jobs)
    assert set(labels) == {1, 2}
    assert (labels[1].eligible_pk, labels[1].eligible_in, labels[1].remote_scope) == (True, True, "regions")
    assert (labels[2].eligible_pk, labels[2].method, labels[2].confidence) == (False, "llm", 0.8)


def test_llm_evidence_must_be_quoted():
    jobs = [job(1, "We are a remote company."), job(2, "Remote.")]
    text = json.dumps({"jobs": [
        {"id": 1, "remote_scope": "worldwide", "eligible_pk": "yes", "eligible_in": "yes",
         "evidence": "We hire in Pakistan and India."},
        {"id": 2, "remote_scope": "worldwide", "eligible_pk": "yes", "eligible_in": "yes", "evidence": ""},
    ]})
    labels = gemini.parse_labels(text, jobs)
    assert (labels[1].eligible_pk, labels[1].eligible_in) == (None, None)
    assert (labels[2].eligible_pk, labels[2].eligible_in) == (None, None)


def test_parse_labels_survives_bad_json():
    assert gemini.parse_labels("not json", [job(1)]) == {}
    assert gemini.parse_labels(json.dumps({"nope": 1}), [job(1)]) == {}


def test_api_key_goes_in_header_not_url():
    post = FakePost(answer([]))
    client(post).label([job(1)])
    call = post.calls[0]
    assert "secret-key" not in call["url"] and call["headers"]["x-goog-api-key"] == "secret-key"
    assert "gemini-test:generateContent" in call["url"]
    assert call["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_quota_errors_retry_then_raise():
    sleeps = []
    c = gemini.GeminiClient("k", "m", post=FakePost(Resp(429), Resp(429), Resp(429)), sleep=sleeps.append)
    with pytest.raises(gemini.QuotaExhausted):
        c.label([job(1)])
    assert len(sleeps) >= 2
    recovered = gemini.GeminiClient("k", "m", post=FakePost(Resp(429), answer([])), sleep=lambda s: None)
    assert recovered.label([job(1)]) == {}


# --- the AI pass against the database ----------------------------------------------

@pytest.fixture
def conn(pipeline_db):
    for name in ("004_currency_rates.sql", "013_dedup_enrichment.sql"):
        run_sql(pipeline_db, (MIGRATIONS / name).read_text(encoding="utf-8"))
    c = psycopg2.connect(pipeline_db)
    yield c
    c.close()


def add_unclear(url, pid, description, location="Remote"):
    (raw_id,), = run_sql(url, "INSERT INTO raw.jobs (job_platform_id, raw_data, source) VALUES (%s, '{}', 'lever') "
                              "RETURNING id", (pid,))
    (job_id,), = run_sql(url, """INSERT INTO staging.stg_jobs (job_platform_id, title, company_name, description,
                                     location_display, location_areas, workplace_type, country_code, raw_job_id, source)
                                 VALUES (%s, 'Data Engineer', 'Acme', %s, %s, %s, 'remote', 'remote', %s, 'lever')
                                 RETURNING job_id""", (pid, description, location, [location], raw_id))
    run_sql(url, "UPDATE staging.stg_jobs SET canonical_job_id = job_id WHERE job_id = %s", (job_id,))
    return job_id


def label_row(conn, job_id):
    with conn.cursor() as cur:
        cur.execute("SELECT eligible_pk, eligible_in, method, model, eligibility_evidence "
                    "FROM staging.job_enrichment WHERE job_id = %s", (job_id,))
        row = cur.fetchone()
    conn.rollback()
    return row


def test_llm_pass_fills_unclear_labels(conn, pipeline_db):
    a = add_unclear(pipeline_db, "a", "Our team is spread across the APAC region and we hire there.")
    b = add_unclear(pipeline_db, "b", "We are building great software.")
    enrich.enrich_rules(conn, enrich.load_rates(conn))
    post = FakePost(answer([
        {"id": a, "remote_scope": "regions", "eligible_pk": "yes", "eligible_in": "yes",
         "evidence": "Our team is spread across the APAC region and we hire there."},
        {"id": b, "remote_scope": "unclear", "eligible_pk": "unclear", "eligible_in": "unclear", "evidence": ""},
    ]))
    result = enrich.enrich_llm(conn, client(post), max_calls=5)
    assert result["calls"] == 1 and result["labelled"] == 2 and result["decided"] == 1
    assert label_row(conn, a)[:4] == (True, True, "llm", "gemini-test")
    # an "unclear" answer is still recorded, so the job isn't re-sent every day
    assert label_row(conn, b)[:3] == (None, None, "llm")
    assert enrich.enrich_llm(conn, client(FakePost()), max_calls=5)["calls"] == 0


def test_llm_does_not_override_a_decided_rules_label(conn, pipeline_db):
    job_id = add_unclear(pipeline_db, "a", "Hiring in EMEA.", location="EMEA")  # rules: pk unclear, in no
    enrich.enrich_rules(conn, enrich.load_rates(conn))
    post = FakePost(answer([{"id": job_id, "remote_scope": "regions", "eligible_pk": "yes",
                             "eligible_in": "yes", "evidence": "Hiring in EMEA."}]))
    enrich.enrich_llm(conn, client(post), max_calls=5)
    assert label_row(conn, job_id)[:2] == (True, False)


def test_llm_bad_json_keeps_rules_label(conn, pipeline_db):
    a = add_unclear(pipeline_db, "a", "We build software.")
    b = add_unclear(pipeline_db, "b", "We build hardware. Anyone in South Asia may apply.")
    enrich.enrich_rules(conn, enrich.load_rates(conn))
    bad = Resp(200, {"candidates": [{"content": {"parts": [{"text": "{oops"}]}}]})
    good = answer([{"id": b, "remote_scope": "regions", "eligible_pk": "yes", "eligible_in": "yes",
                    "evidence": "Anyone in South Asia may apply."}])
    result = enrich.enrich_llm(conn, client(FakePost(bad, good)), max_calls=5, batch_size=1)
    assert result["calls"] == 2
    assert label_row(conn, a)[2] == "rules"
    assert label_row(conn, b)[:3] == (True, True, "llm")


def test_llm_quota_stops_cleanly(conn, pipeline_db):
    a = add_unclear(pipeline_db, "a", "We build software.")
    enrich.enrich_rules(conn, enrich.load_rates(conn))
    c = gemini.GeminiClient("k", "m", post=FakePost(Resp(429), Resp(429), Resp(429)), sleep=lambda s: None)
    result = enrich.enrich_llm(conn, c, max_calls=5)
    assert result["stopped"] == "quota"
    assert label_row(conn, a)[2] == "rules"


def test_no_api_key_is_a_clean_skip(monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert enrich.main(["--llm"]) == 0
    assert "GEMINI_API_KEY" in capsys.readouterr().out
