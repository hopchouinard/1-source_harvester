from __future__ import annotations

import os
import shutil

import pytest

from app.db.session import get_session_factory
from app.db.queries import init_models, insert_search_run, get_run


pytestmark = pytest.mark.skipif(
    os.getenv("CI") is None or shutil.which("docker") is None,
    reason="Runs in CI with Docker via Testcontainers",
)


@pytest.mark.asyncio
async def test_repositories_work_with_postgres_testcontainers(monkeypatch: pytest.MonkeyPatch):
    try:
        from testcontainers.postgres import PostgresContainer
    except Exception as e:  # pragma: no cover - only in CI
        pytest.skip("testcontainers not available")

    with PostgresContainer("postgres:16-alpine") as pg:
        uri = pg.get_connection_url()  # e.g., postgresql://test:test@0.0.0.0:5432/test
        async_url = uri.replace("postgresql://", "postgresql+asyncpg://")
        monkeypatch.setenv("SH_DATABASE_URL", async_url)

        Session = get_session_factory()
        async with Session() as session:
            await init_models(session)
            run_id = await insert_search_run(session, "q", "{}", {"x": 1}, ["serper"])
            data = await get_run(session, run_id)
            assert data and data["run"]["id"] == run_id

