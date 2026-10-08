from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dynamic_harness.config import (
    HarnessConfig,
    LLMSettings,
    ModelSpec,
    ProviderConfig,
    ResolvedModel,
    SafetyConfig,
    _deep_merge,
    _discover_config_files,
    _discover_path,
    _xdg_config_dir,
    load_harness_config,
    resolve_model_ref,
)


class TestHarnessConfig:
    def test_defaults(self) -> None:
        cfg = HarnessConfig()
        assert cfg.root_model == "openrouter/deepseek/deepseek-v4-flash"
        assert cfg.safety.max_iterations == 400
        assert cfg.safety.repeated_call_limit == 5

    def test_default_llm_settings(self) -> None:
        cfg = HarnessConfig()
        assert cfg.llm.verify_ssl is True
        assert cfg.llm.call_timeout_seconds == 500.0
        assert cfg.llm.retry_max_attempts == 4
        assert cfg.llm.rate_limit_max_attempts == 6
        assert cfg.llm.retry_base_delay_seconds == 1.0
        assert cfg.llm.retry_max_delay_seconds == 30.0
        assert cfg.llm.retry_jitter_seconds == 0.5
        assert cfg.llm.rate_limit_backoff_multiplier == 3.0
        assert cfg.llm.fallback_on_rate_limit is True

    def test_default_provider_is_openrouter(self) -> None:
        cfg = HarnessConfig()
        assert sorted(cfg.providers) == ["openrouter"]
        pc = cfg.providers["openrouter"]
        assert pc.env == ["OPENROUTER_API_KEY", "OPENAI_API_KEY"]
        assert pc.base_url == "https://openrouter.ai/api/v1"
        assert pc.provider_ignore == []
        assert pc.provider_allow_fallbacks is True
        assert pc.provider_force is None
        assert "deepseek/deepseek-v4-flash" in pc.models
        assert pc.models["deepseek/deepseek-v4-flash"].name == "DeepSeek V4 Flash"

    def test_default_llm_provider_ignore_empty(self) -> None:
        for pc in HarnessConfig().providers.values():
            assert pc.provider_ignore == []

    def test_safety_config_defaults(self) -> None:
        sc = SafetyConfig()
        assert sc.max_iterations == 400
        assert sc.repeated_call_limit == 5
        assert sc.timeout_seconds == 7200.0
        assert sc.disable_root_timeout is True
        assert sc.max_agents == 300
        assert sc.max_same_target_delegations == 0

    def test_safety_timeout_seconds(self) -> None:
        assert SafetyConfig(timeout_seconds=120.0).timeout_seconds == 120.0

    def test_llm_settings(self) -> None:
        llm = LLMSettings(verify_ssl=False, call_timeout_seconds=45.0)
        assert llm.verify_ssl is False
        assert llm.call_timeout_seconds == 45.0

    def test_custom_model_and_provider(self) -> None:
        cfg = HarnessConfig.model_validate(
            {
                "root_model": "openai/gpt-5.2",
                "providers": {
                    "openai": {
                        "env": ["OPENAI_API_KEY"],
                        "base_url": "https://api.openai.com/v1",
                        "models": {
                            "gpt-5.2": {
                                "model_id": "gpt-5.2",
                                "name": "GPT-5.2",
                                "cost": {"input": 1.25, "output": 10.0},
                            }
                        },
                    }
                },
            }
        )
        assert cfg.root_model == "openai/gpt-5.2"
        assert cfg.providers["openai"].base_url == "https://api.openai.com/v1"
        assert cfg.safety.max_iterations == 400

    def test_legacy_model_key_alias(self) -> None:
        """The pre-rename top-level ``model`` key still loads, as ``root_model``."""
        cfg = HarnessConfig.model_validate({"model": "openai/gpt-5.2"})
        assert cfg.root_model == "openai/gpt-5.2"

    def test_explicit_root_model_wins_over_legacy(self) -> None:
        cfg = HarnessConfig.model_validate(
            {"model": "openai/legacy", "root_model": "openai/explicit"}
        )
        assert cfg.root_model == "openai/explicit"

    def test_stale_flat_llm_keys_error(self) -> None:
        """The flat provider keys were removed — stale configs fail loudly."""
        with pytest.raises(Exception, match="model"):
            HarnessConfig.model_validate({"llm": {"model": "x"}})
        with pytest.raises(Exception, match="base_url"):
            HarnessConfig.model_validate(
                {"llm": {"verify_ssl": True, "base_url": "https://x"}}
            )
        with pytest.raises(Exception, match="price_input_per_mtok"):
            HarnessConfig.model_validate({"llm": {"price_input_per_mtok": 1.0}})

    def test_partial_config_merge(self) -> None:
        cfg = HarnessConfig.model_validate({"llm": {"call_timeout_seconds": 45.5}})
        assert cfg.llm.call_timeout_seconds == 45.5
        assert cfg.llm.verify_ssl is True
        assert cfg.safety.max_iterations == 400


