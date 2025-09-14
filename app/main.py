from __future__ import annotations

from typing import Any, AsyncIterator

from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Depends

from app.config import load_runtime_config
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schema import ProviderNeutralQuery
from app.core.orchestrator import orchestrate, AllProvidersFailed
from app.db.session import get_session_factory
from app.db import queries as repo
from app.llm.client import LLMClient, LLMServiceError, LLMValidationError
from app.observability.logging import configure_logging
from app.observability.health import db_ping, http_probe


def build_adapters() -> dict[str, Any]:
    # Lazy import to avoid heavy deps at import time
    import os
    from app.adapters.serper import SerperAdapter
    from app.adapters.google import GoogleCSEAdapter
    from app.adapters.brave import BraveAdapter

    adapters: dict[str, Any] = {}
    if (k := os.getenv("SH_SERPER_KEY")):
        adapters["serper"] = SerperAdapter(api_key=k)
    gk = os.getenv("SH_GOOGLE_API_KEY")
    gcx = os.getenv("SH_GOOGLE_CSE_ID")
    if gk and gcx:
        adapters["google"] = GoogleCSEAdapter(api_key=gk, cse_id=gcx)
    if (bk := os.getenv("SH_BRAVE_KEY")):
        adapters["brave"] = BraveAdapter(api_key=bk)
    return adapters


class SearchOptions(BaseModel):
    lang: str | None = None
    geo: str | None = None
    maxResults: int | None = Field(default=None, ge=1, le=100)


class SearchRunRequest(BaseModel):
    query: str
    options: SearchOptions | None = None


class ProcessedOut(BaseModel):
    url: str
    providers: list[str]
    confidence: int


class SearchRunResponse(BaseModel):
    id: int
    providers_used: list[str]
    per_provider_query_used: dict[str, str]
    processed: list[ProcessedOut]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.runtime_config = load_runtime_config()
    configure_logging(debug=app.state.runtime_config.settings.debug)
    # Load API bearer token from env for security
    import os
    app.state.api_bearer_token = os.getenv("SH_API_BEARER_TOKEN")
    try:
        yield
    finally:
        # Place shutdown hooks here when added (DB close, etc.)
        pass


def create_app() -> FastAPI:
    app = FastAPI(title="Source Harvester", version="0.1.0", lifespan=lifespan)

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        rc = app.state.runtime_config
        # DB ping and HTTP probe
        db_ok = await db_ping(get_session_factory())
        http_ok = await http_probe()
        return {
            "status": "ok" if (db_ok and http_ok) else "degraded",
            "env": rc.settings.environment,
            "provider": rc.settings.search.provider,
            "checks": {"db": db_ok, "http": http_ok},
        }

    

    def _check_bearer(authorization: str | None) -> None:
        expected: str | None = getattr(app.state, "api_bearer_token", None)
        if not expected:
            # allow runtime env override for tests or dynamic config
            import os as _os
            expected = _os.getenv("SH_API_BEARER_TOKEN")
        if not expected:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization.split(" ", 1)[1]
        if token != expected:
            raise HTTPException(status_code=401, detail="invalid bearer token")

    def require_bearer(authorization: str | None = Header(None)) -> None:
        # Enforce bearer on POST routes only when a token is configured
        _check_bearer(authorization)

    @app.post("/search-runs", status_code=201, response_model=SearchRunResponse)
    async def create_search_run(payload: SearchRunRequest, _: None = Depends(require_bearer)) -> SearchRunResponse:
        rc = app.state.runtime_config
        # Prepare DB session
        Session = get_session_factory()
        async with Session() as session:  # type: AsyncSession
            # Ensure schema exists (tests/dev). In production, rely on Alembic.
            await repo.init_models(session)
            # Enforce raw query length limit
            if len(payload.query) > 512:
                raise HTTPException(status_code=400, detail="query length exceeds 512 characters")
            # Cache lookup
            cached = await repo.get_cached_rewritten_template(session, payload.query)
            if cached:
                data = __import__("json").loads(cached)
                schema = ProviderNeutralQuery.model_validate(data)
                template = cached
            else:
                # Call LLM
                try:
                    llm = LLMClient.from_runtime_config()
                    schema, template = await llm.rewrite_query(payload.query)
                except LLMValidationError as e:
                    raise HTTPException(status_code=400, detail=str(e))
                except LLMServiceError as e:
                    raise HTTPException(status_code=502, detail=str(e))
                # Insert cache
                await repo.insert_query_cache(session, payload.query, template)

            # Orchestrate providers
            adapters = build_adapters()
            try:
                out = await orchestrate(
                    original_query=payload.query,
                    rewritten_template=template,
                    schema=schema,
                    config=rc.settings,
                    adapters=adapters,
                    session=session,
                    run_config={"options": payload.options.model_dump() if payload.options else {}},
                )
            except AllProvidersFailed as e:
                raise HTTPException(status_code=502, detail=str(e))

            return SearchRunResponse(
                id=out.run_id,
                providers_used=out.providers_used,
                per_provider_query_used=out.per_provider_query_used,
                processed=[
                    ProcessedOut(url=p.url, providers=p.providers, confidence=p.confidence)
                    for p in out.processed
                ],
            )

    @app.get("/search-runs/{run_id}")
    async def get_search_run(run_id: int, authorization: str | None = Header(None)) -> Any:
        Session = get_session_factory()
        # In prod, enforce bearer for GET as well
        import os as _os
        env_val = app.state.runtime_config.settings.environment
        if env_val == "prod" or _os.getenv("SH_ENVIRONMENT") == "prod":
            _check_bearer(authorization)
        async with Session() as session:
            # Ensure schema exists for dev/test
            await repo.init_models(session)
            data = await repo.get_run(session, run_id)
            if not data:
                raise HTTPException(status_code=404, detail="run not found")
            run = data["run"]
            return {
                "id": run["id"],
                "query": run["query"],
                "rewritten_template": run["rewritten_template"],
                "providers_used": run["providers_used"],
                "processed": [
                    {"url": r["url"], "providers": r["providers"], "confidence": r["confidence"]}
                    for r in data["processed"]
                ],
            }

    return app


# For ASGI servers
app = create_app()
