import pytest

from enrich.geo import Places, membership, merge, parse_places


@pytest.mark.parametrize("text,countries,regions", [
    ("Remote - United States", {"us"}, set()),
    ("San Francisco, CA", {"us"}, set()),
    ("Toronto, ON", {"ca"}, set()),
    ("Remote, Bangalore", {"in"}, set()),
    ("Lahore, Pakistan", {"pk"}, set()),
    ("London, UK", {"gb"}, set()),
    ("Remote Spain", {"es"}, set()),
    ("Home based - Worldwide", set(), {"worldwide"}),
    ("Remote, AMER", set(), {"americas"}),
    ("EMEA", set(), {"emea"}),
    ("Asia", set(), {"apac"}),
    ("Canada - Remote (ON, AB, BC, or NS Only)", {"ca"}, set()),
    ("Remote, Canada; Remote, United States", {"ca", "us"}, set()),
    ("Republic of Ireland (Remote)", {"ie"}, set()),
    ("New York, NY (HQ)", {"us"}, set()),
    ("Remote", set(), set()),
])
def test_parse_places_countries_and_cities(text, countries, regions):
    places = parse_places(text)
    assert places.countries == countries
    assert places.regions == regions


def test_parse_places_flags_remote_words():
    assert parse_places("Remote, Bangalore").remote
    assert not parse_places("Lahore, Pakistan").remote


def test_parse_places_ambiguous_codes():
    assert parse_places("Indianapolis, IN").countries == {"us"}
    assert parse_places("Remote, IN").countries == set()
    assert parse_places("Remote, CA").countries == {"us"}
    assert parse_places("Remote, US").countries == {"us"}
    # free text: bare short codes are words ("join us"), only spelled-out names count
    assert parse_places("join us in building the future", structured=False).countries == set()
    assert parse_places("must reside in the U.S.", structured=False).countries == {"us"}
    assert parse_places("based in the United States or Canada", structured=False).countries == {"us", "ca"}


def test_merge_unions_places():
    merged = merge(parse_places("Remote - India"), parse_places("Remote - Pakistan"))
    assert merged.countries == {"in", "pk"} and merged.remote


@pytest.mark.parametrize("countries,regions,country,expected", [
    ({"us"}, set(), "pk", False),
    (set(), {"worldwide"}, "pk", True),
    (set(), {"apac"}, "in", True),
    (set(), {"emea"}, "pk", None),
    (set(), {"emea"}, "in", False),
    ({"us", "in"}, set(), "in", True),
    ({"us", "in"}, set(), "pk", False),
    (set(), set(), "pk", None),
    (set(), {"europe", "apac"}, "pk", True),
])
def test_membership(countries, regions, country, expected):
    places = Places(frozenset(countries), frozenset(regions), True)
    assert membership(places, country) is expected
