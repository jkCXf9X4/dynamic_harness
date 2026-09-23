"""Skills layer: the skill_load tool and the proactive SkillInjectionPolicy."""

from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_harness.config import HarnessConfig
from dynamic_harness.core.policies.interface import Observation
from dynamic_harness.core.policies.skill_inject import SkillInjectionPolicy
from dynamic_harness.core.references import Skill
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task


def _runtime_with_refs(tmp_path: Path, refs: dict[str, str]) -> Runtime:
    d = tmp_path / "refs"
    d.mkdir()
    for filename, body in refs.items():
        (d / filename).write_text(body)
    cfg = HarnessConfig()
    cfg.agent.references_dir = str(d)
    return Runtime(
        artifact_root=tmp_path / "a",
        repo_root=tmp_path / "r",
        generated_root=tmp_path,
        config=cfg,
    )


_SKILL_BODY = (
    "---\nname: tool-motivations\ndescription: Choose between tools.\n---\n\n"
    "# Tool Motivations\n\n## Discovery tools\n\n- **glob** — find files.\n"
)


# -- skill_load tool -------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_load_returns_body(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="T"))
    result = await runtime.tool_registry.execute("skill_load", "tc1", agent=agent, skill="tool-motivations")
    assert "Error" not in result.content
    assert "Discovery tools" in result.content
    # Frontmatter is stripped from the body.
    assert "name: tool-motivations" not in result.content


@pytest.mark.asyncio
async def test_skill_load_unknown_name(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="T"))
    result = await runtime.tool_registry.execute("skill_load", "tc1", agent=agent, skill="nope")
    assert "Error: unknown skill 'nope'" in result.content
    assert "tool-motivations" in result.content  # lists available skills


@pytest.mark.asyncio
async def test_skill_load_no_library(runtime: Runtime, tmp_path: Path) -> None:
    cfg = HarnessConfig()
    cfg.agent.references_dir = str(tmp_path / "does_not_exist")
    rt = Runtime(
        artifact_root=tmp_path / "a",
        repo_root=tmp_path / "r",
        generated_root=tmp_path,
        config=cfg,
    )
    agent = rt.delegate(Task(description="T"))
    result = await rt.tool_registry.execute("skill_load", "tc1", agent=agent, skill="tool-motivations")
    assert "Error: unknown skill 'tool-motivations'" in result.content
    assert "Available skills: (none)" in result.content


@pytest.mark.asyncio
async def test_skill_load_role_scoped_refusal(tmp_path: Path) -> None:
    rt = _runtime_with_refs(tmp_path, {
        "mission_command.md": (
            "---\nname: mission-command\ndescription: Brief children.\n"
            "roles:\n  - orchestrator\n---\n\n# Mission Command\n\nbrief body\n"
        ),
    })
    worker = rt.delegate(Task(description="W"))
    res = await rt.tool_registry.execute("skill_load", "tc1", agent=worker, skill="mission-command")
    assert "status: refused" in res.content
    assert "scoped to role" in res.content

    orchestrator = rt.delegate(Task(description="O", role="orchestrator"))
    res = await rt.tool_registry.execute("skill_load", "tc2", agent=orchestrator, skill="mission-command")
    assert "status: refused" not in res.content
    assert "brief body" in res.content


@pytest.mark.asyncio
async def test_skill_load_is_cacheable(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="T"))
    result = await runtime.tool_registry.execute("skill_load", "tc1", agent=agent, skill="tool-motivations")
    assert result.result_id is not None  # read-only → snapshotted behind a handle


# -- SkillInjectionPolicy ---------------------------------------------------


def _obs(**kw: object) -> Observation:
    defaults: dict[str, object] = dict(
        iteration=1, max_iterations=100, has_delegated=False,
    )
    defaults.update(kw)
    return Observation(**defaults)  # type: ignore[arg-type]


def test_policy_fires_once_for_matching_task() -> None:
    skills = [Skill(name="product-breakdown", description="decision records, IMP candidates")]
    pol = SkillInjectionPolicy(skills, role=None)
    inj = pol.evaluate(_obs(task_description="Update the decision log for IMP-3"))
    assert inj is not None
    assert "product-breakdown" in inj.message
    assert inj.warning_type == "skill_hint"
    assert inj.data == {"skill": "product-breakdown"}
    # Fires exactly once per agent lifetime.
    assert pol.evaluate(_obs(task_description="Update the decision log")) is None


def test_policy_silent_when_no_match() -> None:
    skills = [Skill(name="product-breakdown", description="decision records, IMP candidates")]
    pol = SkillInjectionPolicy(skills, role=None)
    assert pol.evaluate(_obs(task_description="Write a python function")) is None


def test_policy_requires_min_score() -> None:
    skills = [Skill(name="x", description="totally unrelated wording")]
    pol = SkillInjectionPolicy(skills, role=None, min_score=5)
    assert pol.evaluate(_obs(task_description="totally unrelated wording")) is None


def test_policy_silent_without_task_description() -> None:
    pol = SkillInjectionPolicy([Skill(name="a", description="d")], role=None)
    assert pol.evaluate(_obs(task_description=None)) is None


def test_policy_respects_role_scoping() -> None:
    skills = [Skill(name="mission-command", description="brief children with intent", roles=("orchestrator",))]
    worker_pol = SkillInjectionPolicy(skills, role="worker")
    assert worker_pol.evaluate(_obs(task_description="brief children with intent")) is None
    orchestrator_pol = SkillInjectionPolicy(skills, role="orchestrator")
    assert orchestrator_pol.evaluate(_obs(task_description="brief children with intent")) is not None


def test_observation_new_fields_have_defaults() -> None:
    obs = _obs()
    assert obs.task_description is None
    assert obs.role is None


@pytest.mark.asyncio
async def test_policy_wired_per_agent(tmp_path: Path) -> None:
    rt = _runtime_with_refs(tmp_path, {
        "product_breakdown.md": (
            "---\nname: product-breakdown\ndescription: decision records, IMP candidates\n---\n\n"
            "# Product Breakdown\n\nbody\n"
        ),
    })
    agent = rt.delegate(Task(description="Update the decision log for IMP-3"))
    names = agent.reactive_policies.names()
    assert "skill_injection" in names