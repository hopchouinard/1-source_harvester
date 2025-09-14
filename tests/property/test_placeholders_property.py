from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given, strategies as st

from app.core.placeholders import expand_date_placeholder


@given(n=st.integers(min_value=0, max_value=365))
def test_days_ago_property(n: int):
    base = date(2025, 1, 15)
    out = expand_date_placeholder(f"{{{{days_ago:{n}}}}}", today=base)
    assert out == (base - timedelta(days=n)).isoformat()


def test_today_yesterday_shortcuts():
    base = date(2025, 1, 15)
    assert expand_date_placeholder("{{today}}", today=base) == base.isoformat()
    assert expand_date_placeholder("{{yesterday}}", today=base) == (base - timedelta(days=1)).isoformat()

