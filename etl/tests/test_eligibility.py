import pytest

from enrich.eligibility import RULES_VERSION, classify


def job(location="", areas=None, description="", workplace="remote", country="remote", title="Data Engineer"):
    return {"title": title, "description": description, "location_display": location,
            "location_areas": areas if areas is not None else ([location] if location else []),
            "workplace_type": workplace, "country_code": country}


EXPORT = ("If you are located in or are a national of one of the listed countries or regions, "
          "an export license may be required as a condition of your employment in this role.")
LEGAL = ("For positions based in San Francisco or Los Angeles: Affirm considers qualified applicants "
         "with arrest and conviction records, as required by law.")
PAY = ("Below is the annual On Target Compensation (OTE) range for candidates located in California, "
       "Colorado, Illinois, New York and Washington.")


@pytest.mark.parametrize("j,pk,inn,scope", [
    (job("Remote - United States"), False, False, "countries"),
    (job("Remote, Bangalore", country="in"), False, True, "countries"),
    (job("India, Pakistan", areas=["India", "Pakistan"]), True, True, "countries"),
    (job("Worldwide", areas=[]), True, True, "worldwide"),
    (job("EMEA"), None, False, "regions"),
    (job("Asia"), True, True, "regions"),
    # a region plus specific cities: the region may just be a label, so not a promise
    (job("Asia", areas=["Asia", "Hong Kong", "Taiwan, Taipei"]), None, None, "regions"),
    (job("Asia", areas=["Asia", "Bengaluru, India"]), None, True, "regions"),
    (job("Canada", areas=["Canada", "Distributed, Global"]), True, True, "worldwide"),
    (job("Remote, KSA; Remote, UAE"), False, False, "countries"),
    (job("Lahore, Pakistan", workplace="onsite", country="pk"), True, False, "onsite"),
    (job("Bengaluru", workplace="hybrid", country="in"), False, True, "hybrid"),
    (job("Mumbai", workplace=None, country="in"), False, True, "onsite"),  # Adzuna/Jooble local job
    (job("Remote"), None, None, "unclear"),
    (job("Remote", description="Our team works from anywhere in the world."), True, True, "worldwide"),
    (job("Worldwide", description="Candidates must be authorized to work in the US."), False, False, "countries"),
    (job("San Francisco"), False, False, "countries"),  # Ashby isRemote + an SF primary location
    (job("Remote, Canada; Remote, United States"), False, False, "countries"),
    (job("Remote - India", areas=["Remote - India", "Remote - Pakistan"]), True, True, "countries"),
    (job("Remote", description="You'll overlap with EST for standups."), None, None, "unclear"),
    (job("Remote", description=EXPORT), None, None, "unclear"),
    (job("Remote", description=LEGAL), None, None, "unclear"),
    (job("Remote", description=PAY), None, None, "unclear"),
    (job("Remote", description="We build culture together, regardless of location."), None, None, "unclear"),
    (job("Remote", description="You can work remotely from anywhere in the UK or the Netherlands."),
     False, False, "countries"),
    (job("The Netherlands", description="This position can be remote in any EMEA country."), None, False, "regions"),
    (job("Remote", description="Must be based in or within one hour of the Eastern Time zone."),
     False, False, "regions"),
    (job("Remote - Canada", description="This role is remote and open to candidates based in the US."),
     False, False, "countries"),
    (job("Remote", description="This role is open to candidates based in North America and Europe."),
     False, False, "regions"),
    (job("Remote", description="This role is fully remote-based in Americas or European time zones."),
     False, False, "regions"),
    (job("Remote", description="We hire globally and you can apply from Pakistan or India."), True, True, "worldwide"),
    (job("Remote", description="Requirements: US work authorization and 5 years of Python."), False, False, "countries"),
    (job("Remote", description="We are hiring across APAC, including India."), True, True, "regions"),
    (job("Remote", description="We are hiring in London and Berlin."), False, False, "countries"),
])
def test_classify_cases(j, pk, inn, scope):
    result = classify(j)
    assert (result.eligible_pk, result.eligible_in, result.remote_scope) == (pk, inn, scope), result


def test_description_restriction_beats_bare_remote_location():
    result = classify(job("Remote", description="We are a remote team. You must be based in the United States. "
                                               "We love Python."))
    assert result.eligible_pk is False and result.eligible_in is False
    assert result.evidence == "You must be based in the United States."
    assert result.confidence >= 0.8 and result.method == "rules"


def test_evidence_is_a_sentence_from_the_text():
    text = "About us.\nThis is a remote position open to candidates residing in the US.\nPerks."
    result = classify(job("Remote", description=text))
    assert result.evidence in text and "residing in the US" in result.evidence


def test_location_evidence_and_lists():
    result = classify(job("Remote - United States", areas=["Remote - United States", "Remote - Canada"]))
    assert result.eligible_countries == ["ca", "us"] and result.eligible_regions == []
    assert "Remote - United States" in result.evidence


def test_unclear_has_low_confidence():
    result = classify(job("Remote"))
    assert result.confidence < 0.5 and result.evidence == ""


def test_rules_version_is_an_int():
    assert isinstance(RULES_VERSION, int) and RULES_VERSION >= 1
