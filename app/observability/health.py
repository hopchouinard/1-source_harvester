from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.http.client import build_async_client


async def db_ping(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    try:
        engine: AsyncEngine = session_factory.kw["bind"]  # type: ignore[attr-defined]
    except Exception:
        # Fallback if factory not bound
        engine = session_factory().bind  # type: ignore[assignment]
    try:
        async with engine.begin() as conn:  # type: ignore[arg-type]
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def http_probe(url: str = "https://example.com", timeout_s: float = 2.0) -> bool:
    client = build_async_client(timeout_s=timeout_s)
    try:
        resp = await client.get(url)
        return 200 <= resp.status_code < 500
    except Exception:
        return False
    finally:
        await client.aclose()

