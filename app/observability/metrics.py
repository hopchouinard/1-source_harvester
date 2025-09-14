from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

import httpx

_counters: dict[tuple[str, frozenset[tuple[str, str]]], int] = defaultdict(int)
_histograms: dict[tuple[str, frozenset[tuple[str, str]]], list[float]] = defaultdict(list)


def inc(name: str, tags: dict[str, str] | None = None, value: int = 1) -> None:
    tags_f = frozenset((tags or {}).items())
    _counters[(name, tags_f)] += value


def observe(name: str, value: float, tags: dict[str, str] | None = None) -> None:
    tags_f = frozenset((tags or {}).items())
    _histograms[(name, tags_f)].append(value)


def get_counter(name: str, tags: dict[str, str] | None = None) -> int:
    return _counters.get((name, frozenset((tags or {}).items())), 0)


def get_histogram(name: str, tags: dict[str, str] | None = None) -> list[float]:
    return _histograms.get((name, frozenset((tags or {}).items())), [])


@dataclass
class MetricsTelemetryHook:
    """Telemetry hook that records basic request/response metrics."""

    def _tags(
        self, request: httpx.Request, response: httpx.Response | None = None
    ) -> dict[str, str]:
        tags = {"method": request.method, "host": request.url.host or ""}
        if response is not None:
            tags["status"] = str(response.status_code)
            tags["family"] = f"{response.status_code//100}xx"
        return tags

    async def on_request(self, request: httpx.Request) -> None:
        # Count outbound requests
        inc("http_client.requests", self._tags(request))

    async def on_response(self, response: httpx.Response) -> None:
        request = response.request
        tags = self._tags(request, response)
        inc("http_client.responses", tags)
        start_ts = request.extensions.get("_start_ts")
        start_ts_source = request.extensions.get("_start_ts_source")
        if isinstance(start_ts, int | float) and start_ts_source == "perf_counter":
            # only compute duration if the start timestamp came from perf_counter
            dur_ms = (time.perf_counter() - start_ts) * 1000
            observe("http_client.duration_ms", dur_ms, tags)
