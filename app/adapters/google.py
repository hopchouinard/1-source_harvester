from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.adapters.base import ProviderResult, SearchProviderAdapter, build_query_from_schema
from app.core.schema import ProviderNeutralQuery
from app.http.client import RetryPolicy, build_async_client, request_with_retries


GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


def _to_lr(lang: str | None) -> str | None:
    if not lang:
        return None
    return f"lang_{lang}"


@dataclass
class GoogleCSEAdapter(SearchProviderAdapter):
    api_key: str
    cse_id: str
    client: httpx.AsyncClient | None = None

    name: str = "google"

    async def search(self, schema: ProviderNeutralQuery, options: dict | None = None) -> ProviderResult:
        query = build_query_from_schema(schema)
        params: dict[str, Any] = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
        }
        if schema.filters.max_results:
            params["num"] = min(schema.filters.max_results, 10)  # CSE max 10 per request
        if schema.filters.lang:
            params["lr"] = _to_lr(schema.filters.lang)
        if schema.filters.geo:
            params["gl"] = schema.filters.geo

        client = self.client or build_async_client()
        resp = await request_with_retries(
            client,
            "GET",
            GOOGLE_CSE_URL,
            params=params,
            policy=RetryPolicy(),
        )

        data = resp.json()
        urls: list[str] = []
        meta: dict[str, Any] = {}
        items = data.get("items") or []
        for item in items:
            link = item.get("link")
            if link:
                urls.append(link)
        meta["queryUsed"] = query
        meta["raw_count"] = len(items)
        return ProviderResult(provider=self.name, query_used=query, urls=urls, meta=meta)

