from __future__ import annotations

import json

import pytest

from app.core.schema import ProviderNeutralQuery


@pytest.fixture(autouse=True)
def set_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("SH_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'auth.sqlite3'}")


@pytest.mark.asyncio
async def test_post_requires_bearer_when_configured(monkeypatch: pytest.MonkeyPatch):
    # Configure API token
    monkeypatch.setenv("SH_API_BEARER_TOKEN", "t0k3n")

    # Patch LLM and adapters
    async def fake_rewrite(self, user_query: str):
        data = {"keywords": ["openai"]}
        return ProviderNeutralQuery.model_validate(data), json.dumps(data)

    monkeypatch.setenv("SH_SERPER_KEY", "serper")
    monkeypatch.setattr("app.llm.client.LLMClient.rewrite_query", fake_rewrite)

    from app.main import create_app
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    app = create_app()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Missing Authorization
            resp = await client.post("/search-runs", json={"query": "openai"})
            assert resp.status_code == 401

            # With Authorization
            resp2 = await client.post("/search-runs", headers={"Authorization": "Bearer t0k3n"}, json={"query": "openai"})
            assert resp2.status_code in {201, 502}  # 502 if no adapters configured


@pytest.mark.asyncio
async def test_get_requires_bearer_in_prod(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SH_ENVIRONMENT", "prod")
    monkeypatch.setenv("SH_API_BEARER_TOKEN", "abc")
    # satisfy secret validation in prod
    monkeypatch.setenv("SH_SERPER_KEY", "serper")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    # GET should require token in prod
    from app.main import create_app
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    app = create_app()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/search-runs/1")
            assert resp.status_code == 401
            resp2 = await client.get("/search-runs/1", headers={"Authorization": "Bearer abc"})
            # 404 since run doesn't exist, but auth accepted
            assert resp2.status_code in {200, 404}
