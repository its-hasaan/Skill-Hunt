import pytest

from enrich.attributes import min_years, salary_from_text, seniority, tz_overlap


@pytest.mark.parametrize("text,expected", [
    ("5+ years of experience in Python", 5),
    ("3-5 years of experience building data pipelines", 3),
    ("At least 4 years experience with AWS", 4),
    ("Minimum of 2 years' experience in QA", 2),
    ("7 years of professional software engineering experience", 7),
    ("Experience: 3+ years", 3),
    ("two years of experience with React", 2),
    ("3+ years of Python experience and 5+ years of experience overall", 3),
    ("We were founded 10 years ago and serve 2,000 customers.", None),
    ("20 years of experience", None),
    ("", None),
])
def test_min_years_cases(text, expected):
    assert min_years(text) == expected


@pytest.mark.parametrize("title,years,expected", [
    ("Senior Data Engineer", None, "senior"),
    ("Sr. Backend Engineer", None, "senior"),
    ("Staff Software Engineer", None, "lead"),
    ("Principal Engineer", None, "lead"),
    ("Engineering Manager, Payments", None, "lead"),
    ("Head of Data", None, "lead"),
    ("Junior Data Analyst", None, "junior"),
    ("Data Engineering Intern", None, "intern"),
    ("Graduate Software Engineer", None, "junior"),
    ("Associate Product Manager", None, "junior"),
    ("Software Engineer II", None, "mid"),
    ("Software Engineer I", None, "junior"),
    ("Software Engineer III", None, "senior"),
    ("Senior Product Manager", None, "senior"),
    ("Product Manager", None, "mid"),
    ("Internal Tools Engineer", None, "mid"),
    ("Data Engineer", 6, "senior"),
    ("Data Engineer", 1, "junior"),
    ("Data Engineer", 3, "mid"),
])
def test_seniority_cases(title, years, expected):
    assert seniority(title, years) == expected


@pytest.mark.parametrize("text,expected", [
    ("You must overlap at least 4 hours with EST.", "americas"),
    ("Working hours aligned with US time zones.", "americas"),
    ("Core hours are 9am-1pm PST.", "americas"),
    ("Please be available for overlap with CET business hours.", "europe"),
    ("Comfortable working in European time zones.", "europe"),
    ("You will work APAC hours (SGT).", "apac"),
    ("We collaborate asynchronously across time zones.", None),
    ("Est. 2015, we are a growing startup.", None),
    ("", None),
])
def test_tz_overlap_cases(text, expected):
    assert tz_overlap(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("The base salary range is $120,000 - $150,000 per year.", (120000.0, 150000.0, "USD")),
    ("Pay: $120K–$150K + equity", (120000.0, 150000.0, "USD")),
    ("USD 90,000 to 110,000 annually", (90000.0, 110000.0, "USD")),
    ("$120k - 150k", (120000.0, 150000.0, "USD")),
    ("£50,000 - £70,000", (50000.0, 70000.0, "GBP")),
    ("€60.000 - €80.000 gross", (60000.0, 80000.0, "EUR")),
    ("$4,000 - $6,000 per month", (48000.0, 72000.0, "USD")),
    ("$40 - $60 per hour", None),
    ("We raised $5 million in funding.", None),
    ("3-5 years of experience", None),
    ("", None),
])
def test_salary_from_text_cases(text, expected):
    assert salary_from_text(text) == expected
