from ops import preflight

POOLER = "postgresql://postgres.ref:pw@aws-1-ap-south-1.pooler.supabase.com:6543/postgres"
DIRECT = "postgresql://postgres:pw@db.abcd.supabase.co:5432/postgres"


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
    problems = preflight.diagnose_db_url(DIRECT)
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
    bad = fresh_db.replace(":test@", ":S3cretXyz@")
    check = preflight.check_db(bad)
    assert not check.ok
    assert "password" in check.detail.lower()
    assert "S3cretXyz" not in check.detail  # never echo credentials


def test_adzuna_check_outcomes():
    assert preflight.check_adzuna("id", "key", http=FakeHttp(200)).ok
    rejected = preflight.check_adzuna("id", "key", http=FakeHttp(401))
    assert not rejected.ok and "rejected" in rejected.detail
    assert "quota" in preflight.check_adzuna("id", "key", http=FakeHttp(429)).detail
    assert not preflight.check_adzuna(None, None, http=FakeHttp(200)).ok


def test_static_problems_skip_network_checks():
    checks = preflight.run_checks(DIRECT, adzuna=False)
    assert [c.name for c in checks] == ["database url"]


def test_main_exit_codes(fresh_db, monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", fresh_db)
    assert preflight.main([]) == 0
    monkeypatch.setenv("SUPABASE_URL", DIRECT)
    assert preflight.main([]) == 1
    assert "IPv6" in capsys.readouterr().out
