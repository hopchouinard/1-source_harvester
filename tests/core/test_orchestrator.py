from __future__ import annotations

from dataclasses import dataclass

import pytest
import pytest_asyncio

from app.core.hashing import url_hash
from app.core.orchestrator import AllProvidersFailed, orchestrate
from app.core.schema import ProviderNeutralQuery
from app.db.queries import init_models, get_run
from app.db.session import get_engine, get_session_factory
from app.config import load_runtime_config


@dataclass
class FakeAdapter:
    name: str
    urls: list[str]
    query_used: str

    async def search(self, schema, options=None):  # noqa: D401
        from app.adapters.base import ProviderResult

        return ProviderResult(provider=self.name, query_used=self.query_used, urls=self.urls, meta={})


@pytest_asyncio.fixture
async def session(tmp_path):
    # Use sqlite file per test
    import os
    os.environ["SH_DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path/'orch.sqlite3'}"
    engine = get_engine()
    Session = get_session_factory()
    async with Session() as s:
        await init_models(s)
        yield s


@pytest.mark.asyncio
async def test_orchestrator_merge_and_persist(session):
    rc = load_runtime_config()
    schema = ProviderNeutralQuery(keywords=["openai"], filters={"max_results": 10})
    adapters = {
        "serper": FakeAdapter(name="serper", urls=["https://a", "https://b"], query_used="q1"),
        "google": FakeAdapter(name="google", urls=["https://b", "https://c"], query_used="q2"),
    }

    out = await orchestrate(
        original_query="orig q",
        rewritten_template="{\"keywords\":[\"openai\"],\"filters\":{}}",
        schema=schema,
        config=rc.settings,
        adapters=adapters,
        session=session,
        run_config={"maxResults": 10},
    )

    # Verify merge
    proc = {r.url: r for r in out.processed}
    assert proc["https://a"].confidence == 1
    assert proc["https://b"].confidence == 2
    assert proc["https://c"].confidence == 1
    assert proc["https://b"].providers == ["google", "serper"]
    assert proc["https://a"].dedupe_hash == url_hash("https://a")

    # Verify DB persisted
    run = await get_run(session, out.run_id)
    assert run is not None
    assert len(run["processed"]) == 3


@pytest.mark.asyncio
async def test_orchestrator_all_providers_failed(session):
    rc = load_runtime_config()
    schema = ProviderNeutralQuery(keywords=["openai"], filters={})
    adapters = {}
    with pytest.raises(AllProvidersFailed):
        await orchestrate(
            original_query="q",
            rewritten_template="{}",
            schema=schema,
            config=rc.settings,
            adapters=adapters,
            session=session,
        )

