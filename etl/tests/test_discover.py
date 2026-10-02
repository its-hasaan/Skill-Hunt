import json

from ops import discover_companies as dc


def test_extract_tokens_by_system():
    urls = [
        "https://boards.greenhouse.io/GitLab/jobs/123",
        "https://job-boards.greenhouse.io/figma",
        "https://boards.greenhouse.io/embed/job_board?for=Stripe&b=x",
        "https://boards.greenhouse.io/assets/app.js",
        "https://jobs.lever.co/Spotify/2f1c-uuid",
        "https://jobs.ashbyhq.com/ramp/abc?utm_source=x",
        "https://jobs.ashbyhq.com/",
        "https://jobs.smartrecruiters.com/BoschGroup/7440001",
        "https://example.com/careers",
    ]
    assert dc.extract_tokens(urls) == {
        "greenhouse": {"gitlab", "figma", "stripe"},
        "lever": {"spotify"},
        "ashby": {"ramp"},
        "smartrecruiters": {"BoschGroup"},
        "workable": set(),
    }


def test_extract_workable_tokens():
    urls = ["https://apply.workable.com/HuggingFace/j/F4C096B22E/",
            "https://apply.workable.com/j/F4C096B22E",
            "https://apply.workable.com/api/v1/widget/accounts/x",
            "https://apply.workable.com/arbisoft/"]
    assert dc.extract_tokens(urls)["workable"] == {"huggingface", "arbisoft"}


def test_crawl_pages_until_empty_with_one_request_per_page():
    pages = {0: ["https://jobs.ashbyhq.com/a/1", "https://jobs.ashbyhq.com/b/2"],
             1: ["https://jobs.ashbyhq.com/c/3"]}
    calls = []

    def fetch(url):
        calls.append(url)
        if "jobs.ashbyhq.com" not in url:
            return ""
        page = int(url.rsplit("page=", 1)[1])
        return "\n".join(json.dumps({"url": u}) for u in pages.get(page, []))

    found = dc.crawl("CC-TEST", max_pages=5, fetch=fetch, sleep=lambda s: None)
    assert found["ashby"] == {"a", "b", "c"}
    ashby_calls = [c for c in calls if "jobs.ashbyhq.com" in c]
    assert len(ashby_calls) == 3  # pages 0, 1 and the empty page 2


class Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


def scripted_get(*results):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        result = results[len(calls) - 1]
        if isinstance(result, Exception):
            raise result
        return result
    get.calls = calls
    return get


def test_http_fetch_retries_overloaded_index_then_returns_body():
    sleeps = []
    get = scripted_get(Resp(504), Resp(503), Resp(200, "body"))
    assert dc.http_fetch("u", attempts=3, get=get, sleep=sleeps.append) == "body"
    assert len(get.calls) == 3 and len(sleeps) == 2 and sleeps[0] < sleeps[1]


def test_http_fetch_gives_up_after_all_attempts_fail():
    sleeps = []
    get = scripted_get(Resp(504), Resp(504), Resp(504))
    assert dc.http_fetch("u", attempts=3, get=get, sleep=sleeps.append) is None
    assert len(get.calls) == 3 and len(sleeps) == 2  # no pointless wait after the last try


def test_http_fetch_retries_timeouts_but_not_client_errors():
    import requests
    get = scripted_get(requests.Timeout("slow"), Resp(200, "ok"))
    assert dc.http_fetch("u", attempts=3, get=get, sleep=lambda s: None) == "ok"
    get404 = scripted_get(Resp(404))
    assert dc.http_fetch("u", attempts=3, get=get404, sleep=lambda s: None) is None
    assert len(get404.calls) == 1


def test_crawl_survives_a_failing_host():
    def fetch(url):
        if "lever" in url:
            return None  # timeout / 5xx
        return ""

    assert dc.crawl("CC-TEST", max_pages=2, fetch=fetch, sleep=lambda s: None)["lever"] == set()
