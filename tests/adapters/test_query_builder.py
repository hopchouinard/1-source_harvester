from __future__ import annotations

import pytest

from app.adapters.base import build_query_from_schema
from app.core.schema import ProviderNeutralQuery


def test_keywords_join_and_default_and_sites():
    schema = ProviderNeutralQuery(keywords=["openai", "api"], filters={"sites": ["openai.com", "platform.openai.com"]})
    q = build_query_from_schema(schema)
    # default boolean AND -> space-separated
    assert "openai api" in q
    assert "site:openai.com" in q and "site:platform.openai.com" in q


def test_keywords_join_or():
    schema = ProviderNeutralQuery(keywords=["a", "b"], boolean="OR", filters={})
    q = build_query_from_schema(schema)
    assert "a OR b" in q


def test_date_after_before_iso():
    schema = ProviderNeutralQuery(keywords=["x"], filters={"date_after": "2024-01-02", "date_before": "2024-02-03"})
    q = build_query_from_schema(schema)
    assert "after:2024-01-02" in q
    assert "before:2024-02-03" in q


def test_date_placeholders_expand():
    schema = ProviderNeutralQuery(keywords=["x"], filters={"date_after": "{{days_ago:1}}", "date_before": "{{today}}"})
    q = build_query_from_schema(schema)
    # we don't assert exact dates, just that tokens were replaced (no braces)
    assert "after:" in q and "{{" not in q
    assert "before:" in q


def test_invalid_placeholder_is_skipped():
    # force invalid placeholder via bypassing schema validation using model_dump update
    schema = ProviderNeutralQuery(keywords=["x"]).model_copy()
    # Inject an invalid placeholder; this simulates a downstream call using unvalidated data
    schema.filters.date_after = "{{tomorrow}}"  # type: ignore[attr-defined]
    q = build_query_from_schema(schema)
    # invalid placeholder should be ignored and not appear
    assert "after:" not in q

