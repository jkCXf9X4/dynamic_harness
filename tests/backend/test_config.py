from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dynamic_harness.config import (
    HarnessConfig,
    LLMProviderConfig,
    SafetyConfig,
    _deep_merge,
    _discover_config_files,
    _discover_path,
    load_harness_config,
    merge_api_key,
)


class TestHarnessConfig:
    def test_defaults(self) -> None:
        cfg = HarnessConfig()
        assert cfg.llm.model == "deepseek/deepseek-v4-flash"
        assert cfg.llm.base_url == "https://openrouter.ai/api/v1"
        assert cfg.safety.max_iterations == 400
        assert cfg.safety.repeated_call_limit == 5

    def test_default_llm_provider_ignore_empty(self) -> None:
        cfg = HarnessConfig()
        assert cfg.llm.provider_ignore == []

    def test_default_llm_allow_fallbacks(self) -> None:
        cfg = HarnessConfig()
        assert cfg.llm.provider_allow_fallbacks is True

    def test_safety_config_defaults(self) -> None:
        sc = SafetyConfig()
        assert sc.max_iterations == 400
        assert sc.repeated_call_limit == 5
        assert sc.timeout_seconds == 7200.0
        assert sc.disable_root_timeout is True
        assert sc.max_agents == 300
        assert sc.max_same_target_delegations == 0

    def test_safety_timeout_seconds(self) -> None:
        sc = SafetyConfig(timeout_seconds=120.0)
        assert sc.timeout_seconds == 120.0

    def test_llm_provider_config_defaults(self) -> None:
        lpc = LLMProviderConfig()
        assert lpc.model == "deepseek/deepseek-v4-flash"
        assert lpc.base_url == "https://openrouter.ai/api/v1"
        assert lpc.provider_ignore == []
        assert lpc.provider_allow_fallbacks is True
        assert lpc.provider_force is None
        assert lpc.call_timeout_seconds == 500.0

    def test_call_timeout_seconds(self) -> None:
        lpc = LLMProviderConfig(call_timeout_seconds=45.0)
        assert lpc.call_timeout_seconds == 45.0

    def test_partial_config_merge(self) -> None:
        cfg = HarnessConfig.model_validate({"llm": {"model": "custom-model"}})
        assert cfg.llm.model == "custom-model"
        assert cfg.llm.base_url == "https://openrouter.ai/api/v1"
        assert cfg.safety.max_iterations == 400


class TestLoadHarnessConfig:
    def test_load_from_file(self, tmp_path: Path) -> None:
        config_data = {
            "llm": {"model": "test-model", "base_url": "http://localhost"},
            "safety": {"max_iterations": 100, "repeated_call_limit": 3, "timeout_seconds": 90},
        }
        cfg_path = tmp_path / "harness.json"
        cfg_path.write_text(json.dumps(config_data))

        cfg = load_harness_config(str(cfg_path))
        assert cfg.llm.model == "test-model"
        assert cfg.llm.base_url == "http://localhost"
        assert cfg.safety.max_iterations == 100
        assert cfg.safety.repeated_call_limit == 3
        assert cfg.safety.timeout_seconds == 90

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


class TestDeepMerge:
    def test_overlay_replaces_scalar(self) -> None:
        merged = _deep_merge({"a": 1, "b": 2}, {"b": 3})
        assert merged == {"a": 1, "b": 3}

    def test_nested_dicts_merge_field_by_field(self) -> None:
        merged = _deep_merge(
            {"llm": {"model": "base", "base_url": "http://base"}},
            {"llm": {"model": "local"}},
        )
        assert merged == {"llm": {"model": "local", "base_url": "http://base"}}

    def test_overlay_list_replaces_base_list(self) -> None:
        merged = _deep_merge({"llm": {"provider_ignore": ["a", "b"]}}, {"llm": {"provider_ignore": ["c"]}})
        assert merged["llm"]["provider_ignore"] == ["c"]

    def test_overlay_adds_new_key(self) -> None:
        merged = _deep_merge({"llm": {"model": "base"}}, {"agent": {"stream_children": True}})
        assert merged == {"llm": {"model": "base"}, "agent": {"stream_children": True}}

    def test_does_not_mutate_inputs(self) -> None:
        base = {"llm": {"model": "base"}}
        overlay = {"llm": {"model": "local"}}
        _deep_merge(base, overlay)
        assert base == {"llm": {"model": "base"}}
        assert overlay == {"llm": {"model": "local"}}


class TestLayeredLoading:
    def test_common_base_is_applied_when_no_local(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "empty"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        monkeypatch.setattr(
            "dynamic_harness.config.XDG_CONFIG_DIR",
            tmp_path / "xdg",
        )
        xdg_dir = tmp_path / "xdg"
        xdg_dir.mkdir()
        (xdg_dir / "harness.json").write_text(
            json.dumps({"llm": {"model": "base-model"}, "safety": {"max_iterations": 300}})
        )

        cfg = load_harness_config()
        assert cfg.llm.model == "base-model"
        assert cfg.safety.max_iterations == 300

    def test_local_overlay_overrides_common_base(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        xdg_dir = tmp_path / "xdg"
        xdg_dir.mkdir()
        monkeypatch.setattr("dynamic_harness.config.XDG_CONFIG_DIR", xdg_dir)
        (xdg_dir / "harness.json").write_text(
            json.dumps(
                {
                    "llm": {"model": "base-model", "base_url": "http://base", "verify_ssl": False},
                    "safety": {"max_iterations": 300, "repeated_call_limit": 5},
                }
            )
        )
        (cwd / "harness.json").write_text(
            json.dumps({"llm": {"model": "local-model"}, "safety": {"repeated_call_limit": 9}})
        )

        cfg = load_harness_config()
        assert cfg.llm.model == "local-model"
        assert cfg.llm.base_url == "http://base"
        assert cfg.llm.verify_ssl is False
        assert cfg.safety.max_iterations == 300
        assert cfg.safety.repeated_call_limit == 9

    def test_explicit_path_overlays_common_base(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        xdg_dir = tmp_path / "xdg"
        xdg_dir.mkdir()
        monkeypatch.setattr("dynamic_harness.config.XDG_CONFIG_DIR", xdg_dir)
        (xdg_dir / "harness.json").write_text(json.dumps({"llm": {"model": "base-model", "base_url": "http://base"}}))
        explicit = tmp_path / "custom.json"
        explicit.write_text(json.dumps({"llm": {"model": "custom-model"}}))

        cfg = load_harness_config(str(explicit))
        assert cfg.llm.model == "custom-model"
        assert cfg.llm.base_url == "http://base"

    def test_invalid_json_in_base_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        xdg_dir = tmp_path / "xdg"
        xdg_dir.mkdir()
        monkeypatch.setattr("dynamic_harness.config.XDG_CONFIG_DIR", xdg_dir)
        (xdg_dir / "harness.json").write_text("{ not json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_harness_config()

    def test_discover_config_files_orders_base_before_local(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        xdg_dir = tmp_path / "xdg"
        xdg_dir.mkdir()
        monkeypatch.setattr("dynamic_harness.config.XDG_CONFIG_DIR", xdg_dir)
        (xdg_dir / "harness.json").write_text("{}")
        (cwd / "harness.json").write_text("{}")

        files = _discover_config_files()
        assert files == [xdg_dir / "harness.json", cwd / "harness.json"]


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