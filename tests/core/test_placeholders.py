from __future__ import annotations

from datetime import date

import pytest

from app.core.placeholders import expand_date_placeholder


def test_expand_today_fixed_now():
    d = expand_date_placeholder("{{today}}", today=date(2025, 1, 15))
    assert d == "2025-01-15"


def test_expand_yesterday_fixed_now():
    d = expand_date_placeholder("{{yesterday}}", today=date(2025, 1, 15))
    assert d == "2025-01-14"


def test_expand_days_ago_fixed_now():
    d = expand_date_placeholder("{{days_ago:10}}", today=date(2025, 1, 15))
    assert d == "2025-01-05"


def test_non_placeholder_passthrough():
    assert expand_date_placeholder("2024-01-01", today=date(2025, 1, 15)) == "2024-01-01"


def test_unknown_placeholder_raises():
    with pytest.raises(ValueError):
        expand_date_placeholder("{{tomorrow}}", today=date(2025, 1, 15))

