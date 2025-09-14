from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.db.queries import init_models
from app.models import search_results_processed as t_processed, search_results_raw as t_raw


@dataclass
class FakeAdapter:
    name: str
    urls: list[str]
    query_used: str

    async def search(self, schema, options=None):
        from app.adapters.base import ProviderResult

        return ProviderResult(self.name, self.query_used, self.urls, {})


@pytest_asyncio.fixture
async def client(monkeypatch: pytest.MonkeyPatch, tmp_path):
    # isolate DB per test
    monkeypatch.setenv("SH_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'acc.sqlite3'}")
    # reset engine/session singletons
    import app.db.session as sess

    sess._engine = None  # type: ignore[attr-defined]
    sess._session_factory = None  # type: ignore[attr-defined]

    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        # Ensure schema exists
        Session = get_session_factory()
        async with Session() as s:
            await init_models(s)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c


@pytest.mark.asyncio
async def test_p95_latency_and_db_invariants(monkeypatch: pytest.MonkeyPatch, client: AsyncClient):
    # Patch LLM rewrite with small delay to simulate cost on cold path
    async def fake_rewrite(self, user_query: str):
        from anyio import sleep

        await sleep(0.02)
        data = {"keywords": ["openai"], "filters": {"max_results": 5}}
        return (
            __import__("app.core.schema").core.schema.ProviderNeutralQuery.model_validate(data),
            json.dumps(data),
        )

    monkeypatch.setattr("app.llm.client.LLMClient.rewrite_query", fake_rewrite)

    # Patch adapters: two providers with one overlapping URL
    def fake_build_adapters():
        return {
            "serper": FakeAdapter("serper", ["https://a", "https://b"], "q1"),
            "google": FakeAdapter("google", ["https://b", "https://c"], "q2"),
        }

    monkeypatch.setattr("app.main.build_adapters", fake_build_adapters)

    # Cold call to fill cache
    first = await client.post("/search-runs", json={"query": "acceptance openai"})
    assert first.status_code == 201
    run_id = first.json()["id"]

    # Warm path timings
    durations = []
    for _ in range(20):
        t0 = time.perf_counter()
        r = await client.post("/search-runs", json={"query": "acceptance openai"})
        t1 = time.perf_counter()
        assert r.status_code == 201
        durations.append((t1 - t0) * 1000.0)  # ms

    # Compute p95
    p95 = statistics.quantiles(durations, n=100)[94]
    # Generous threshold for CI variance; warm path should be fast
    assert p95 < 500.0

    # DB invariants: processed equals distinct URLs; raw equals sum of per-provider
    Session = get_session_factory()
    async with Session() as session:  # type: AsyncSession
        # counts for this run_id
        raw_count = await _count_where(session, t_raw, t_raw.c.run_id == run_id)
        processed_count = await _count_where(session, t_processed, t_processed.c.run_id == run_id)
        assert raw_count == 4  # 2 + 2 raw entries (overlap kept in raw)
        assert processed_count == 3  # distinct URLs: a, b, c
        # uniqueness by dedupe_hash enforced (sanity: no duplicates)
        dup_hashes = await _count_duplicate_hashes(session, run_id)
        assert dup_hashes == 0


async def _count_where(session: AsyncSession, table, where_expr) -> int:
    res = await session.execute(select(func.count()).select_from(table).where(where_expr))
    return int(res.scalar_one())


async def _count_duplicate_hashes(session: AsyncSession, run_id: int) -> int:
    # Count duplicates of dedupe_hash within a run; should be zero due to unique constraint
    res = await session.execute(
        select(t_processed.c.dedupe_hash, func.count())
        .where(t_processed.c.run_id == run_id)
        .group_by(t_processed.c.dedupe_hash)
        .having(func.count() > 1)
    )
    rows = res.fetchall()
    return len(rows)
