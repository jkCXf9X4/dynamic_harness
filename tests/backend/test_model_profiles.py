"""Model profiles: named capability/speed tiers an agent picks for a delegated child.

Covers the config surface (ModelProfile / HarnessConfig.profiles /
resolve_profile), the per-model provider registry (cache + provider_for),
the dynamic delegate tool schema, and the full delegate → child plumbing
(child runs on the profile's model, event carries the profile, bad profiles
are rejected before any agent is created).
"""

from __future__ import annotations

import json

import pytest

from dynamic_harness.config import (
    HarnessConfig,
    ModelProfile,
    ProviderConfig,
    SafetyConfig,
    SelfHealConfig,
    ModelSpec,
)
from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ActivityEventType, ReportPayload, Task
from dynamic_harness.llm.registry import ProviderCredentialError, ProviderRegistry


def _profiles_config() -> HarnessConfig:
    """Config with two models on one provider and two profiles."""

    return HarnessConfig.model_validate(
        {
            "model": "openrouter/deepseek/deepseek-v4-flash",
            "providers": {
                "openrouter": {
                    "env": ["FAKE_PROFILE_KEY"],
                    "base_url": "https://profile-test.invalid/v1",
                    "models": {
                        "deepseek/deepseek-v4-flash": {"name": "Fast tier"},
                        "openai/gpt-5.2": {"name": "Strong tier"},
                    },
                }
            },
            "profiles": {
                "fast": "openrouter/deepseek/deepseek-v4-flash",
                "strong": {
                    "ref": "openrouter/openai/gpt-5.2",
                    "description": "hard reasoning",
                },
            },
        }
    )


class TestModelProfileConfig:
    def test_bare_string_shorthand(self) -> None:
        profile = ModelProfile.model_validate("openrouter/some/model")
        assert profile.ref == "openrouter/some/model"
        assert profile.description == ""

    def test_dict_form_with_description(self) -> None:
        profile = ModelProfile.model_validate(
            {"ref": "openrouter/some/model", "description": "the fast one"}
        )
        assert profile.ref == "openrouter/some/model"
        assert profile.description == "the fast one"

    def test_harness_config_parses_profiles(self) -> None:
        cfg = _profiles_config()
        assert set(cfg.profiles) == {"fast", "strong"}
        assert cfg.profiles["fast"].ref == "openrouter/deepseek/deepseek-v4-flash"
        assert cfg.profiles["strong"].ref == "openrouter/openai/gpt-5.2"
        assert cfg.profiles["strong"].description == "hard reasoning"

    def test_profiles_empty_by_default(self) -> None:
        assert HarnessConfig().profiles == {}

    def test_resolve_profile(self) -> None:
        cfg = _profiles_config()
        resolved = cfg.resolve_profile("strong")
        assert resolved.provider_id == "openrouter"
        assert resolved.model_id == "openai/gpt-5.2"
        assert resolved.name == "Strong tier"

    def test_resolve_profile_unknown_name(self) -> None:
        cfg = _profiles_config()
        with pytest.raises(ValueError, match="unknown model profile 'nope'"):
            cfg.resolve_profile("nope")
        with pytest.raises(ValueError, match="configured profiles: fast, strong"):
            cfg.resolve_profile("nope")

    def test_resolve_profile_bad_ref(self) -> None:
        cfg = _profiles_config()
        cfg.profiles["bad"] = ModelProfile(ref="nosuchprovider/model")
        with pytest.raises(ValueError, match="model ref"):
            cfg.resolve_profile("bad")


