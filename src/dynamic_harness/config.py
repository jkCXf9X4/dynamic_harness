from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


DEFAULT_CONFIG_FILENAME = "harness.json"
XDG_CONFIG_DIR = Path.home() / ".config" / "dynamic-harness"


class LLMProviderConfig(BaseModel):
    model: str = "deepseek/deepseek-v4-flash"
    base_url: str = "https://openrouter.ai/api/v1"
    provider_ignore: list[str] = Field(default_factory=list)
    provider_allow_fallbacks: bool = True


class SafetyConfig(BaseModel):
    max_iterations: int = 500
    repeated_call_limit: int = 5


class HarnessConfig(BaseModel):
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)


def _discover_path(explicit: str | None = None) -> Path | None:
    if explicit:
        return Path(explicit)
    cwd_candidate = Path.cwd() / DEFAULT_CONFIG_FILENAME
    if cwd_candidate.exists():
        return cwd_candidate
    xdg_candidate = XDG_CONFIG_DIR / DEFAULT_CONFIG_FILENAME
    if xdg_candidate.exists():
        return xdg_candidate
    return None


def load_harness_config(path: str | None = None) -> HarnessConfig:
    cfg_path = _discover_path(path)
    if cfg_path is None:
        return HarnessConfig()
    raw = json.loads(cfg_path.read_text())
    return HarnessConfig.model_validate(raw)


def merge_api_key(config: HarnessConfig | None = None) -> str | None:
    """Return the API key from env only — never from the JSON config."""
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")