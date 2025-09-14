from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_query_length_limit_enforced(client):
    long_query = "x" * 513
    resp = await client.post("/search-runs", json={"query": long_query})
    assert resp.status_code == 400
    assert "query length" in resp.text

