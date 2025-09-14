from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz_includes_checks(monkeypatch, client, tmp_path):
    # Use file-based sqlite
    monkeypatch.setenv("SH_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'health.sqlite3'}")

    # Patch HTTP probe to avoid real network
    async def ok_probe(*args, **kwargs):
        return True

    monkeypatch.setattr("app.observability.health.http_probe", ok_probe)

    resp = await client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"ok", "degraded"}
    assert "checks" in data and set(data["checks"].keys()) == {"db", "http"}


@pytest.mark.asyncio
async def test_db_ping_paths(monkeypatch, tmp_path):
    from app.observability.health import db_ping
    from app.db.session import get_session_factory

    # normal path: bound factory
    monkeypatch.setenv("SH_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'health_db.sqlite3'}")
    Session = get_session_factory()
    ok = await db_ping(Session)
    assert ok is True

    # fallback path with a fake factory lacking kw['bind'] and a bad engine
    class _BadEngineCtx:
        async def __aenter__(self):
            raise RuntimeError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _BadEngine:
        def begin(self):
            return _BadEngineCtx()

    class _FakeFactory:
        kw = {}  # no bind here to trigger fallback

        def __call__(self):
            class _S:
                bind = _BadEngine()

            return _S()

    bad = await db_ping(_FakeFactory())
    assert bad is False


@pytest.mark.asyncio
async def test_http_probe_paths(respx_mock):
    from app.observability.health import http_probe
    import httpx

    # success path 200
    respx_mock.get("https://example.com").mock(return_value=httpx.Response(200))
    assert await http_probe() is True

    # 500 path returns False
    respx_mock.get("https://example.com").mock(return_value=httpx.Response(500))
    assert await http_probe() is False

    # exception path returns False
    def _raise(request):
        raise httpx.ConnectError("x")

    respx_mock.get("https://example.com").mock(side_effect=_raise)
    assert await http_probe() is False
