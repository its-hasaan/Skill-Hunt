import json
from pathlib import Path

import pytest

from connectors import ashby, greenhouse, lever, smartrecruiters
from connectors.utils import RoleMatcher

FIX = Path(__file__).resolve().parent / "fixtures" / "ats"
ROLES = json.loads((Path(__file__).resolve().parents[1] / "config" / "extraction_config.json").read_text())["roles"]


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_greenhouse_maps_real_sample():
    item = load("greenhouse_gitlab.json")["jobs"][0]
    job = greenhouse.map_job("gitlab", item)
    assert job["title"] == "AI Engineer"
    assert job["id"] == str(item["id"])
    assert job["redirect_url"] == item["absolute_url"]
    assert "Remote, Bangalore" in job["locations"]
    assert "<" not in job["description"] and len(job["description"]) > 50
    assert job["job_posted_at"].startswith("2026-")


def test_lever_maps_real_sample():
    item = load("lever_spotify.json")[0]
    job = lever.map_job("spotify", item)
    assert job["title"] == "Android Engineer - Experience"
    assert job["workplace_hint"] == "hybrid"
    assert "London" in job["locations"]
    assert job["redirect_url"].startswith("https://jobs.lever.co/spotify/")
    assert job["job_posted_at"].startswith("2026-")


def test_ashby_maps_real_sample():
    item = load("ashby_ramp.json")["jobs"][0]
    job = ashby.map_job("ramp", item)
    assert job["remote_flag"] is True
    assert "Remote (US)" in job["locations"]
    assert job["salary_min"] == 211400 and job["salary_max"] == 290600
    assert job["salary_currency"] == "USD"


def test_ashby_skips_unlisted():
    assert ashby.map_job("ramp", {"id": "x", "title": "T", "isListed": False}) is None


def test_smartrecruiters_maps_list_and_detail():
    item = load("smartrecruiters_list.json")["content"][0]
    job = smartrecruiters.map_job("smartrecruiters", item)
    assert job["remote_flag"] is True
    assert job["redirect_url"].startswith("https://jobs.smartrecruiters.com/smartrecruiters/")
    detail = load("smartrecruiters_detail.json")
    text = smartrecruiters.description_from_detail(detail)
    assert len(text) > 50 and "<" not in text


class FakeGreenhouse(greenhouse.GreenhouseConnector):
    def __init__(self, boards_items, **kw):
        self.boards_items = boards_items
        self.recorded = []
        cfg = {"boards": list(boards_items), "record_check": lambda *a, **k: self.recorded.append((a, k))}
        super().__init__(cfg, RoleMatcher(ROLES))

    def fetch_board(self, board):
        return self.boards_items[board]


def gh_item(i, title, location):
    return {"id": i, "title": title, "absolute_url": f"https://x/{i}", "location": {"name": location},
            "offices": [], "content": "&lt;p&gt;Python and SQL&lt;/p&gt;", "first_published": "2026-09-01T00:00:00Z"}


def test_connector_filters_roles_and_locations():
    conn = FakeGreenhouse({"acme": [
        gh_item(1, "Senior Data Engineer", "Remote"),
        gh_item(2, "Account Executive", "Remote"),
        gh_item(3, "Backend Developer", "New York, NY"),
        gh_item(4, "QA Engineer", "Lahore, Pakistan"),
    ]})
    jobs = list(conn.fetch())
    assert [(j.external_id, j.search_role, j.country_code, j.workplace_type) for j in jobs] == [
        ("acme:1", "Data Engineer", "remote", "remote"),
        ("acme:4", "QA Engineer", "pk", "onsite"),
    ]
    assert jobs[0].job_platform_id == "greenhouse:acme:1"
    assert jobs[0].description == "Python and SQL"


def test_connector_tracks_seen_boards_and_skips_failed():
    conn = FakeGreenhouse({"ok": [gh_item(1, "Data Engineer", "Remote")], "down": None})
    list(conn.fetch())
    assert conn.seen_boards == {"ok"}
    outcomes = {a[0][1]: a[1]["ok"] for a in conn.recorded}
    assert outcomes == {"ok": True, "down": False}


def test_workable_maps_real_sample():
    from connectors import workable
    item = load("workable_huggingface.json")["jobs"][0]
    job = workable.map_job("huggingface", item)
    assert job["title"] == "Low-level Senior Software Engineer, Xet Storage - EMEA Remote"
    assert job["id"] == "F4C096B22E"
    assert job["redirect_url"] == "https://apply.workable.com/j/F4C096B22E"
    assert job["remote_flag"] is True
    assert job["locations"] == []  # Workable hides the office of remote roles; it isn't a requirement
    assert "<" not in job["description"] and len(job["description"]) > 50
    assert job["job_posted_at"] == "2026-07-30"
    assert (job["contract_type"], job["contract_time"]) == ("full_time", "permanent")


def test_workable_keeps_visible_locations():
    from connectors import workable
    item = {"title": "Data Engineer", "shortcode": "X1", "telecommuting": False, "url": "https://w/j/X1",
            "locations": [{"country": "Pakistan", "city": "Lahore", "region": "Punjab", "hidden": False}],
            "description": "<p>Build pipelines</p>", "published_on": "2026-09-01"}
    job = workable.map_job("acme", item)
    assert job["locations"] == ["Lahore, Punjab, Pakistan"] and job["remote_flag"] is False


def test_workable_payload_shape():
    from connectors.ats_endpoints import job_items, list_url
    assert job_items("workable", load("workable_huggingface.json"))[0]["shortcode"] == "F4C096B22E"
    assert job_items("workable", {"error": "x"}) is None
    assert list_url("workable", "acme") == "https://apply.workable.com/api/v1/widget/accounts/acme?details=true"
