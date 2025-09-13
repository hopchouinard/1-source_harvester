from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.adapters.base import ProviderResult, SearchProviderAdapter, build_query_from_schema
from app.core.schema import ProviderNeutralQuery
from app.http.client import RetryPolicy, build_async_client, request_with_retries


BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


def _freshness_from_schema(schema: ProviderNeutralQuery) -> str | None:
    # crude mapping: if date_after is days_ago:N → map small windows
    da = schema.filters.date_after or ""
    if da.startswith("{{days_ago:") and da.endswith("}}"):
        try:
            n = int(da.split(":")[1].rstrip("}"))
            if n <= 1:
                return "pd"  # past day
            if n <= 7:
                return "pw"  # past week
            if n <= 30:
                return "pm"  # past month
        except Exception:
            return None
    return None


@dataclass
class BraveAdapter(SearchProviderAdapter):
    api_key: str
    client: httpx.AsyncClient | None = None

    name: str = "brave"

    async def search(self, schema: ProviderNeutralQuery, options: dict | None = None) -> ProviderResult:
        query = build_query_from_schema(schema)
        params: dict[str, Any] = {
            "q": query,
        }
        if schema.filters.max_results:
            params["count"] = min(schema.filters.max_results, 20)
        if schema.filters.lang:
            params["search_lang"] = schema.filters.lang
        if schema.filters.geo:
            params["country"] = schema.filters.geo
        fresh = _freshness_from_schema(schema)
        if fresh:
            params["freshness"] = fresh

        headers = {"X-Subscription-Token": self.api_key}
        client = self.client or build_async_client()
        resp = await request_with_retries(
            client,
            "GET",
            BRAVE_URL,
            headers=headers,
            params=params,
            policy=RetryPolicy(),
        )
        data = resp.json()
        urls: list[str] = []
        meta: dict[str, Any] = {}
        web = data.get("web") or {}
        results = web.get("results") or []
        for item in results:
            link = item.get("url")
            if link:
                urls.append(link)
        meta["queryUsed"] = query
        meta["raw_count"] = len(results)
        return ProviderResult(provider=self.name, query_used=query, urls=urls, meta=meta)