class TestResolveModelRef:
    def _providers(self) -> dict[str, ProviderConfig]:
        return {
            "openrouter": ProviderConfig(
                env=["OPENROUTER_API_KEY"],
                base_url="https://openrouter.ai/api/v1",
                models={
                    "deepseek/deepseek-v4-flash": ModelSpec(
                        name="DeepSeek V4 Flash",
                        cost=None,
                    )
                },
            ),
            "openai": ProviderConfig(
                env=["OPENAI_API_KEY"],
                base_url="https://api.openai.com/v1",
                models={
                    "gpt-5.2": ModelSpec(
                        model_id="gpt-5.2",
                        name="GPT-5.2",
                        cost=None,
                    )
                },
            ),
        }

    def test_default_ref_resolves_multi_slash(self) -> None:
        """The first slash splits provider id from model id, so OpenRouter's
        multi-slash upstream ids resolve: provider 'openrouter', model
        'deepseek/deepseek-v4-flash'."""

        resolved = resolve_model_ref(self._providers(), "openrouter/deepseek/deepseek-v4-flash")
        assert (resolved.provider_id, resolved.model_id) == (
            "openrouter",
            "deepseek/deepseek-v4-flash",
        )

    def test_model_id_remaps_upstream_id(self) -> None:
        providers = self._providers()
        providers["openai"].models["alias"] = ModelSpec(model_id="upstream/gpt-5.2")
        resolved = resolve_model_ref(providers, "openrouter/deepseek/deepseek-v4-flash")
        assert resolved.upstream_id == "deepseek/deepseek-v4-flash"
        assert resolve_model_ref(providers, "openai/alias").upstream_id == "upstream/gpt-5.2"

    def test_explicit_model_ref_overrides_default(self) -> None:
        resolved = resolve_model_ref(self._providers(), "openai/gpt-5.2")
        assert (resolved.provider_id, resolved.model_id) == ("openai", "gpt-5.2")

    def test_provider_selection_uses_config_model_when_it_names_provider(self) -> None:
        resolved = resolve_model_ref(
            self._providers(),
            "openrouter/deepseek/deepseek-v4-flash",
            provider="openai",
        )
        assert (resolved.provider_id, resolved.model_id) == ("openai", "gpt-5.2")

    def test_provider_selection_falls_back_to_first_model_key(self) -> None:
        resolved = resolve_model_ref(
            self._providers(),
            "openrouter/deepseek/deepseek-v4-flash",
            provider="openai",
        )
        assert (resolved.provider_id, resolved.model_id) == ("openai", "gpt-5.2")

    def test_provider_selection_errors_for_provider_with_no_models(self) -> None:
        providers = self._providers()
        providers["openai"].models = {}
        with pytest.raises(ValueError, match="no models"):
            resolve_model_ref(providers, "openrouter/deepseek/deepseek-v4-flash", provider="openai")

    def test_unknown_provider_errors_listing_keys(self) -> None:
        with pytest.raises(ValueError, match="openrouter"):
            resolve_model_ref(self._providers(), "deepseek/deepseek-v4-flash")

    def test_bare_ref_errors(self) -> None:
        with pytest.raises(ValueError, match="<provider>/<model>"):
            resolve_model_ref(self._providers(), "deepseek/deepseek-v4-flash")

    def test_model_absent_from_map_passes_through(self) -> None:
        """A model absent from the map passes through as-is (upstream id =
        the ref, no metadata) — a typo fails at the provider, like today."""
        resolved = resolve_model_ref(self._providers(), "openai/oops")
        assert isinstance(resolved, ResolvedModel)
        assert (resolved.provider_id, resolved.model_id, resolved.upstream_id) == (
            "openai",
            "oops",
            "oops",
        )
        assert resolved.name is None
        assert resolved.cost is None


