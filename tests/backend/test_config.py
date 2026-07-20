from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dynamic_harness.config import (
    HarnessConfig,
    LLMProviderConfig,
    SafetyConfig,
    _discover_path,
    load_harness_config,
    merge_api_key,
)


class TestHarnessConfig:
    def test_defaults(self) -> None:
        cfg = HarnessConfig()
        assert cfg.llm.model == "deepseek/deepseek-v4-flash"
        assert cfg.llm.base_url == "https://openrouter.ai/api/v1"
        assert cfg.safety.max_iterations == 500
        assert cfg.safety.repeated_call_limit == 5

    def test_default_llm_provider_ignore_empty(self) -> None:
        cfg = HarnessConfig()
        assert cfg.llm.provider_ignore == []

    def test_default_llm_allow_fallbacks(self) -> None:
        cfg = HarnessConfig()
        assert cfg.llm.provider_allow_fallbacks is True

    def test_safety_config_defaults(self) -> None:
        sc = SafetyConfig()
        assert sc.max_iterations == 500
        assert sc.repeated_call_limit == 5

    def test_llm_provider_config_defaults(self) -> None:
        lpc = LLMProviderConfig()
        assert lpc.model == "deepseek/deepseek-v4-flash"
        assert lpc.base_url == "https://openrouter.ai/api/v1"
        assert lpc.provider_ignore == []
        assert lpc.provider_allow_fallbacks is True

    def test_partial_config_merge(self) -> None:
        cfg = HarnessConfig.model_validate({"llm": {"model": "custom-model"}})
        assert cfg.llm.model == "custom-model"
        assert cfg.llm.base_url == "https://openrouter.ai/api/v1"
        assert cfg.safety.max_iterations == 500


class TestLoadHarnessConfig:
    def test_load_from_file(self, tmp_path: Path) -> None:
        config_data = {
            "llm": {"model": "test-model", "base_url": "http://localhost"},
            "safety": {"max_iterations": 100, "repeated_call_limit": 3},
        }
        cfg_path = tmp_path / "harness.json"
        cfg_path.write_text(json.dumps(config_data))

        cfg = load_harness_config(str(cfg_path))
        assert cfg.llm.model == "test-model"
        assert cfg.llm.base_url == "http://localhost"
        assert cfg.safety.max_iterations == 100
        assert cfg.safety.repeated_call_limit == 3

    def test_load_raises_for_missing_explicit_path(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_harness_config(str(tmp_path / "nonexistent.json"))

    def test_load_returns_defaults_when_no_path(self) -> None:
        cwd_candidate = Path.cwd() / "harness.json"
        if cwd_candidate.exists():
            cfg = load_harness_config()
            assert isinstance(cfg, HarnessConfig)
        else:
            cfg = load_harness_config()
            assert isinstance(cfg, HarnessConfig)
            assert cfg.llm.model == "deepseek/deepseek-v4-flash"


class TestDiscoverPath:
    def test_explicit_path_returns_that_path(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "my_config.json"
        cfg_path.write_text("{}")
        result = _discover_path(str(cfg_path))
        assert result == cfg_path

    def test_cwd_overrides_xdg(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        (cwd / "harness.json").write_text("{}")

        monkeypatch.setattr(Path, "cwd", lambda: cwd)

        result = _discover_path()
        assert result == cwd / "harness.json"


class TestMergeApiKey:
    def test_openrouter_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert merge_api_key() == "sk-or-key"

    def test_openai_key_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-key")
        assert merge_api_key() == "sk-oai-key"

    def test_openrouter_preferred_over_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-key")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-key")
        assert merge_api_key() == "sk-or-key"

    def test_no_keys_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert merge_api_key() is None