from __future__ import annotations

import os

import pytest
import pytest_asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_url, get_engine, get_session, get_session_factory


def test_get_database_url_default_and_override(monkeypatch):
    # default
    monkeypatch.delenv("SH_DATABASE_URL", raising=False)
    assert get_database_url().startswith("sqlite+aiosqlite:///")
    # override
    monkeypatch.setenv("SH_DATABASE_URL", "sqlite+aiosqlite:///./override.sqlite3")
    assert get_database_url().endswith("override.sqlite3")


@pytest.mark.asyncio
async def test_get_session_yields_asyncsession(tmp_path, monkeypatch):
    monkeypatch.setenv("SH_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'sess.sqlite3'}")
    # ensure engine/factory initialized
    _ = get_engine()
    _ = get_session_factory()
    # use get_session async generator
    agen = get_session()
    session: AsyncSession = await agen.__anext__()
    try:
        assert isinstance(session, AsyncSession)
        # Do a trivial execute via ORM connection chain: SELECT 1
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
    finally:
        try:
            await agen.__anext__()
        except StopAsyncIteration:
            pass
