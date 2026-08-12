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
    verify_ssl: bool = True
    price_input_per_mtok: float | None = Field(default=None, description="USD per 1M input tokens, if known")
    price_output_per_mtok: float | None = Field(default=None, description="USD per 1M output tokens, if known")


class SafetyConfig(BaseModel):
    max_iterations: int = 500
    repeated_call_limit: int = 5


class AgentConfig(BaseModel):
    environment_notes: list[str] = Field(
        default_factory=list,
        description="Extra environment instructions appended to every agent's "
                    "context observation (e.g. 'pip is unavailable'). Kept empty "
                    "by default so agents are never told false environment facts.",
    )
    active_turn_window: int = Field(
        default=50, ge=1,
        description="How many recent committed turns the Context Observation lists.",
    )


class HarnessConfig(BaseModel):
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)


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
    try:
        raw = json.loads(cfg_path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file '{cfg_path}': {e}") from e
    return HarnessConfig.model_validate(raw)


def merge_api_key(config: HarnessConfig | None = None) -> str | None:
    """Return the API key from env only — never from the JSON config."""
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")