from __future__ import annotations

import json
import os
from dataclasses import dataclass

import pytest

from app.core.schema import ProviderNeutralQuery


@dataclass
class FakeAdapter:
    name: str
    urls: list[str]
    query_used: str

    async def search(self, schema, options=None):
        from app.adapters.base import ProviderResult

        return ProviderResult(provider=self.name, query_used=self.query_used, urls=self.urls, meta={})


@pytest.fixture(autouse=True)
def set_test_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("SH_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'api.sqlite3'}")


@pytest.mark.asyncio
async def test_post_search_runs_happy_path(monkeypatch: pytest.MonkeyPatch, client):
    # Patch LLM to return fixed schema
    async def fake_rewrite(self, user_query: str):
        data = {"keywords": ["openai"], "filters": {"max_results": 5}}
        return ProviderNeutralQuery.model_validate(data), json.dumps(data)

    monkeypatch.setattr("app.llm.client.LLMClient.rewrite_query", fake_rewrite)

    # Patch adapters to avoid external calls
    def fake_build_adapters():
        return {
            "serper": FakeAdapter(name="serper", urls=["https://a", "https://b"], query_used="q-serper"),
            "google": FakeAdapter(name="google", urls=["https://b", "https://c"], query_used="q-google"),
        }

    monkeypatch.setattr("app.main.build_adapters", fake_build_adapters)

    resp = await client.post("/search-runs", json={"query": "what is openai api"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] > 0
    assert sorted(data["providers_used"]) == ["google", "serper"]
    proc = {p["url"]: p for p in data["processed"]}
    assert proc["https://b"]["confidence"] == 2

    # GET the run
    rid = data["id"]
    get_resp = await client.get(f"/search-runs/{rid}")
    assert get_resp.status_code == 200
    j = get_resp.json()
    assert j["id"] == rid
    assert len(j["processed"]) == 3


@pytest.mark.asyncio
async def test_post_search_runs_llm_validation_error(monkeypatch: pytest.MonkeyPatch, client):
    from app.llm.client import LLMValidationError

    async def bad_rewrite(self, user_query: str):
        raise LLMValidationError("bad json")

    monkeypatch.setattr("app.llm.client.LLMClient.rewrite_query", bad_rewrite)
    monkeypatch.setattr("app.main.build_adapters", lambda: {})

    resp = await client.post("/search-runs", json={"query": "bad"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_post_search_runs_all_providers_failed(monkeypatch: pytest.MonkeyPatch, client):
    # Good LLM, but no adapters
    async def ok_rewrite(self, user_query: str):
        data = {"keywords": ["openai"]}
        return ProviderNeutralQuery.model_validate(data), json.dumps(data)

    monkeypatch.setattr("app.llm.client.LLMClient.rewrite_query", ok_rewrite)
    monkeypatch.setattr("app.main.build_adapters", lambda: {})

    resp = await client.post("/search-runs", json={"query": "openai"})
    assert resp.status_code == 502

