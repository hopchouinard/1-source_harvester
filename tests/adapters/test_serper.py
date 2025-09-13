from __future__ import annotations

import httpx
import pytest
import respx

from app.adapters.serper import SERPER_URL, SerperAdapter
from app.core.schema import ProviderNeutralQuery


@pytest.mark.asyncio
@respx.mock
async def test_serper_search_success_and_query_used():
    adapter = SerperAdapter(api_key="serper-key")
    schema = ProviderNeutralQuery(keywords=["openai", "api"], filters={"sites": ["openai.com"], "max_results": 5})

    def handler(request: httpx.Request):
        import json as _json
        assert request.headers.get("X-API-KEY") == "serper-key"
        body = _json.loads(request.content.decode()) if request.content else {}
        assert "openai api" in body["q"]
        assert "site:openai.com" in body["q"]
        return httpx.Response(200, json={"organic": [{"link": "https://openai.com"}, {"link": "https://platform.openai.com"}]})

    respx.post(SERPER_URL).mock(side_effect=handler)

    result = await adapter.search(schema)
    assert result.provider == "serper"
    assert "openai" in result.query_used
    assert len(result.urls) == 2
