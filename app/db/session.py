from __future__ import annotations

import os
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///./_test_db.sqlite3"


def get_database_url() -> str:
    return os.getenv("SH_DATABASE_URL", DEFAULT_SQLITE_URL)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_database_url(), future=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    Session = get_session_factory()
    async with Session() as session:
        yield session

