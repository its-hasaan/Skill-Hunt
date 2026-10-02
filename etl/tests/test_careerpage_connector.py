import json
from pathlib import Path

import psycopg2

from connectors.careerpage import CareerPageConnector
from connectors.utils import RoleMatcher
from ops import lifecycle
from tests.dbutil import run_sql

FIX = Path(__file__).resolve().parent / "fixtures" / "careers"
ROLES = json.loads((Path(__file__).resolve().parents[1] / "config" / "extraction_config.json").read_text())["roles"]


def html(name):
    return (FIX / name).read_text(encoding="utf-8")


CAREERS = """<html><body>
<a href="/careers/senior-data-engineer">Senior Data Engineer</a>
<a href="/careers/more-roles">More roles</a>
<a href="/careers/third-role">Third</a>
</body></html>"""


class Harness:
    def __init__(self, pages, sites=None, **config):
        self.pages = pages
        self.calls, self.records, self.registered, self.touched = [], [], [], []
        cfg = {
            "sites": sites or [{"domain": "acme.example", "careers_url": "https://acme.example/careers"}],
            "fetch": self.fetch, "sleep": lambda s: None,
            "record": lambda domain, status, **kw: self.records.append((domain, status, kw)),
            "register_board": lambda ats, tokens: self.registered.append((ats, set(tokens))),
            "touch": lambda domain: self.touched.append(domain),
            "page_budget": 10, "delay_seconds": 0,
        }
        cfg.update(config)
        self.connector = CareerPageConnector(cfg, RoleMatcher(ROLES))

    def fetch(self, url, headers):
        self.calls.append((url, dict(headers)))
        return self.pages.get(url, (404, "", {}))

    def run(self):
        return list(self.connector.fetch())


def test_unreadable_robots_skips_site():
    h = Harness({"https://acme.example/robots.txt": (503, "", {})})
    assert h.run() == []
    assert [url for url, _ in h.calls] == ["https://acme.example/robots.txt"]
    assert h.records == [("acme.example", None, {"failed": True})]
    assert h.connector.seen_boards == set()


def test_robots_disallow_marks_site_blocked():
    h = Harness({"https://acme.example/robots.txt": (200, "User-agent: *\nDisallow: /careers\n", {})})
    assert h.run() == []
    assert len(h.calls) == 1 and h.records[0][:2] == ("acme.example", "blocked")


def test_embedded_board_is_registered_not_scraped():
    h = Harness({"https://acme.example/careers": (200, html("greenhouse_embed.html"), {})})
    assert h.run() == []
    assert ("greenhouse", {"acme"}) in h.registered and ("lever", {"betaco"}) in h.registered
    assert h.records[0][:2] == ("acme.example", "ats")
    assert len(h.calls) == 2  # robots.txt (404 = no rules) + careers page


def test_jsonld_jobs_are_filtered_and_namespaced():
    h = Harness({
        "https://acme.example/careers": (200, CAREERS, {"ETag": '"v1"'}),
        "https://acme.example/careers/senior-data-engineer": (200, html("jsonld_graph.html"), {}),
        "https://acme.example/careers/more-roles": (200, html("jsonld_list.html"), {}),
    })
    jobs = h.run()
    # remote Data Engineer (India/Pakistan) and Lahore Backend Developer kept; New York onsite QA dropped
    assert sorted(j.title for j in jobs) == ["Backend Developer", "Senior Data Engineer"]
    data = next(j for j in jobs if j.title == "Senior Data Engineer")
    assert data.job_platform_id == "careerpage:acme.example:DE-42" and data.workplace_type == "remote"
    assert data.source == "careerpage" and data.company_name == "Acme Corp"
    backend = next(j for j in jobs if j.title == "Backend Developer")
    assert backend.country_code == "pk" and backend.company_name == "Beta Inc"
    domain, status, kw = h.records[-1]
    assert (domain, status, kw["jobs_found"], kw["etag"]) == ("acme.example", "jsonld", 3, '"v1"')
    assert h.connector.seen_boards == {"acme.example"}


def test_budget_cut_site_is_not_fully_seen():
    pages = {"https://acme.example/careers": (200, CAREERS, {}),
             "https://acme.example/careers/senior-data-engineer": (200, html("jsonld_graph.html"), {})}
    small = Harness(pages, page_budget=2)  # careers page + one job page: two links left unread
    small.run()
    assert small.connector.seen_boards == set()
    assert len(small.calls) == 3


def test_not_modified_careers_page_touches_jobs():
    sites = [{"domain": "acme.example", "careers_url": "https://acme.example/careers", "status": "jsonld",
              "etag": '"v1"', "last_modified": None}]
    h = Harness({"https://acme.example/careers": (304, "", {})}, sites=sites)
    assert h.run() == []
    assert h.calls[-1] == ("https://acme.example/careers", {"If-None-Match": '"v1"'})
    assert h.touched == ["acme.example"] and h.records[-1][:2] == ("acme.example", "jsonld")
    assert h.connector.seen_boards == set()  # nothing may be closed from a skipped crawl


def test_careers_url_falls_back_to_common_paths():
    h = Harness({"https://acme.example/jobs": (200, "<html>nothing here</html>", {})},
                sites=[{"domain": "acme.example", "careers_url": None}])
    h.run()
    assert [url for url, _ in h.calls] == ["https://acme.example/robots.txt", "https://acme.example/careers",
                                           "https://acme.example/jobs"]
    assert h.records[-1][:2] == ("acme.example", "empty")


def test_touch_board_bumps_open_jobs(pipeline_db):
    run_sql(pipeline_db, """INSERT INTO raw.jobs (job_platform_id, raw_data, source, last_seen_at, closed_at) VALUES
        ('careerpage:acme.example:1', '{}', 'careerpage', now() - interval '10 days', NULL),
        ('careerpage:acme.example:2', '{}', 'careerpage', now() - interval '10 days', now()),
        ('careerpage:other.example:3', '{}', 'careerpage', now() - interval '10 days', NULL)""")
    conn = psycopg2.connect(pipeline_db)
    try:
        assert lifecycle.touch_board(conn, "careerpage", "acme.example") == 1
    finally:
        conn.close()


def test_redirect_to_hiring_system_registers_board():
    page = (200, "<html><a href='/acme/jobs/1'>Job</a></html>", {"_final_url": "https://jobs.lever.co/acme"})
    h = Harness({"https://acme.example/careers": page})
    assert h.run() == []
    assert ("lever", {"acme"}) in h.registered and h.records[-1][:2] == ("acme.example", "ats")
