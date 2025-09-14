from __future__ import annotations

import httpx
import pytest
import respx

from app.http.client import build_async_client, request_with_retries
from app.observability.metrics import MetricsTelemetryHook, get_counter, get_histogram


@pytest.mark.asyncio
@respx.mock
async def test_metrics_telemetry_increments_and_observes():
    hook = MetricsTelemetryHook()
    client = build_async_client(telemetry=[hook])
    respx.get("https://metrics.example/").mock(return_value=httpx.Response(200, json={"ok": True}))
    try:
        resp = await request_with_retries(client, "GET", "https://metrics.example/")
        assert resp.status_code == 200
        # Verify counters
        assert get_counter("http_client.requests", {"method": "GET", "host": "metrics.example"}) == 1
        assert get_counter("http_client.responses", {"method": "GET", "host": "metrics.example", "status": "200", "family": "2xx"}) == 1
        # Verify durations recorded
        hist = get_histogram("http_client.duration_ms", {"method": "GET", "host": "metrics.example", "status": "200", "family": "2xx"})
        assert len(hist) == 1
        assert hist[0] >= 0.0
    finally:
        await client.aclose()