class TestRegistryPerModel:
    def test_distinct_instances_per_model(self, monkeypatch) -> None:
        monkeypatch.setenv("FAKE_PROFILE_KEY", "test-key")
        registry = ProviderRegistry.from_config(_profiles_config())
        fast = registry.provider_for("openrouter/deepseek/deepseek-v4-flash")
        strong = registry.provider_for("openrouter/openai/gpt-5.2")
        assert fast is not strong
        assert fast.default_model == "deepseek/deepseek-v4-flash"
        assert strong.default_model == "openai/gpt-5.2"

    def test_same_model_cached(self, monkeypatch) -> None:
        monkeypatch.setenv("FAKE_PROFILE_KEY", "test-key")
        registry = ProviderRegistry.from_config(_profiles_config())
        first = registry.provider_for("openrouter/openai/gpt-5.2")
        second = registry.provider_for("openrouter/openai/gpt-5.2")
        assert first is second

    def test_active_selection_untouched(self, monkeypatch) -> None:
        monkeypatch.setenv("FAKE_PROFILE_KEY", "test-key")
        registry = ProviderRegistry.from_config(_profiles_config())
        active_before = registry.model_info.model_id
        registry.provider_for("openrouter/openai/gpt-5.2")
        assert registry.model_info.model_id == active_before

    def test_missing_credential_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("FAKE_PROFILE_KEY", raising=False)
        registry = ProviderRegistry.from_config(_profiles_config())
        with pytest.raises(ProviderCredentialError):
            registry.provider_for("openrouter/openai/gpt-5.2")


def _make_runtime(tmp, cfg: HarnessConfig, *, with_registry: bool = True, monkeypatch=None):
    """Runtime wired for profile delegation (fake credential when a registry is attached)."""

    if with_registry and monkeypatch is not None:
        monkeypatch.setenv("FAKE_PROFILE_KEY", "test-key")
    return Runtime(
        artifact_root=tmp / "artifacts",
        repo_root=tmp / "repo",
        generated_root=tmp,
        config=cfg,
        provider_registry=(
            ProviderRegistry.from_config(cfg) if with_registry else None
        ),
    )


class _OKChild(Agent):
    """A child that reports immediately without touching the LLM, echoing
    the provider model it was constructed with."""

    async def run(self) -> None:
        model = getattr(self.llm, "default_model", None)
        info = self.model_info.model_id if self.model_info else None
        self.report(ReportPayload(
            task_id=self.task.id,
            summary=f"ok llm={model} info={info}",
        ))


