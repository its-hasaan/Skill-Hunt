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
