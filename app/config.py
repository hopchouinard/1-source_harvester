from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


# ----- Models for YAML + env config -----


ProviderName = Literal["serper", "google", "brave"]


class SearchDefaultOptions(BaseModel):
    lang: str | None = None
    geo: str | None = None
    max_results: int = 50


class SearchSettings(BaseModel):
    provider: Literal["auto", ProviderName] = "auto"
    cascade_order: list[ProviderName] = Field(default_factory=lambda: ["serper", "google", "brave"])
    default_options: SearchDefaultOptions = Field(default_factory=SearchDefaultOptions)


class LLMSettings(BaseModel):
    provider: Literal["openai", "anthropic", "gemini", "local"] = "openai"
    prompt_path: str = "app/llm/prompts/rewrite_query.txt"
    model: str | None = None
    temperature: float = 0.0
    timeout_seconds: float = 5.0


class AppConfig(BaseModel):
    environment: Literal["dev", "test", "staging", "prod"] = "dev"
    debug: bool = False
    search: SearchSettings = Field(default_factory=SearchSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)


class EnvOverrides(BaseSettings):
    """Environment overrides with nested keys via SH_<NESTED> variables.

    Example: SH_SEARCH__PROVIDER=google
    """

    environment: Literal["dev", "test", "staging", "prod"] | None = None
    debug: bool | None = None
    search: SearchSettings | None = None
    llm: LLMSettings | None = None

    model_config = SettingsConfigDict(env_prefix="SH_", env_nested_delimiter="__", extra="ignore")


class RuntimeConfig(BaseModel):
    settings: AppConfig
    project_root: Path
    prompt_path: Path
    prompt_sha256: str
    prompt_size: int


# ----- Loader helpers -----


def _read_yaml(file_path: Path) -> dict:
    if not file_path.exists():
        raise FileNotFoundError(f"Config YAML not found at {file_path}")
    with file_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _resolve_prompt_path(project_root: Path, path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = project_root / p
    return p


def _get_env(name: str, fallback_names: Iterable[str] | None = None) -> str | None:
    if name in os.environ:
        return os.environ[name]
    if fallback_names:
        for alt in fallback_names:
            if alt in os.environ:
                return os.environ[alt]
    return None


def _validate_secrets(cfg: AppConfig) -> None:
    # Only enforce in prod or when explicitly enabled
    enforce = cfg.environment == "prod" or (_get_env("SH_VALIDATE_SECRETS") or "").lower() in {"1", "true", "yes"}
    if not enforce:
        return

    missing: list[str] = []

    # Providers
    def has_serper() -> bool:
        return _get_env("SH_SERPER_KEY") is not None

    def has_google() -> bool:
        return _get_env("SH_GOOGLE_API_KEY") is not None and _get_env("SH_GOOGLE_CSE_ID") is not None

    def has_brave() -> bool:
        return _get_env("SH_BRAVE_KEY") is not None

    if cfg.search.provider == "serper":
        if not has_serper():
            missing.append("SH_SERPER_KEY")
    elif cfg.search.provider == "google":
        if not has_google():
            if _get_env("SH_GOOGLE_API_KEY") is None:
                missing.append("SH_GOOGLE_API_KEY")
            if _get_env("SH_GOOGLE_CSE_ID") is None:
                missing.append("SH_GOOGLE_CSE_ID")
    elif cfg.search.provider == "brave":
        if not has_brave():
            missing.append("SH_BRAVE_KEY")
    else:  # auto
        # Require at least one configured provider in cascade_order
        available = {
            "serper": has_serper(),
            "google": has_google(),
            "brave": has_brave(),
        }
        if not any(available.get(p, False) for p in cfg.search.cascade_order):
            missing.append("One of: SH_SERPER_KEY | SH_GOOGLE_API_KEY+SH_GOOGLE_CSE_ID | SH_BRAVE_KEY")

    # LLM
    if cfg.llm.provider == "openai":
        if _get_env("OPENAI_API_KEY", ["SH_OPENAI_API_KEY"]) is None:
            missing.append("OPENAI_API_KEY")

    if missing:
        raise ValueError("Missing required secrets: " + ", ".join(missing))


def load_runtime_config(config_file: str | Path | None = None) -> RuntimeConfig:
    project_root = Path(__file__).resolve().parents[1]

    # Determine YAML path (env overrides default)
    env_path = _get_env("SH_CONFIG_FILE")
    cfg_path = Path(config_file) if config_file else (Path(env_path) if env_path else project_root / "configs" / "default.yaml")

    yaml_data = _read_yaml(cfg_path)

    # Base from YAML
    try:
        base = AppConfig.model_validate(yaml_data)
    except ValidationError as e:
        raise ValueError(f"Invalid YAML config: {e}")

    # Env overrides: merge dicts then re-validate
    overrides = EnvOverrides().model_dump(exclude_none=True)

    def deep_merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in b.items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = deep_merge(out[k], v)
            else:
                out[k] = v
        return out

    merged_dict = deep_merge(base.model_dump(), overrides)
    merged = AppConfig.model_validate(merged_dict)

    # Secrets gate
    _validate_secrets(merged)

    # Prompt hashing
    prompt_path = _resolve_prompt_path(project_root, merged.llm.prompt_path)
    if not prompt_path.exists():
        raise FileNotFoundError(f"LLM prompt not found at {prompt_path}")
    prompt_bytes = prompt_path.read_bytes()
    prompt_sha = _sha256_bytes(prompt_bytes)

    return RuntimeConfig(
        settings=merged,
        project_root=project_root,
        prompt_path=prompt_path,
        prompt_sha256=prompt_sha,
        prompt_size=len(prompt_bytes),
    )
