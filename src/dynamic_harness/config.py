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
    provider_force: str | None = Field(
        default=None,
        description="OpenRouter provider slug to pin exclusively (disables fallbacks).",
    )
    verify_ssl: bool = True
    price_input_per_mtok: float | None = Field(default=None, description="USD per 1M input tokens, if known")
    price_output_per_mtok: float | None = Field(default=None, description="USD per 1M output tokens, if known")
    call_timeout_seconds: float = Field(
        default=120.0, gt=0,
        description="Timeout for a single LLM request, in seconds. A slow or stuck "
                    "provider call is abandoned after this; the agent may retry "
                    "transient failures and keeps a separate full-run budget "
                    "(`safety.timeout_seconds`) spanning its whole context.",
    )


class SafetyConfig(BaseModel):
    max_iterations: int = 500
    repeated_call_limit: int = 5
    repeated_recovery_attempts: int = Field(
        default=1, ge=0,
        description="How many times a looping agent is nudged (a plain 'you are "
                    "repeating yourself, change strategy' user message is appended "
                    "and it gets another turn) before repeated-call detection "
                    "force-fails it. 0 preserves the old behavior of failing "
                    "immediately on first detection.",
    )
    timeout_seconds: float | None = Field(
        default=None, gt=0,
        description="Wall-clock budget for a single agent's ENTIRE run (its whole "
                    "context), in seconds. After this the loop force-fails with a "
                    "timeout. None disables the wall-clock cap (cost is then "
                    "bounded only by max_iterations / max_agent_tokens). This is "
                    "separate from llm.call_timeout_seconds, which bounds a single "
                    "LLM request.",
    )
    disable_root_timeout: bool = Field(
        default=False,
        description="Exempt only the TOP (root) agent from safety.timeout_seconds. "
                    "The root's full-run wall-clock cap is cleared so it runs until "
                    "it finishes on its own; the person overseeing the run decides "
                    "when to kill it. Child agents still inherit the cap, so a stuck "
                    "child force-fails and stays recoverable via resume/self-heal. "
                    "The per-call httpx timeout (llm.call_timeout_seconds) still "
                    "bounds every individual request.",
    )
    max_agent_tokens: int | None = Field(
        default=None, ge=0,
        description="Hard cap on total tokens (prompt + completion) a single agent may "
                    "use before it is force-failed (a safety invariant). None or 0 "
                    "disables the cap. When set, it is surfaced to the agent each turn "
                    "as its live token budget. The default per-agent guidance (when no "
                    "cap is configured) recommends staying under ~50,000 total tokens for best performance.",
    )


class SelfHealConfig(BaseModel):
    """Bounded, diagnosis-driven recovery for agent runs that end in failure.

    ``max_resumes`` bounds Layer 1 (resume the same agent with a corrective
    nudge — salvages a healthy context). ``max_fresh_retries`` bounds Layer 3
    (spawn a fresh worker over the same task when the context is poisoned / rot).
    See docs/concepts/self-healing.md.
    """

    mode: bool = True
    max_resumes: int = Field(default=1, ge=0)
    max_fresh_retries: int = Field(default=1, ge=0)


class AgentConfig(BaseModel):
    environment_notes: list[str] = Field(
        default_factory=list,
        description="Extra environment instructions appended to every agent's "
                    "context observation (e.g. 'pip is unavailable'). Kept empty "
                    "by default so agents are never told false environment facts.",
    )
    references_dir: str | None = Field(
        default=None,
        description="Directory of durable, git-tracked reference docs (rationale, "
                    "tool motivations, guidelines) that survive prompt optimization. "
                    "A compact index is injected into every agent's environment; the "
                    "agent reads full bodies on demand. Defaults to 'docs/references' "
                    "relative to the working directory.",
    )
    active_turn_window: int = Field(
        default=50, ge=1,
        description="How many recent committed turns the Context Observation lists.",
    )
    stream_children: bool = Field(
        default=False,
        description="When true, an agent that delegates multiple children stays "
                    "responsive: it is re-admitted to its LLM loop as each child "
                    "settles (report/escalate/fail) instead of blocking until ALL "
                    "children finish (the default batch gather). This lets a parent "
                    "act on child events — re-delegate a failed branch, converse, "
                    "cancel the rest, or report early — before its siblings are "
                    "done. Cost: generally more LLM turns per parent. Default off "
                    "preserves the current block-until-all semantics.",
    )


class HarnessConfig(BaseModel):
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    self_heal: SelfHealConfig = Field(default_factory=SelfHealConfig)
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