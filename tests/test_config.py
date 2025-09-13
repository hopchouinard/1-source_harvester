from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import AppConfig, EnvOverrides, load_runtime_config


def test_yaml_parsing_defaults():
    rc = load_runtime_config()
    assert rc.settings.environment == "dev"
    assert rc.settings.search.provider == "auto"
    assert rc.settings.search.cascade_order == ["serper", "google", "brave"]
    assert rc.prompt_path.is_file()
    assert rc.prompt_size > 0
    assert len(rc.prompt_sha256) == 64


def test_env_override_precedence(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SH_SEARCH__PROVIDER", "google")
    rc = load_runtime_config()
    assert rc.settings.search.provider == "google"


def test_secret_presence_serper_prod(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SH_ENVIRONMENT", "prod")
    monkeypatch.setenv("SH_SEARCH__PROVIDER", "serper")
    # avoid llm openai requirement for this test
    monkeypatch.setenv("SH_LLM__PROVIDER", "local")
    # Ensure not set
    monkeypatch.delenv("SH_SERPER_KEY", raising=False)
    with pytest.raises(ValueError) as e:
        load_runtime_config()
    assert "SH_SERPER_KEY" in str(e.value)

    # Now satisfy provider secret
    monkeypatch.setenv("SH_SERPER_KEY", "test-key")
    rc = load_runtime_config()
    assert rc.settings.search.provider == "serper"


def test_llm_secret_presence_openai_prod(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SH_ENVIRONMENT", "prod")
    # ensure provider requirement is satisfied independently
    monkeypatch.setenv("SH_SEARCH__PROVIDER", "serper")
    monkeypatch.setenv("SH_SERPER_KEY", "serper-key")
    monkeypatch.setenv("SH_LLM__PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SH_OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError) as e:
        load_runtime_config()
    assert "OPENAI_API_KEY" in str(e.value)

    # Now satisfy LLM secret
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    rc = load_runtime_config()
    assert rc.settings.llm.provider == "openai"


@pytest.mark.asyncio
async def test_app_boot_reads_config(app, client):
    # client fixture ensures startup ran
    assert hasattr(app.state, "runtime_config")
    rc = app.state.runtime_config
    assert isinstance(rc.settings, AppConfig)
    assert rc.settings.environment in {"dev", "test", "staging", "prod"}
