from __future__ import annotations

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager
from fastapi import FastAPI

# Ensure project root is on sys.path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
