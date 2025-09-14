from __future__ import annotations

import json

import pytest

from app.core.schema import ProviderNeutralQuery


@pytest.mark.asyncio
async def test_post_invalid_token(monkeypatch, client):
    monkeypatch.setenv("SH_API_BEARER_TOKEN", "correct")

    async def ok_rewrite(self, user_query: str):
        data = {"keywords": ["openai"]}
        return ProviderNeutralQuery.model_validate(data), json.dumps(data)

    monkeypatch.setattr("app.llm.client.LLMClient.rewrite_query", ok_rewrite)
    monkeypatch.setattr("app.main.build_adapters", lambda: {})

    resp = await client.post("/search-runs", headers={"Authorization": "Bearer wrong"}, json={"query": "q"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_llm_service_error_maps_to_502(monkeypatch, client):
    from app.llm.client import LLMServiceError

    async def boom(self, user_query: str):
        raise LLMServiceError("upstream")

    monkeypatch.setattr("app.llm.client.LLMClient.rewrite_query", boom)
    resp = await client.post("/search-runs", json={"query": "q"})
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_get_404(monkeypatch, client):
    resp = await client.get("/search-runs/424242")
    assert resp.status_code == 404

