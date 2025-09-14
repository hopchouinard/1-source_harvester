from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz_ok(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"ok", "degraded"}
    assert set(["status", "env", "provider"]).issubset(data.keys())
    assert "checks" in data
