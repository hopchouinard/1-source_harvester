from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    metadata,
    queries as t_queries,
    search_results_processed as t_processed,
    search_results_raw as t_raw,
    search_runs as t_runs,
)

__all__ = [
    "init_models",
    "get_cached_rewritten_template",
    "insert_query_cache",
    "insert_search_run",
    "bulk_insert_raw",
    "bulk_insert_processed",
    "get_run",
    "list_runs",
]


async def init_models(session: AsyncSession) -> None:
    """Create all tables for the current engine (used for tests)."""
    async with session.bind.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(metadata.create_all)


async def get_cached_rewritten_template(session: AsyncSession, original_query: str) -> str | None:
    q = select(t_queries.c.rewritten_template).where(t_queries.c.original_query == original_query)
    res = await session.execute(q)
    row = res.first()
    return row[0] if row else None


async def insert_query_cache(session: AsyncSession, original_query: str, rewritten_template: str) -> None:
    try:
        stmt = insert(t_queries).values(original_query=original_query, rewritten_template=rewritten_template)
        await session.execute(stmt)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # already exists; optionally update
        # we choose to ignore duplicates to keep idempotency
        return


async def insert_search_run(
    session: AsyncSession,
    query: str,
    rewritten_template: str,
    config: dict,
    providers_used: list[str],
) -> int:
    stmt = insert(t_runs).values(
        query=query,
        rewritten_template=rewritten_template,
        config=config,
        providers_used=providers_used,
    )
    res = await session.execute(stmt)
    await session.commit()
    run_id = int(res.inserted_primary_key[0])
    return run_id


async def bulk_insert_raw(session: AsyncSession, run_id: int, rows: Iterable[dict[str, Any]]) -> None:
    payload = []
    for r in rows:
        payload.append(
            {
                "run_id": run_id,
                "provider": r.get("provider"),
                "url": r.get("url"),
                "rank": r.get("rank"),
                "meta": r.get("meta"),
            }
        )
    if payload:
        await session.execute(insert(t_raw), payload)
        await session.commit()


async def bulk_insert_processed(session: AsyncSession, run_id: int, rows: Iterable[dict[str, Any]]) -> None:
    payload = []
    for r in rows:
        payload.append(
            {
                "run_id": run_id,
                "url": r.get("url"),
                "providers": r.get("providers"),
                "confidence": r.get("confidence"),
                "dedupe_hash": r.get("dedupe_hash"),
            }
        )
    if payload:
        await session.execute(insert(t_processed), payload)
        await session.commit()


async def get_run(session: AsyncSession, run_id: int) -> dict[str, Any] | None:
    # Fetch run
    run_res = await session.execute(select(t_runs).where(t_runs.c.id == run_id))
    run_row = run_res.mappings().first()
    if not run_row:
        return None
    # Fetch processed results
    proc_res = await session.execute(select(t_processed).where(t_processed.c.run_id == run_id))
    processed = [dict(r._mapping) for r in proc_res]
    return {"run": dict(run_row), "processed": processed}


async def list_runs(session: AsyncSession, filters: dict | None = None) -> list[dict[str, Any]]:
    filters = filters or {}
    q = select(t_runs)
    if "query" in filters:
        q = q.where(t_runs.c.query == filters["query"])  # simple exact match for now
    if "from" in filters:
        q = q.where(t_runs.c.run_timestamp >= filters["from"])  # expects datetime
    if "to" in filters:
        q = q.where(t_runs.c.run_timestamp <= filters["to"])  # expects datetime
    res = await session.execute(q)
    return [dict(r._mapping) for r in res]
