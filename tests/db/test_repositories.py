from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_engine, get_session_factory
from app.db.queries import (
    bulk_insert_processed,
    bulk_insert_raw,
    get_cached_rewritten_template,
    get_run,
    init_models,
    insert_query_cache,
    insert_search_run,
)


TEST_DB_URL = "sqlite+aiosqlite:///./_repo_test.sqlite3"


@pytest.fixture(autouse=True)
def _set_db_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SH_DATABASE_URL", TEST_DB_URL)
    # reset engine/session singletons to avoid cross-test contamination
    import app.db.session as sess
    sess._engine = None  # type: ignore[attr-defined]
    sess._session_factory = None  # type: ignore[attr-defined]
    # clean up any existing db file
    db_path = Path("_repo_test.sqlite3")
    if db_path.exists():
        db_path.unlink()


import pytest_asyncio


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = get_engine()
    Session = get_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: c.execute(text("PRAGMA foreign_keys=ON")))
    async with Session() as s:
        await init_models(s)
        yield s


@pytest.mark.asyncio
async def test_query_cache_insert_and_get(session: AsyncSession):
    q = "what is openai?"
    assert await get_cached_rewritten_template(session, q) is None
    await insert_query_cache(session, q, "{\"keywords\":[\"openai\"],\"filters\":{}}")
    tpl = await get_cached_rewritten_template(session, q)
    assert tpl and "keywords" in tpl


@pytest.mark.asyncio
async def test_insert_run_and_results(session: AsyncSession):
    run_id = await insert_search_run(
        session,
        query="q",
        rewritten_template="{}",
        config={"opt": 1},
        providers_used=["serper", "google"],
    )
    assert isinstance(run_id, int)

    await bulk_insert_raw(
        session,
        run_id,
        [
            {"provider": "serper", "url": "https://a", "rank": 1, "meta": {"m": 1}},
            {"provider": "google", "url": "https://b", "rank": 1, "meta": {}},
        ],
    )
    await bulk_insert_processed(
        session,
        run_id,
        [
            {"url": "https://a", "providers": ["serper"], "confidence": 1, "dedupe_hash": "h1"},
            {"url": "https://b", "providers": ["google"], "confidence": 1, "dedupe_hash": "h2"},
        ],
    )

    run = await get_run(session, run_id)
    assert run is not None
    assert run["run"]["id"] == run_id
    assert len(run["processed"]) == 2


@pytest.mark.asyncio
async def test_processed_unique_constraint(session: AsyncSession):
    run_id = await insert_search_run(session, "q2", "{}", {"x": 1}, ["serper"])
    await bulk_insert_processed(
        session,
        run_id,
        [
            {"url": "https://same", "providers": ["serper"], "confidence": 1, "dedupe_hash": "dup"}
        ],
    )
    with pytest.raises(IntegrityError):
        # direct execute to surface IntegrityError (bulk function commits)
        await bulk_insert_processed(
            session,
            run_id,
            [
                {"url": "https://same", "providers": ["serper"], "confidence": 2, "dedupe_hash": "dup"}
            ],
        )
