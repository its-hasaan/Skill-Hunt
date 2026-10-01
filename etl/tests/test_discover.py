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
    }


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


def test_crawl_survives_a_failing_host():
    def fetch(url):
        if "lever" in url:
            return None  # timeout / 5xx
        return ""

    assert dc.crawl("CC-TEST", max_pages=2, fetch=fetch, sleep=lambda s: None)["lever"] == set()