class TestLoadHarnessConfig:
    def test_load_from_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Isolate the XDG base so the machine's global config can never
        # leak into an explicit-path load.
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        config_data = {
            "root_model": "openrouter/test-model",
            "providers": {"openrouter": {"base_url": "http://localhost"}},
            "safety": {"max_iterations": 100, "repeated_call_limit": 3, "timeout_seconds": 90},
        }
        cfg_path = tmp_path / "dynamic_harness.json"
        cfg_path.write_text(json.dumps(config_data))

        cfg = load_harness_config(str(cfg_path))
        assert cfg.root_model == "openrouter/test-model"
        assert cfg.providers["openrouter"].base_url == "http://localhost"
        assert cfg.safety.max_iterations == 100
        assert cfg.safety.repeated_call_limit == 3
        assert cfg.safety.timeout_seconds == 90

    def test_load_raises_for_missing_explicit_path(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_harness_config(str(tmp_path / "nonexistent.json"))

    def test_load_returns_defaults_when_no_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Isolate from the machine's XDG config — the test asserts the
        built-in defaults, not machine state."""

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        cfg = load_harness_config()
        assert cfg.root_model == "openrouter/deepseek/deepseek-v4-flash"


class TestDiscoverPath:
    def test_explicit_path_returns_that_path(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "my_config.json"
        cfg_path.write_text("{}")
        result = _discover_path(str(cfg_path))
        assert result == cfg_path

    def test_cwd_overrides_xdg(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        (cwd / "dynamic_harness.json").write_text("{}")

        monkeypatch.setattr(Path, "cwd", lambda: cwd)

        result = _discover_path()
        assert result == cwd / "dynamic_harness.json"


class TestDeepMerge:
    def test_overlay_replaces_scalar(self) -> None:
        merged = _deep_merge({"a": 1, "b": 2}, {"b": 3})
        assert merged == {"a": 1, "b": 3}

    def test_nested_dicts_merge_field_by_field(self) -> None:
        merged = _deep_merge(
            {"llm": {"call_timeout_seconds": 500.0, "verify_ssl": True}},
            {"llm": {"verify_ssl": False}},
        )
        assert merged == {"llm": {"call_timeout_seconds": 500.0, "verify_ssl": False}}

    def test_overlay_replaces_base_list(self) -> None:
        merged = _deep_merge(
            {"providers": {"openrouter": {"provider_ignore": ["a", "b"]}}},
            {"providers": {"openrouter": {"provider_ignore": ["c"]}}},
        )
        assert merged["providers"]["openrouter"]["provider_ignore"] == ["c"]

    def test_overlay_adds_new_key(self) -> None:
        merged = _deep_merge(
            {"llm": {"verify_ssl": True}},
            {"agent": {"stream_children": True}},
        )
        assert merged == {"llm": {"verify_ssl": True}, "agent": {"stream_children": True}}

    def test_does_not_mutate_inputs(self) -> None:
        base = {"llm": {"verify_ssl": True}}
        overlay = {"llm": {"verify_ssl": False}}
        _deep_merge(base, overlay)
        assert base == {"llm": {"verify_ssl": True}}
        assert overlay == {"llm": {"verify_ssl": False}}


class TestLayeredLoading:
    def test_common_base_is_applied_when_no_local(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "empty"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        xdg_dir = tmp_path / "dynamic_harness"
        xdg_dir.mkdir()
        (xdg_dir / "dynamic_harness.json").write_text(
            json.dumps(
                {
                    "root_model": "openrouter/base-model",
                    "providers": {"openrouter": {"base_url": "http://base"}},
                    "safety": {"max_iterations": 300},
                }
            )
        )

        cfg = load_harness_config()
        assert cfg.root_model == "openrouter/base-model"
        assert cfg.providers["openrouter"].base_url == "http://base"
        assert cfg.safety.max_iterations == 300

    def test_local_overlay_overrides_common_base(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        xdg_dir = tmp_path / "dynamic_harness"
        xdg_dir.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        (xdg_dir / "dynamic_harness.json").write_text(
            json.dumps(
                {
                    "root_model": "openrouter/base-model",
                    "providers": {
                        "openrouter": {
                            "base_url": "http://base",
                            "provider_ignore": ["a"],
                        }
                    },
                    "llm": {"verify_ssl": False},
                    "safety": {"max_iterations": 300, "repeated_call_limit": 5},
                }
            )
        )
        (cwd / "dynamic_harness.json").write_text(
            json.dumps(
                {
                    "root_model": "openrouter/local-model",
                    "safety": {"repeated_call_limit": 9},
                }
            )
        )

        cfg = load_harness_config()
        assert cfg.root_model == "openrouter/local-model"
        assert cfg.providers["openrouter"].base_url == "http://base"
        assert cfg.providers["openrouter"].provider_ignore == ["a"]
        assert cfg.llm.verify_ssl is False
        assert cfg.safety.max_iterations == 300
        assert cfg.safety.repeated_call_limit == 9

    def test_explicit_path_overlays_common_base(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        xdg_dir = tmp_path / "dynamic_harness"
        xdg_dir.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        (xdg_dir / "dynamic_harness.json").write_text(
            json.dumps({"providers": {"openrouter": {"base_url": "http://base"}}})
        )
        explicit = tmp_path / "custom.json"
        explicit.write_text(json.dumps({"root_model": "openrouter/custom-model"}))

        cfg = load_harness_config(str(explicit))
        assert cfg.root_model == "openrouter/custom-model"
        assert cfg.providers["openrouter"].base_url == "http://base"

    def test_invalid_json_in_base_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        xdg_dir = tmp_path / "dynamic_harness"
        xdg_dir.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        (xdg_dir / "dynamic_harness.json").write_text("{ not json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_harness_config()

    def test_discover_config_files_orders_base_before_local(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cwd = tmp_path / "project"
        cwd.mkdir()
        monkeypatch.setattr(Path, "cwd", lambda: cwd)
        xdg_dir = tmp_path / "dynamic_harness"
        xdg_dir.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        (xdg_dir / "dynamic_harness.json").write_text("{}")
        (cwd / "dynamic_harness.json").write_text("{}")

        files = _discover_config_files()
        assert files == [xdg_dir / "dynamic_harness.json", cwd / "dynamic_harness.json"]


class TestXdgConfigDir:
    def test_honors_xdg_config_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert _xdg_config_dir() == tmp_path / "dynamic_harness"

    def test_defaults_to_home_config_when_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert _xdg_config_dir() == tmp_path / ".config" / "dynamic_harness"

    def test_empty_env_var_falls_back_to_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert _xdg_config_dir() == tmp_path / ".config" / "dynamic_harness"
