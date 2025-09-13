from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import ProviderResult, SearchProviderAdapter
from app.config import AppConfig
from app.core.hashing import url_hash
from app.core.schema import ProviderNeutralQuery
from app.db.queries import (
    bulk_insert_processed,
    bulk_insert_raw,
    insert_search_run,
)


class OrchestratorError(Exception):
    pass


class AllProvidersFailed(OrchestratorError):
    pass


@dataclass
class ProcessedResult:
    url: str
    providers: list[str]
    confidence: int
    dedupe_hash: str


@dataclass
class OrchestratorOutput:
    processed: list[ProcessedResult]
    providers_used: list[str]
    per_provider_query_used: dict[str, str]
    run_id: int


async def orchestrate(
    *,
    original_query: str,
    rewritten_template: str,
    schema: ProviderNeutralQuery,
    config: AppConfig,
    adapters: Mapping[str, SearchProviderAdapter],
    session: AsyncSession,
    run_config: dict | None = None,
) -> OrchestratorOutput:
    # Determine providers to call
    if config.search.provider != "auto":
        provider_list = [config.search.provider]
    else:
        provider_list = list(config.search.cascade_order)

    # Filter to available adapters
    to_call = [p for p in provider_list if p in adapters]
    if not to_call:
        raise AllProvidersFailed("No available providers to call")

    providers_used: list[str] = []
    per_provider_query_used: dict[str, str] = {}
    raw_rows: list[dict[str, Any]] = []
    results_by_url: dict[str, set[str]] = {}

    # Insert run row early to obtain run_id
    run_id = await insert_search_run(
        session,
        query=original_query,
        rewritten_template=rewritten_template,
        config=run_config or {},
        providers_used=to_call,
    )

    for name in to_call:
        adapter = adapters[name]
        try:
            res: ProviderResult = await adapter.search(schema, options=None)
        except Exception:
            continue
        providers_used.append(name)
        per_provider_query_used[name] = res.query_used
        # raw rows
        for rank, url in enumerate(res.urls, start=1):
            raw_rows.append({
                "provider": name,
                "url": url,
                "rank": rank,
                "meta": {"queryUsed": res.query_used},
            })
            results_by_url.setdefault(url, set()).add(name)

    if not providers_used:
        raise AllProvidersFailed("All providers failed or returned no data")

    # Persist raw rows
    await bulk_insert_raw(session, run_id, raw_rows)

    # Merge/dedupe processed rows
    processed: list[ProcessedResult] = []
    for url, provs in results_by_url.items():
        prov_list = sorted(provs)
        processed.append(
            ProcessedResult(
                url=url,
                providers=prov_list,
                confidence=len(provs),
                dedupe_hash=url_hash(url),
            )
        )

    # Persist processed rows
    await bulk_insert_processed(
        session,
        run_id,
        [
            {
                "url": pr.url,
                "providers": pr.providers,
                "confidence": pr.confidence,
                "dedupe_hash": pr.dedupe_hash,
            }
            for pr in processed
        ],
    )

    return OrchestratorOutput(
        processed=processed,
        providers_used=providers_used,
        per_provider_query_used=per_provider_query_used,
        run_id=run_id,
    )

