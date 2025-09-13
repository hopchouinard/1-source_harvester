from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.adapters.base import ProviderResult, SearchProviderAdapter, build_query_from_schema
from app.core.schema import ProviderNeutralQuery
from app.http.client import RetryPolicy, build_async_client, request_with_retries


SERPER_URL = "https://google.serper.dev/search"


@dataclass
class SerperAdapter(SearchProviderAdapter):
    api_key: str
    client: httpx.AsyncClient | None = None

    name: str = "serper"

    async def search(self, schema: ProviderNeutralQuery, options: dict | None = None) -> ProviderResult:
        query = build_query_from_schema(schema)
        payload: dict[str, Any] = {"q": query}
        if schema.filters.max_results:
            payload["num"] = min(schema.filters.max_results, 20)

        headers = {"X-API-KEY": self.api_key}
        client = self.client or build_async_client()
        resp = await request_with_retries(
            client,
            "POST",
            SERPER_URL,
            headers=headers,
            json=payload,
            policy=RetryPolicy(),
        )

        data = resp.json()
        urls: list[str] = []
        meta: dict[str, Any] = {}
        organic = data.get("organic") or []
        for item in organic:
            link = item.get("link")
            if link:
                urls.append(link)
        meta["queryUsed"] = query
        meta["raw_count"] = len(organic)
        return ProviderResult(provider=self.name, query_used=query, urls=urls, meta=meta)

