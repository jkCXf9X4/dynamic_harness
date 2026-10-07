from __future__ import annotations

import pytest

from dynamic_harness.config import HarnessConfig, LLMSettings, ModelSpec, ProviderConfig
from dynamic_harness.llm.registry import (
    ProviderCredentialError,
    ProviderRegistry,
)


def _config() -> HarnessConfig:
    return HarnessConfig.model_validate(
        {
            "providers": {
                "openrouter": {
                    "env": ["OPENROUTER_API_KEY", "OPENAI_API_KEY"],
                    "base_url": "https://openrouter.ai/api/v1",
                    "provider_ignore": ["bad-slug"],
                    "models": {
                        "deepseek/deepseek-v4-flash": {"name": "DeepSeek V4 Flash"}
                    },
                },
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
                },
            }
        }
    )


class TestFromConfig:
    def test_resolves_config_model_by_default(self) -> None:
        registry = ProviderRegistry.from_config(_config())
        assert registry.active_provider_id == "openrouter"
        assert registry.model_info.model_id == "deepseek/deepseek-v4-flash"

    def test_model_ref_overrides(self) -> None:
        registry = ProviderRegistry.from_config(_config(), model_ref="openai/gpt-5.2")
        assert registry.active_provider_id == "openai"
        assert registry.model_info.model_id == "gpt-5.2"

    def test_provider_override_selects(self) -> None:
        registry = ProviderRegistry.from_config(_config(), provider="openai")
        assert registry.active_provider_id == "openai"
        assert registry.model_info.model_id == "gpt-5.2"

    def test_provider_override_falls_back_to_first_model_key(self) -> None:
        registry = ProviderRegistry.from_config(
            _config(), model_ref="openrouter/deepseek/deepseek-v4-flash", provider="openai"
        )
        assert registry.model_info.model_id == "gpt-5.2"

    def test_provider_override_errors_for_provider_with_no_models(self) -> None:
        """The no-models raise is deterministic, so it fires at registry
        construction (resolution time) — before select()."""

        cfg = _config()
        cfg.providers["openai"].models = {}
        with pytest.raises(ValueError, match="no models"):
            ProviderRegistry.from_config(
                cfg, model_ref="openrouter/deepseek/deepseek-v4-flash", provider="openai"
            )


class TestResolve:
    def test_first_slash_splits(self) -> None:
        registry = ProviderRegistry.from_config(_config())
        resolved = registry.resolve("openai/gpt-5.2")
        assert (resolved.provider_id, resolved.model_id) == ("openai", "gpt-5.2")

    def test_multi_slash_upstream_id(self) -> None:
        registry = ProviderRegistry.from_config(_config())
        resolved = registry.resolve("openrouter/deepseek/deepseek-v4-flash")
        assert (resolved.provider_id, resolved.model_id) == (
            "openrouter",
            "deepseek/deepseek-v4-flash",
        )

    def test_model_id_remaps_upstream_id(self) -> None:
        cfg = _config()
        cfg.providers["openai"].models["alias"] = ModelSpec(model_id="upstream/gpt-5.2")
        registry = ProviderRegistry.from_config(cfg)
        resolved = registry.resolve("openai/alias")
        assert resolved.upstream_id == "upstream/gpt-5.2"

    def test_model_absent_from_map_passes_through(self) -> None:
        """A model absent from the map passes through as-is (upstream id = the
        ref, no metadata) — a typo fails at the provider, like today."""

        registry = ProviderRegistry.from_config(_config())
        resolved = registry.resolve("openai/oops")
        assert (resolved.provider_id, resolved.model_id, resolved.upstream_id) == (
            "openai",
            "oops",
            "oops",
        )
        assert resolved.name is None
        assert resolved.cost is None

    def test_unknown_provider_errors_listing_keys(self) -> None:
        registry = ProviderRegistry.from_config(_config())
        with pytest.raises(ValueError, match="openrouter"):
            registry.resolve("deepseek/deepseek-v4-flash")

    def test_bare_ref_errors(self) -> None:
        registry = ProviderRegistry.from_config(_config())
        with pytest.raises(ValueError, match="<provider>/<model>"):
            registry.resolve("deepseek/deepseek-v4-flash")

    def test_pure_constructs_nothing(self) -> None:
        registry = ProviderRegistry.from_config(_config())
        registry.resolve("openai/gpt-5.2")
        assert registry._built == {}


class TestCredentials:
    def test_env_walk_first_set_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        registry = ProviderRegistry.from_config(_config())
        assert registry.api_key_for("openrouter") == "sk-or-key"

    def test_env_fallback_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The built-in OpenRouter entry walks OPENROUTER_API_KEY then
        OPENAI_API_KEY — the old merge_api_key fallback order."""

        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-key")
        registry = ProviderRegistry.from_config(_config())
        assert registry.api_key_for("openrouter") == "sk-oai-key"

    def test_unknown_provider_errors(self) -> None:
        registry = ProviderRegistry.from_config(_config())
        with pytest.raises(KeyError):
            registry.api_key_for("nonexistent")


class TestSelect:
    def test_builds_and_marks_active(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-key")
        registry = ProviderRegistry.from_config(_config())
        llm = registry.select()
        assert llm is registry._active
        assert llm is registry.build("openrouter")
        assert llm.default_model == "deepseek/deepseek-v4-flash"

    def test_missing_credential_raises_naming_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        registry = ProviderRegistry.from_config(_config())
        with pytest.raises(ProviderCredentialError, match="OPENROUTER_API_KEY"):
            registry.select()
        assert registry._active is None

    def test_api_key_override_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        registry = ProviderRegistry.from_config(_config(), api_key="sk-run-key")
        llm = registry.select()
        assert llm is not None
        assert llm.client.api_key == "sk-run-key"

    def test_base_url_override_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-key")
        registry = ProviderRegistry.from_config(
            _config(), base_url="https://gateway.example.com/v1"
        )
        llm = registry.select()
        assert llm is not None
        assert str(llm.client.base_url).rstrip("/") == "https://gateway.example.com/v1"


class TestBuild:
    def test_cached_per_provider_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-key")
        registry = ProviderRegistry.from_config(_config())
        assert registry.build("openrouter") is registry.build("openrouter")

    def test_errors_for_provider_with_no_models(self) -> None:
        cfg = _config()
        cfg.providers["openai"].models = {}
        registry = ProviderRegistry.from_config(cfg)
        with pytest.raises(ValueError, match="no models"):
            registry.build("openai")

    def test_unknown_provider_errors(self) -> None:
        registry = ProviderRegistry.from_config(_config())
        with pytest.raises(KeyError):
            registry.build("nonexistent")

    def test_catalog_metadata_flows_to_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-key")
        registry = ProviderRegistry.from_config(_config())
        llm = registry.build("openai")
        assert llm.default_model == "gpt-5.2"
        assert llm._provider_force is None
        assert llm._provider_allow_fallbacks is True


class TestCloseAll:
    @pytest.mark.asyncio
    async def test_releases_built_instances(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-key")
        registry = ProviderRegistry.from_config(_config())
        llm = registry.select()
        await registry.close_all()
        assert registry._built == {}
        assert registry._active is None
        await llm.aclose()  # idempotent — a closed instance keeps closing
