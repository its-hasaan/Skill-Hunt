from pathlib import Path

import pytest

from careers.html_links import ats_boards, extract_links, job_links
from careers.jsonld import extract_jobpostings, map_jobposting
from careers.robots import RobotsPolicy

FIX = Path(__file__).resolve().parent / "fixtures" / "careers"


def html(name):
    return (FIX / name).read_text(encoding="utf-8")


# --- robots.txt -----------------------------------------------------------------

def test_robots_blocks_disallowed_paths():
    policy = RobotsPolicy.from_response(200, "User-agent: *\nDisallow: /careers\n")
    assert not policy.allowed("https://acme.example/careers/data-engineer")
    assert policy.allowed("https://acme.example/about")
    named = RobotsPolicy.from_response(200, "User-agent: JobwiseBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n")
    assert not named.allowed("https://acme.example/jobs")


def test_robots_404_allows_all():
    assert RobotsPolicy.from_response(404, "Not found").allowed("https://acme.example/careers")


@pytest.mark.parametrize("status,text", [
    (None, ""),
    (503, "Service unavailable"),
    (403, "<!DOCTYPE html><html><head><title>Just a moment...</title>"),
    (200, "<!DOCTYPE html><html><head><title>Just a moment...</title>"),
])
def test_robots_unreadable_is_none(status, text):
    assert RobotsPolicy.from_response(status, text) is None


# --- links ------------------------------------------------------------------------

def test_extract_links_absolute_without_fragments():
    links = extract_links(html("links.html"), "https://acme.example/careers")
    assert "https://acme.example/careers/data-engineer-123" in links
    assert "https://acme.example/positions/qa-lead" in links
    assert "https://acme.example/img/team.png" in links
    assert not any(link.startswith("mailto:") or "#" in link for link in links)


def test_ats_boards_finds_links_and_embeds():
    boards = ats_boards(html("greenhouse_embed.html"), "https://acme.example/careers")
    assert boards == {"greenhouse": {"acme"}, "lever": {"betaco"}}


def test_job_links_same_domain_only_and_limited():
    links = extract_links(html("links.html"), "https://acme.example/careers")
    assert job_links(links, "acme.example", limit=10) == [
        "https://acme.example/careers/data-engineer-123",
        "https://www.acme.example/jobs/ml-engineer",
        "https://acme.example/positions/qa-lead",
        "https://acme.example/openings/support-engineer",
    ]
    assert len(job_links(links, "acme.example", limit=2)) == 2


# --- JSON-LD ------------------------------------------------------------------------

def test_extract_jobpostings_shapes():
    assert [j["title"] for j in extract_jobpostings(html("jsonld_graph.html"))] == ["Senior Data Engineer"]
    assert [j["title"] for j in extract_jobpostings(html("jsonld_list.html"))] == ["QA Engineer", "Backend Developer"]
    single = '<script type="application/ld+json">{"@type": "JobPosting", "title": "X"}</script>'
    assert [j["title"] for j in extract_jobpostings(single)] == ["X"]
    assert extract_jobpostings("<html>no data</html>") == []


def test_map_jobposting_remote_with_applicant_countries():
    item = extract_jobpostings(html("jsonld_graph.html"))[0]
    job = map_jobposting(item, "https://acme.example/careers/senior-data-engineer")
    assert job["id"] == "DE-42" and job["title"] == "Senior Data Engineer"
    assert job["company_name"] == "Acme Corp"
    assert job["remote_flag"] is True and job["workplace_hint"] == "remote"
    assert job["locations"] == ["India", "Pakistan"]  # where applicants may be, not the office
    text = " ".join(job["description"].split())  # html_to_text puts inline tags on their own lines
    assert text.startswith("Build pipelines in Python and SQL.") and "<" not in text
    assert (job["salary_min"], job["salary_max"], job["salary_currency"]) == (60000.0, 90000.0, "USD")
    assert job["job_posted_at"] == "2026-09-20"
    assert (job["contract_type"], job["contract_time"]) == ("full_time", "permanent")
    assert job["redirect_url"] == "https://acme.example/careers/senior-data-engineer"


def test_map_jobposting_onsite_address():
    qa, backend = extract_jobpostings(html("jsonld_list.html"))
    job = map_jobposting(qa, "https://careers.beta.example/jobs")
    assert job["remote_flag"] is False and job["locations"] == ["New York, NY, United States"]
    assert job["company_name"] == "Beta Inc" and job["redirect_url"].endswith("qa-engineer-77")
    assert len(job["id"]) == 16  # sha1 of the posting url
    assert (job["contract_type"], job["contract_time"]) == ("contract", "temporary")
    assert map_jobposting(backend, "https://careers.beta.example/jobs")["locations"] == ["Lahore, Pakistan"]


def test_map_jobposting_salary_and_dates():
    qa, backend = extract_jobpostings(html("jsonld_list.html"))
    assert map_jobposting(qa, "u")["salary_min"] is None  # hourly is skipped
    job = map_jobposting(backend, "u")
    assert (job["salary_min"], job["salary_max"], job["salary_currency"]) == (3_600_000.0, 5_400_000.0, "PKR")
    assert map_jobposting({"@type": "JobPosting"}, "u") is None  # no title
