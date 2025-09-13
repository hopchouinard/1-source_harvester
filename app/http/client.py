from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Protocol

import httpx


logger = logging.getLogger("app.http")


class TelemetryHook(Protocol):
    async def on_request(self, request: httpx.Request) -> None:  # pragma: no cover - interface
        ...

    async def on_response(self, response: httpx.Response) -> None:  # pragma: no cover - interface
        ...


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": "source-harvester/0.1.0",
        "Accept": "application/json, */*;q=0.1",
    }


def _event_hooks(telemetry: Iterable[TelemetryHook] | None = None) -> dict[str, list[Callable[[Any], Any]]]:
    telemetry = list(telemetry or [])

    async def on_request(request: httpx.Request) -> None:
        run_id = request.headers.get("X-Run-Id")
        request.extensions["_start_ts"] = time.perf_counter()
        logger.debug(
            "http.request",
            extra={"method": request.method, "url": str(request.url), "run_id": run_id},
        )
        for t in telemetry:
            try:
                await t.on_request(request)
            except Exception:
                logger.debug("telemetry.on_request failed", exc_info=True)

    async def on_response(response: httpx.Response) -> None:
        request = response.request
        run_id = request.headers.get("X-Run-Id")
        start_ts = request.extensions.get("_start_ts")
        elapsed_ms = None
        if isinstance(start_ts, (int, float)):
            elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        logger.debug(
            "http.response",
            extra={
                "method": request.method,
                "url": str(request.url),
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
                "run_id": run_id,
            },
        )
        for t in telemetry:
            try:
                await t.on_response(response)
            except Exception:
                logger.debug("telemetry.on_response failed", exc_info=True)

    return {"request": [on_request], "response": [on_response]}


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_base_s: float = 0.25
    jitter_s: float = 0.1
    retry_on_status: tuple[int, ...] = field(
        default_factory=lambda: tuple([429] + list(range(500, 600)))
    )


def build_async_client(
    *,
    timeout_s: float = 4.0,
    headers: Optional[dict[str, str]] = None,
    telemetry: Iterable[TelemetryHook] | None = None,
) -> httpx.AsyncClient:
    merged_headers = _default_headers()
    if headers:
        merged_headers.update(headers)
    return httpx.AsyncClient(timeout=timeout_s, headers=merged_headers, event_hooks=_event_hooks(telemetry))


async def request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    json: Any | None = None,
    data: Any | None = None,
    policy: RetryPolicy | None = None,
    run_id: str | None = None,
) -> httpx.Response:
    policy = policy or RetryPolicy()
    attempt = 0
    last_exc: Exception | None = None

    req_headers = dict(headers or {})
    if run_id:
        req_headers.setdefault("X-Run-Id", run_id)

    while attempt < policy.max_attempts:
        attempt += 1
        try:
            response = await client.request(method, url, headers=req_headers, params=params, json=json, data=data)
        except httpx.RequestError as e:
            last_exc = e
            if attempt >= policy.max_attempts:
                raise
        else:
            if response.status_code in policy.retry_on_status and attempt < policy.max_attempts:
                # backoff and retry
                delay = policy.backoff_base_s * (2 ** (attempt - 1)) + random.uniform(0, policy.jitter_s)
                await asyncio.sleep(delay)
                continue
            return response

        # if exception and we still have attempts, backoff
        if attempt < policy.max_attempts:
            delay = policy.backoff_base_s * (2 ** (attempt - 1)) + random.uniform(0, policy.jitter_s)
            await asyncio.sleep(delay)

    # If loop exits without return, raise last exception if any
    if last_exc:
        raise last_exc

    # Fallback (should not reach)
    raise RuntimeError("request_with_retries exhausted without response or exception")

