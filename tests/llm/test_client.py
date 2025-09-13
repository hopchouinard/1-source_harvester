from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.llm.client import LLMClient, LLMServiceError, LLMValidationError
from app.config import load_runtime_config


class InMemoryCacheRepo:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def get_cached_rewritten_template(self, original_query: str):
        return self.store.get(original_query)

    async def insert_query_cache(self, original_query: str, rewritten_template: str):
        self.store[original_query] = rewritten_template


def make_client(cache: InMemoryCacheRepo | None = None) -> LLMClient:
    rc = load_runtime_config()
    return LLMClient(
        settings=rc.settings.llm,
        api_key="sk-test",
        prompt_text="Return JSON with fields: keywords, boolean, filters",
        http=httpx.AsyncClient(timeout=rc.settings.llm.timeout_seconds),
        cache_repo=cache,
    )


@pytest.mark.asyncio
@respx.mock
async def test_rewrite_query_success_parses_and_validates():
    client = make_client()
    route = respx.post(LLMClient.OPENAI_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "keywords": ["openai", "api"],
                                    "boolean": "AND",
                                    "filters": {
                                        "sites": ["openai.com"],
                                        "date_after": "{{yesterday}}",
                                        "max_results": 10,
                                    },
                                }
                            )
                        }
                    }
                ]
            },
        )
    )
    schema, template = await client.rewrite_query("what is the OpenAI api?")
    assert schema.keywords == ["openai", "api"]
    assert "\"keywords\"" in template
    await client.http.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_rewrite_query_invalid_json_raises_validation_error():
    client = make_client()
    respx.post(LLMClient.OPENAI_URL).mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]}),
    )
    with pytest.raises(LLMValidationError):
        await client.rewrite_query("q")
    await client.http.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_rewrite_query_schema_validation_error():
    client = make_client()
    respx.post(LLMClient.OPENAI_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"keywords": [], "filters": {}})}}
                ]
            },
        )
    )
    with pytest.raises(LLMValidationError):
        await client.rewrite_query("q")
    await client.http.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_rewrite_query_timeout_maps_to_service_error():
    client = make_client()

    def raise_timeout(request):
        raise httpx.TimeoutException("timeout")

    respx.post(LLMClient.OPENAI_URL).mock(side_effect=raise_timeout)
    with pytest.raises(LLMServiceError):
        await client.rewrite_query("q")
    await client.http.aclose()


@pytest.mark.asyncio
async def test_cache_lookup_hit_bypasses_http():
    cache = InMemoryCacheRepo()
    cached_template = json.dumps({"keywords": ["cached"], "filters": {}})
    await cache.insert_query_cache("q", cached_template)
    client = make_client(cache)
    schema, template = await client.rewrite_query("q")
    assert schema.keywords == ["cached"]
    assert template == cached_template
    await client.http.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_cache_insert_on_miss():
    cache = InMemoryCacheRepo()
    client = make_client(cache)
    respx.post(LLMClient.OPENAI_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"keywords": ["x"], "filters": {}})}}
                ]
            },
        )
    )
    schema, template = await client.rewrite_query("q2")
    assert await cache.get_cached_rewritten_template("q2") == template
    await client.http.aclose()
