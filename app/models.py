from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func


metadata = MetaData()


queries = Table(
    "queries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("original_query", Text, nullable=False, unique=True),
    Column("rewritten_template", Text, nullable=False),
    Column("created_at", DateTime(timezone=False), server_default=func.now(), nullable=False),
)


search_runs = Table(
    "search_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("query", Text, nullable=False),
    Column("rewritten_template", Text, nullable=False),
    Column("run_timestamp", DateTime(timezone=False), server_default=func.now(), nullable=False),
    Column("config", JSON, nullable=False),
    Column("providers_used", JSON, nullable=False),  # list[str]
)


search_results_raw = Table(
    "search_results_raw",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", Integer, ForeignKey("search_runs.id", ondelete="CASCADE"), nullable=False),
    Column("provider", String(50), nullable=False),
    Column("url", Text, nullable=False),
    Column("rank", Integer, nullable=True),
    Column("meta", JSON, nullable=True),
    Column("inserted_at", DateTime(timezone=False), server_default=func.now(), nullable=False),
    Index("ix_raw_run_provider", "run_id", "provider"),
)


search_results_processed = Table(
    "search_results_processed",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", Integer, ForeignKey("search_runs.id", ondelete="CASCADE"), nullable=False),
    Column("url", Text, nullable=False),
    Column("providers", JSON, nullable=False),  # list[str], portable across DBs
    Column("confidence", Integer, nullable=False),
    Column("dedupe_hash", Text, nullable=False),
    Column("inserted_at", DateTime(timezone=False), server_default=func.now(), nullable=False),
    UniqueConstraint("run_id", "dedupe_hash", name="uq_processed_run_dedupe"),
)

