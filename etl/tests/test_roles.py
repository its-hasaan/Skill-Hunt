import json
from pathlib import Path

import pytest

from connectors.utils import RoleMatcher

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "config" / "extraction_config.json").read_text())
M = RoleMatcher(CONFIG["roles"])


@pytest.mark.parametrize("title,role", [
    ("Senior Software Engineer", "Software Engineer"),
    (".NET Software Engineer", "Software Engineer"),
    ("Senior Java Developer", "Software Engineer"),
    ("Software Engineer - Backend", "Backend Developer"),
    ("Senior Software Engineer, Machine Learning", "Machine Learning Engineer"),
    ("Mobile App Developer (m/w/d)", "Mobile Developer"),
    ("Architecte Cloud H/F", "Cloud Architect"),
    ("Senior Cloud Systems Architect", "Cloud Architect"),
    ("Data Architect", "Data Engineer"),
    ("Data Analist", "Data Analyst"),
    ("QA Automation Engineer", "QA Engineer"),
    ("SDET II", "QA Engineer"),
    ("Senior Product Designer", "UI/UX Designer"),
    ("UI/UX Designer", "UI/UX Designer"),
    ("UI Developer", "Frontend Developer"),
    ("Senior Product Manager", "Product Manager"),
    ("Product Owner", "Product Manager"),
    ("Technical Support Engineer", "Technical Support Engineer"),
    ("Customer Success Engineer", "Technical Support Engineer"),
    ("IT Help Desk Specialist", "Technical Support Engineer"),
    # found by the Phase 1a backfill review of real dropped titles
    ("AI Automation Engineer", "AI Engineer"),
    ("Artificial Intelligence (AI) Engineer", "AI Engineer"),
    ("AI/ML Developer with Python (f/m/x)", "AI Engineer"),
    ("DevSecOps Engineer", "DevOps Engineer"),
    ("Advanced Cyber Sec Archt/Engr", "Cyber Security Engineer"),
    ("Web Developer", "Full Stack Developer"),
    ("Software Architect", "Software Engineer"),
    ("Senior Python Data Scraping Engineer", "Data Engineer"),
    ("Data Governance Analyst", "Data Analyst"),
    ("Software Engineer, iOS", "Mobile Developer"),
])
def test_role_precedence(title, role):
    assert M.match(title) == role


@pytest.mark.parametrize("title", ["Business Development Manager", "Sales Engineer",
                                   "Project Manager", "Accountant", "Security Guard"])
def test_non_tech_titles_do_not_match(title):
    assert M.match(title) is None


def test_config_role_lists():
    assert len(CONFIG["roles"]) == 20
    assert len(CONFIG["adzuna_roles"]) == 15
    assert set(CONFIG["adzuna_roles"]) < set(CONFIG["roles"])
