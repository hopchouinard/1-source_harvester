from __future__ import annotations

from dataclasses import dataclass
from itertools import chain

from hypothesis import given, strategies as st

from app.core.orchestrator import orchestrate
from app.core.schema import ProviderNeutralQuery
from app.db.queries import init_models
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


providers = st.lists(st.sampled_from(["serper", "google", "brave"]), min_size=1, max_size=3, unique=True)
url = st.from_regex(r"https://[a-z]{1,5}\.example\.com(/\w{0,5})?", fullmatch=True)


@given(providers=providers, serper_urls=st.lists(url, max_size=4, unique=True), google_urls=st.lists(url, max_size=4, unique=True), brave_urls=st.lists(url, max_size=4, unique=True))
def test_orchestrator_confidence_equals_distinct_provider_count(providers, serper_urls, google_urls, brave_urls):
    # Hypothesis test is synchronous; we run async bits via event loop using pytest's loop in suite runs.
    import asyncio
    import os

    os.environ["SH_DATABASE_URL"] = "sqlite+aiosqlite:///_orch_prop.sqlite3"

    async def run_case():
        rc = load_runtime_config()
        Session = get_session_factory()
        async with Session() as s:
            await init_models(s)
            adapters = {}
            if "serper" in providers:
                adapters["serper"] = FakeAdapter("serper", serper_urls, "q1")
            if "google" in providers:
                adapters["google"] = FakeAdapter("google", google_urls, "q2")
            if "brave" in providers:
                adapters["brave"] = FakeAdapter("brave", brave_urls, "q3")

            schema = ProviderNeutralQuery(keywords=["openai"], filters={})
            out = await orchestrate(
                original_query="q",
                rewritten_template="{}",
                schema=schema,
                config=rc.settings,
                adapters=adapters,
                session=s,
            )
            by_url = {p.url: p for p in out.processed}
            # Expected providers for each URL
            expected_map = {}
            for name, urls in [("serper", serper_urls), ("google", google_urls), ("brave", brave_urls)]:
                if name in providers:
                    for u in urls:
                        expected_map.setdefault(u, set()).add(name)
            for u, provs in expected_map.items():
                assert by_url[u].confidence == len(provs)

    asyncio.get_event_loop().run_until_complete(run_case())

