import pytest

from connectors.location import classify_location


@pytest.mark.parametrize("locations,hint,remote_flag,expected", [
    (["Remote, Bangalore"], None, None, ("remote", "in")),
    (["Remote, United States"], None, None, ("remote", "remote")),
    (["Remote, Canada; Remote, United Kingdom"], None, None, ("remote", "remote")),
    (["Anywhere"], None, None, ("remote", "remote")),
    (["Lahore, Pakistan"], "hybrid", None, ("hybrid", "pk")),
    (["Karachi"], "onsite", None, ("onsite", "pk")),
    (["New York, NY"], "onsite", None, None),
    (["New York, NY (HQ)", "Remote (US)"], "hybrid", True, ("remote", "remote")),
    (["London"], "hybrid", None, None),
    (["Remote - India", "Remote - Pakistan"], None, None, ("remote", "remote")),
    (["Bengaluru, India"], None, None, ("onsite", "in")),
    ([], "remote", None, ("remote", "remote")),
    ([], None, None, None),
])
def test_classify_location_cases(locations, hint, remote_flag, expected):
    assert classify_location(locations, hint, remote_flag) == expected
