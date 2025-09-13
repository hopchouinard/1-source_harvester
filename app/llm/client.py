from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import httpx

from app.config import LLMSettings, load_runtime_config
from app.core.schema import ProviderNeutralQuery


class LLMError(Exception):
    """Base LLM exception."""


class LLMServiceError(LLMError):
    """Remote service unavailable or failed (maps to 502)."""


class LLMValidationError(LLMError):
    """LLM output invalid (maps to 400)."""


class QueryCacheRepo(Protocol):
    async def get_cached_rewritten_template(self, original_query: str) -> Optional[str]:
        ...

    async def insert_query_cache(self, original_query: str, rewritten_template: str) -> None:
        ...


@dataclass
class LLMClient:
    settings: LLMSettings
    api_key: str
    prompt_text: str
    http: httpx.AsyncClient
    cache_repo: Optional[QueryCacheRepo] = None

    OPENAI_URL = "https://api.openai.com/v1/chat/completions"

    @classmethod
    def from_runtime_config(
        cls,
        api_key: Optional[str] = None,
        http: Optional[httpx.AsyncClient] = None,
        cache_repo: Optional[QueryCacheRepo] = None,
    ) -> "LLMClient":
        rc = load_runtime_config()
        # Resolve API key from env if not provided
        resolved_key = api_key or (  # prefer standard env
            __import__("os").environ.get("OPENAI_API_KEY")
            or __import__("os").environ.get("SH_OPENAI_API_KEY", "")
        )
        if not resolved_key and rc.settings.llm.provider == "openai":
            # Don't enforce here; config loader enforces in prod. Allow tests to inject/mocks.
            resolved_key = "sk-test"
        prompt_bytes = rc.prompt_path.read_bytes()
        prompt_text = prompt_bytes.decode("utf-8")
        client = http or httpx.AsyncClient(timeout=rc.settings.llm.timeout_seconds)
        return cls(settings=rc.settings.llm, api_key=resolved_key, prompt_text=prompt_text, http=client, cache_repo=cache_repo)

    async def rewrite_query(self, user_query: str) -> tuple[ProviderNeutralQuery, str]:
        """Rewrite a user query to a provider-neutral schema using the configured LLM.

        Returns (validated_schema, rewritten_template_json_str).
        """
        # Cache lookup
        if self.cache_repo is not None:
            cached = await self.cache_repo.get_cached_rewritten_template(user_query)
            if cached:
                try:
                    data = json.loads(cached)
                    schema = ProviderNeutralQuery.model_validate(data)
                    return schema, cached
                except Exception as e:  # fall through to regenerate if cache is corrupt
                    pass

        if self.settings.provider != "openai":
            raise LLMServiceError(f"LLM provider {self.settings.provider} not implemented")

        messages = [
            {"role": "system", "content": self.prompt_text},
            {
                "role": "user",
                "content": (
                    "Rewrite the following natural language query into the strict JSON schema.\n"
                    "Return ONLY valid JSON with no markdown fences.\n"
                    f"Query: {user_query}"
                ),
            },
        ]

        payload: dict[str, Any] = {
            "model": self.settings.model or "gpt-4o-mini",
            "temperature": self.settings.temperature,
            "max_tokens": 512,
            "messages": messages,
        }

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            resp = await self.http.post(self.OPENAI_URL, headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise LLMServiceError("LLM request timed out") from e
        except httpx.HTTPError as e:
            raise LLMServiceError("LLM HTTP error") from e

        if resp.status_code >= 500:
            raise LLMServiceError(f"LLM upstream error: {resp.status_code}")
        if resp.status_code >= 400:
            # Treat 4xx from provider as service errors (bad request formatting, quota, etc.)
            raise LLMServiceError(f"LLM request failed: {resp.status_code}")

        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMServiceError("Unexpected LLM response structure") from e

        # Parse JSON content strictly
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMValidationError("LLM did not return valid JSON") from e

        try:
            schema = ProviderNeutralQuery.model_validate(data)
        except Exception as e:
            raise LLMValidationError("LLM JSON did not match schema") from e

        # Cache insert
        if self.cache_repo is not None:
            try:
                await self.cache_repo.insert_query_cache(user_query, json.dumps(data, separators=(",", ":")))
            except Exception:
                # Cache failure should not break the flow
                pass

        return schema, json.dumps(data, separators=(",", ":"))
