from __future__ import annotations

import pytest

from app.core.schema import ProviderNeutralQuery


def test_valid_query_minimal():
    q = ProviderNeutralQuery(keywords=["openai", "api"])
    assert q.boolean == "AND"
    assert q.filters.max_results == 50


def test_keywords_must_be_non_empty():
    with pytest.raises(Exception):
        ProviderNeutralQuery(keywords=[])


def test_keywords_limit_12():
    with pytest.raises(Exception):
        ProviderNeutralQuery(keywords=[str(i) for i in range(13)])


def test_extra_fields_forbidden():
    with pytest.raises(Exception):
        ProviderNeutralQuery(keywords=["a"], extraField=True)  # type: ignore


def test_filters_sites_limit():
    too_many = [f"site{i}.com" for i in range(21)]
    with pytest.raises(Exception):
        ProviderNeutralQuery(keywords=["a"], filters={"sites": too_many})


def test_filters_date_accepts_iso_and_placeholders():
    ProviderNeutralQuery(keywords=["a"], filters={"date_after": "2024-01-02"})
    ProviderNeutralQuery(keywords=["a"], filters={"date_after": "{{today}}"})
    ProviderNeutralQuery(keywords=["a"], filters={"date_before": "{{days_ago:7}}"})


def test_filters_date_rejects_bad_formats():
    with pytest.raises(Exception):
        ProviderNeutralQuery(keywords=["a"], filters={"date_after": "01/02/2024"})
    with pytest.raises(Exception):
        ProviderNeutralQuery(keywords=["a"], filters={"date_before": "{{unknown}}"})

