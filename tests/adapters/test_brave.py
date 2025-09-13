from __future__ import annotations

import httpx
import pytest
import respx

from app.adapters.brave import BRAVE_URL, BraveAdapter
from app.core.schema import ProviderNeutralQuery


@pytest.mark.asyncio
@respx.mock
async def test_brave_search_success_with_lang_geo():
    adapter = BraveAdapter(api_key="brave-key")
    schema = ProviderNeutralQuery(keywords=["openai"], filters={"lang": "en", "geo": "US", "max_results": 2})

    def handler(request: httpx.Request):
        assert request.headers.get("X-Subscription-Token") == "brave-key"
        params = dict(request.url.params)
        assert params["search_lang"] == "en"
        assert params["country"] == "US"
        return httpx.Response(200, json={"web": {"results": [{"url": "https://openai.com"}, {"url": "https://platform.openai.com"}]}})

    respx.get(BRAVE_URL).mock(side_effect=handler)

    result = await adapter.search(schema)
    assert result.provider == "brave"
    assert len(result.urls) == 2