class TestDelegateSchema:
    def test_param_absent_without_profiles(self, tmp_path) -> None:
        cfg = HarnessConfig(
            safety=SafetyConfig(),
            self_heal=SelfHealConfig(mode=False, max_resumes=0, max_fresh_retries=0),
        )
        runtime = Runtime(
            artifact_root=tmp_path / "a",
            repo_root=tmp_path / "r",
            generated_root=tmp_path,
            config=cfg,
        )
        delegate = next(
            s for s in runtime.tool_registry.openai_schemas()
            if s["function"]["name"] == "delegate"
        )
        assert "model_profile" not in delegate["function"]["parameters"]["properties"]

    def test_param_present_with_profiles(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("FAKE_PROFILE_KEY", "test-key")
        runtime = _make_runtime(tmp_path, _profiles_config(), monkeypatch=monkeypatch)
        delegate = next(
            s for s in runtime.tool_registry.openai_schemas()
            if s["function"]["name"] == "delegate"
        )
        prop = delegate["function"]["parameters"]["properties"]["model_profile"]
        assert prop["enum"] == ["fast", "strong"]
        assert "'fast'" in prop["description"]
        assert "'strong' — hard reasoning" in prop["description"]


class TestDelegateProfilePlumbing:
    def test_child_gets_profile_provider(self, tmp_path, monkeypatch) -> None:
        runtime = _make_runtime(tmp_path, _profiles_config(), monkeypatch=monkeypatch)
        runtime.register_agent_class("_OKChild", _OKChild)
        runtime.set_llm(None)

        child = runtime.delegate(
            Task(description="do the hard thing", model_profile="strong"),
            agent_type="_OKChild",
        )
        assert child.model_info.model_id == "openai/gpt-5.2"
        assert child.llm.default_model == "openai/gpt-5.2"

        plain = runtime.delegate(Task(description="do the easy thing"))
        assert plain.model_info.model_id == "deepseek/deepseek-v4-flash"
        assert plain.llm is None  # inherits the (unset) runtime provider

    def test_unknown_profile_raises_before_agent(self, tmp_path, monkeypatch) -> None:
        runtime = _make_runtime(tmp_path, _profiles_config(), monkeypatch=monkeypatch)
        with pytest.raises(ValueError, match="unknown model profile"):
            runtime.delegate(Task(description="x", model_profile="nope"))
        assert not runtime._agents

    def test_runtime_without_registry_raises(self, tmp_path, monkeypatch) -> None:
        runtime = _make_runtime(
            tmp_path, _profiles_config(), with_registry=False, monkeypatch=monkeypatch
        )
        with pytest.raises(RuntimeError, match="no provider registry"):
            runtime.delegate(Task(description="x", model_profile="strong"))
        assert not runtime._agents

    async def test_resume_preserves_model_profile(self, tmp_path, monkeypatch) -> None:
        """A disk-rebuilt child comes back on the tier it was delegated with."""

        runtime = _make_runtime(tmp_path, _profiles_config(), monkeypatch=monkeypatch)
        runtime.register_agent_class("_OKChild", _OKChild)
        child = runtime.delegate(
            Task(description="checkpoint me", model_profile="strong"),
            agent_type="_OKChild",
        )
        runtime.checkpoint_store.save(child)
        child._context_freed = True  # simulate GC → force the disk-rebuild path

        resumed = await runtime.resume(child.id)
        assert resumed.task.model_profile == "strong"
        assert resumed.llm.default_model == "openai/gpt-5.2"

    def test_fresh_restart_preserves_model_profile(self, tmp_path, monkeypatch) -> None:
        """A self-heal fresh worker inherits the failed agent's tier."""

        runtime = _make_runtime(tmp_path, _profiles_config(), monkeypatch=monkeypatch)
        child = runtime.delegate(Task(description="flaky work", model_profile="strong"))

        fresh = runtime._fresh_restart(child, note="try again")
        assert fresh.task.model_profile == "strong"
        assert fresh.llm.default_model == "openai/gpt-5.2"

    async def test_delegate_tool_end_to_end(self, tmp_path, monkeypatch) -> None:
        """Parent delegates with model_profile → child runs on the strong tier and
        reports; the DELEGATION_START event carries the profile."""

        runtime = _make_runtime(tmp_path, _profiles_config(), monkeypatch=monkeypatch)
        runtime.register_agent_class("_OKChild", _OKChild)
        parent = Agent("rootparent0001", Task(description="root work"), runtime)

        seen = []
        runtime.event_bus.on_activity(lambda event: seen.append(event))

        result = json.loads(await parent.run_delegate_tool(
            "verify the architecture", agent_type="_OKChild", model_profile="strong",
        ))
        assert result["status"] == "completed"
        assert "ok llm=openai/gpt-5.2 info=openai/gpt-5.2" in result["summary"]

        starts = [
            e for e in seen
            if e.event_type == ActivityEventType.DELEGATION_START and e.agent_id == parent.id
        ]
        assert len(starts) == 1
        assert starts[0].data["model_profile"] == "strong"
        assert starts[0].data["child_id"] == result["child_id"]

    async def test_delegate_tool_unknown_profile_error(self, tmp_path, monkeypatch) -> None:
        runtime = _make_runtime(tmp_path, _profiles_config(), monkeypatch=monkeypatch)
        parent = Agent("rootparent0002", Task(description="root work"), runtime)

        result = json.loads(await parent.run_delegate_tool(
            "anything", model_profile="nope",
        ))
        assert "unknown model_profile 'nope'" in result["error"]
        assert "fast, strong" in result["error"]
        assert not runtime._agents  # no agent was created

    async def test_delegate_tool_omits_profile_event_field(self, tmp_path, monkeypatch) -> None:
        """A profile-less delegation leaves the event's data untouched (no key)."""

        runtime = _make_runtime(tmp_path, _profiles_config(), monkeypatch=monkeypatch)
        runtime.register_agent_class("_OKChild", _OKChild)
        parent = Agent("rootparent0003", Task(description="root work"), runtime)
        seen = []
        runtime.event_bus.on_activity(lambda event: seen.append(event))

        result = json.loads(await parent.run_delegate_tool(
            "mechanical extraction", agent_type="_OKChild",
        ))
        assert result["status"] == "completed"
        starts = [
            e for e in seen
            if e.event_type == ActivityEventType.DELEGATION_START and e.agent_id == parent.id
        ]
        assert len(starts) == 1
        assert "model_profile" not in starts[0].data
