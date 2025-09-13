from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from app.http.client import RetryPolicy, build_async_client, request_with_retries


class TelemetryHits:
    def __init__(self):
        self.requests: int = 0
        self.responses: int = 0
        self.last_run_id: str | None = None

    async def on_request(self, request: httpx.Request) -> None:
        self.requests += 1
        self.last_run_id = request.headers.get("X-Run-Id")

    async def on_response(self, response: httpx.Response) -> None:
        self.responses += 1


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_500_then_success():
    # Arrange: endpoint returns 500, then 200
    calls = {"n": 0}

    def responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"ok": True})

    route = respx.get("https://example.com/thing").mock(side_effect=responder)

    client = build_async_client()
    try:
        resp = await request_with_retries(
            client,
            "GET",
            "https://example.com/thing",
            policy=RetryPolicy(max_attempts=3, backoff_base_s=0.01, jitter_s=0.0),
        )
        assert resp.status_code == 200
        assert calls["n"] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_429_then_success():
    calls = {"n": 0}

    def responder(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate"})
        return httpx.Response(200, json={"ok": True})

    respx.get("https://example.com/rate").mock(side_effect=responder)

    client = build_async_client()
    try:
        resp = await request_with_retries(
            client,
            "GET",
            "https://example.com/rate",
            policy=RetryPolicy(max_attempts=2, backoff_base_s=0.01, jitter_s=0.0),
        )
        assert resp.status_code == 200
        assert calls["n"] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_telemetry_hooks_called_and_run_id_propagated():
    telemetry = TelemetryHits()
    client = build_async_client(telemetry=[telemetry])
    respx.post("https://example.com/hook").mock(return_value=httpx.Response(200, json={"ok": True}))

    try:
        resp = await request_with_retries(
            client,
            "POST",
            "https://example.com/hook",
            json={"a": 1},
            run_id="run-123",
            policy=RetryPolicy(max_attempts=1),
        )
        assert resp.status_code == 200
        assert telemetry.requests == 1
        assert telemetry.responses == 1
        assert telemetry.last_run_id == "run-123"
    finally:
        await client.aclose()

