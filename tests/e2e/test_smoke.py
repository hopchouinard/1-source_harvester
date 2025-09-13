from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_smoke_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200

