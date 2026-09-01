from datetime import date

import pytest

from muster.rulebook.loader import for_code, load_all


def test_every_shipped_jurisdiction_loads():
    codes = set(load_all())
    assert codes == {"us-or", "us-il-chicago", "us-ny-nyc-fastfood", "us-ny-nyc-retail"}


def test_for_code_returns_the_version_in_force_on_a_date():
    rules = for_code("us-il-chicago", on=date(2026, 9, 1))
    assert rules.notice_hours == 336            # 14 days
    assert rules.rest_hours == 10.0


def test_an_unknown_jurisdiction_raises_rather_than_defaulting():
    """Unknown is never free. A missing rulebook must not silently price at zero."""
    with pytest.raises(KeyError, match="us-tx-austin"):
        for_code("us-tx-austin", on=date(2026, 9, 1))


def test_a_date_before_any_version_took_effect_raises():
    with pytest.raises(LookupError, match="no version of us-or"):
        for_code("us-or", on=date(2000, 1, 1))


def test_every_jurisdiction_carries_a_government_citation():
    for versions in load_all().values():
        for rules in versions:
            assert rules.citation.startswith("https://")
            assert ".gov" in rules.citation
