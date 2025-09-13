from __future__ import annotations

import httpx
import pytest
import respx

from app.adapters.google import GOOGLE_CSE_URL, GoogleCSEAdapter
from app.core.schema import ProviderNeutralQuery


@pytest.mark.asyncio
@respx.mock
async def test_google_cse_search_success():
    adapter = GoogleCSEAdapter(api_key="g-key", cse_id="cse-1")
    schema = ProviderNeutralQuery(keywords=["openai"], filters={"lang": "en", "geo": "US", "max_results": 3})

    def handler(request: httpx.Request):
        params = dict(request.url.params)
        assert params["key"] == "g-key"
        assert params["cx"] == "cse-1"
        assert params["lr"] == "lang_en"
        assert params["gl"] == "US"
        return httpx.Response(200, json={"items": [{"link": "https://openai.com"}]})

    respx.get(GOOGLE_CSE_URL).mock(side_effect=handler)

    result = await adapter.search(schema)
    assert result.provider == "google"
    assert result.urls == ["https://openai.com"]

