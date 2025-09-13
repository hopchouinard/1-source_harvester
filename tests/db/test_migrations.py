from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def alembic_cfg(db_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.mark.asyncio
async def test_alembic_initial_migration_creates_tables(tmp_path: Path):
    db_path = tmp_path / "alembic_test.sqlite3"
    url = f"sqlite:///{db_path}"

    cfg = alembic_cfg(url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert {"queries", "search_runs", "search_results_raw", "search_results_processed"}.issubset(tables)
    finally:
        engine.dispose()

