from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_engine, get_session_factory
from app.db.queries import (
    init_models,
    insert_query_cache,
    get_cached_rewritten_template,
    insert_search_run,
    get_run,
    list_runs,
    bulk_insert_raw,
    bulk_insert_processed,
)


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncSession:
    import os

    os.environ["SH_DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path/'repo_more.sqlite3'}"
    # reset engine/session singletons
    import app.db.session as sess
    sess._engine = None  # type: ignore[attr-defined]
    sess._session_factory = None  # type: ignore[attr-defined]
    Session = get_session_factory()
    async with Session() as s:
        await init_models(s)
        yield s


@pytest.mark.asyncio
async def test_insert_query_cache_duplicate_ignored(session: AsyncSession):
    q = "dup test"
    tpl = "{\"keywords\":[\"x\"],\"filters\":{}}"
    await insert_query_cache(session, q, tpl)
    # Duplicate insert should not raise and should be ignored
    await insert_query_cache(session, q, tpl)
    read = await get_cached_rewritten_template(session, q)
    assert read == tpl


@pytest.mark.asyncio
async def test_list_runs_filters(session: AsyncSession):
    run1 = await insert_search_run(session, "q1", "{}", {"a": 1}, ["serper"])  # now
    run2 = await insert_search_run(session, "q2", "{}", {"b": 2}, ["google"])  # now

    # filter by query
    rows_q1 = await list_runs(session, {"query": "q1"})
    assert all(r["query"] == "q1" for r in rows_q1)

    # from in the past should include both
    past = datetime(2000, 1, 1)
    rows_from_past = await list_runs(session, {"from": past})
    assert {r["id"] for r in rows_from_past}.issuperset({run1, run2})

    # to in the future should include both
    future = datetime(2100, 1, 1)
    rows_to_future = await list_runs(session, {"to": future})
    assert {r["id"] for r in rows_to_future}.issuperset({run1, run2})

    # from in the far future should include none
    far_future = datetime(2200, 1, 1)
    rows_none = await list_runs(session, {"from": far_future})
    assert rows_none == []


@pytest.mark.asyncio
async def test_get_run_not_found(session: AsyncSession):
    out = await get_run(session, 999999)
    assert out is None


@pytest.mark.asyncio
async def test_bulk_insert_noop_on_empty_lists(session: AsyncSession):
    run_id = await insert_search_run(session, "q3", "{}", {}, ["serper"])
    # Should not raise or commit anything if lists are empty
    await bulk_insert_raw(session, run_id, [])
    await bulk_insert_processed(session, run_id, [])
    data = await get_run(session, run_id)
    assert data is not None
    assert data["processed"] == []
