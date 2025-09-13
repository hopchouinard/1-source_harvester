from __future__ import annotations

from fastapi import FastAPI

from app.main import create_app


def test_app_startup_creates_fastapi_app():
    app = create_app()
    assert isinstance(app, FastAPI)
    # openapi schema should be buildable
    assert app.openapi()  # type: ignore[truthy-function]

