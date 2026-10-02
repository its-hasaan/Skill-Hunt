import pytest

from enrich.fingerprint import SOURCE_PRIORITY, fingerprint, normalise_company, normalise_title


@pytest.mark.parametrize("raw,expected", [
    ("GitLab Inc.", "gitlab"),
    ("gitlab", "gitlab"),
    ("GitLab, Inc", "gitlab"),
    ("Acme Technologies Ltd", "acme technologies"),
    ("Deel GmbH", "deel"),
    ("  The Browser Company  ", "the browser company"),
    ("", ""),
    (None, ""),
])
def test_normalise_company(raw, expected):
    assert normalise_company(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Senior Backend Engineer (Remote)", "senior backend engineer"),
    ("Senior Backend Engineer - Remote, US", "senior backend engineer"),
    ("senior backend engineer", "senior backend engineer"),
    ("Sr. Data Engineer", "senior data engineer"),
    ("Jr Data Analyst", "junior data analyst"),
    ("Software Engineer, Backend", "software engineer backend"),
    ("Data Engineer | Bangalore", "data engineer"),
    ("ML Engineer – EMEA", "ml engineer"),
    ("Data Engineer", "data engineer"),
])
def test_normalise_title(raw, expected):
    assert normalise_title(raw) == expected


def test_team_names_in_brackets_keep_jobs_apart():
    assert normalise_title("Staff Software Engineer, Backend (Payments)") == "staff software engineer backend payments"
    assert normalise_title("Staff Software Engineer, Backend (Consumer Lending)") != \
        normalise_title("Staff Software Engineer, Backend (Payments)")
    assert normalise_title("Data Engineer [Remote - EMEA]") == "data engineer"


def test_seniority_words_keep_jobs_apart():
    assert normalise_title("Senior Data Engineer") != normalise_title("Data Engineer")


def test_fingerprint_location_key():
    assert fingerprint("Acme", "Data Engineer", "Remote - United States") == \
        fingerprint("Acme Inc", "Data Engineer", "United States")
    assert fingerprint("Acme", "Data Engineer", "Remote - US") != \
        fingerprint("Acme", "Data Engineer", "Remote - Canada")
    # "Remote" and "Worldwide" say the same thing about a listing
    assert fingerprint("GitLab", "Senior Backend Engineer (Remote)", "Remote") == \
        fingerprint("gitlab", "Senior Backend Engineer", "Worldwide")


def test_source_priority_order():
    assert SOURCE_PRIORITY["greenhouse"] < SOURCE_PRIORITY["careerpage"] < SOURCE_PRIORITY["himalayas"] \
        < SOURCE_PRIORITY["adzuna"]
