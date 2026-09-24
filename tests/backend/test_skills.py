"""Skills layer: the skill_load tool, the proactive SkillInjectionPolicy, and
the filesystem role gate (read/glob/grep refuse role-scoped skill files)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_harness.config import HarnessConfig
from dynamic_harness.core.policies.interface import Observation
from dynamic_harness.core.policies.skill_inject import SkillInjectionPolicy
from dynamic_harness.core.references import Skill
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task


def _write_skill(root: Path, name: str, description: str, roles: str | None = None, body: str = "body") -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    meta = [f"name: {name}", f"description: {description}"]
    if roles is not None:
        meta.append(roles)
    (d / "SKILL.md").write_text(
        f"---\n{chr(10).join(meta)}\n---\n\n# {name}\n\n{body}\n"
    )
    return d


def _runtime_with_skills(tmp_path: Path, specs: dict[str, tuple[str, str | None]], body: str = "body") -> Runtime:
    d = tmp_path / "skills"
    d.mkdir(parents=True, exist_ok=True)
    for name, (description, roles) in specs.items():
        _write_skill(d, name, description, roles, body=body)
    cfg = HarnessConfig()
    cfg.agent.skills_dir = str(d)
    return Runtime(
        artifact_root=tmp_path / "a",
        repo_root=tmp_path / "r",
        generated_root=tmp_path,
        config=cfg,
    )


_skill_body = (
    "# Tool Motivations\n\n## Discovery tools\n\n- **glob** — find files.\n"
)


# -- skill_load tool -------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_load_returns_body(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {"tool-motivations": ("Choose between tools.", None)}, body=_skill_body)
    agent = rt.delegate(Task(description="T"))
    result = await rt.tool_registry.execute(
        "skill_load", "tc1", agent=agent, skill="tool-motivations", token_limit=2000
    )
    assert "Error" not in result.content
    assert "Discovery tools" in result.content
    # Frontmatter is stripped from the body.
    assert "name: tool-motivations" not in result.content


@pytest.mark.asyncio
async def test_skill_load_advertises_resources(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {
        "product-breakdown": ("Product breakdown work.", None),
    })
    agent = rt.delegate(Task(description="T"))
    result = await rt.tool_registry.execute("skill_load", "tc1", agent=agent, skill="product-breakdown")
    assert "[skill resources]" in result.content
    assert "skills/product-breakdown" in result.content
    # The resource note is prefixed so it survives truncation; the body follows.
    assert result.content.index("[skill resources]") < result.content.index("# product-breakdown")


@pytest.mark.asyncio
async def test_skill_load_unknown_name(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {"tool-motivations": ("Choose between tools.", None)})
    agent = rt.delegate(Task(description="T"))
    result = await rt.tool_registry.execute("skill_load", "tc1", agent=agent, skill="nope")
    assert "Error: unknown skill 'nope'" in result.content
    assert "tool-motivations" in result.content  # lists available skills


@pytest.mark.asyncio
async def test_skill_load_no_library(runtime: Runtime, tmp_path: Path) -> None:
    cfg = HarnessConfig()
    cfg.agent.skills_dir = str(tmp_path / "does_not_exist")
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
    rt = _runtime_with_skills(tmp_path, {
        "mission-command": ("Brief children.", "roles:\n  - orchestrator"),
    })
    worker = rt.delegate(Task(description="W"))
    res = await rt.tool_registry.execute("skill_load", "tc1", agent=worker, skill="mission-command")
    assert "status: refused" in res.content
    assert "scoped to role" in res.content

    orchestrator = rt.delegate(Task(description="O", role="orchestrator"))
    res = await rt.tool_registry.execute("skill_load", "tc2", agent=orchestrator, skill="mission-command")
    assert "status: refused" not in res.content
    assert "body" in res.content


@pytest.mark.asyncio
async def test_skill_load_is_cacheable(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {"tool-motivations": ("Choose between tools.", None)})
    agent = rt.delegate(Task(description="T"))
    result = await rt.tool_registry.execute("skill_load", "tc1", agent=agent, skill="tool-motivations")
    assert result.result_id is not None  # read-only → snapshotted behind a handle


# -- filesystem role gate ---------------------------------------------------


@pytest.mark.asyncio
async def test_read_refuses_role_scoped_skill_file(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {
        "mission-command": ("Brief children.", "roles:\n  - manager"),
    })
    worker = rt.delegate(Task(description="W", role="worker"))
    target = rt.skills_root / "mission-command" / "SKILL.md"
    res = await rt.tool_registry.execute("read", "tc1", agent=worker, path=str(target))
    assert "status: refused" in res.content
    assert "mission-command" in res.content

    manager = rt.delegate(Task(description="M", role="manager"))
    res = await rt.tool_registry.execute("read", "tc2", agent=manager, path=str(target))
    assert "status: refused" not in res.content
    assert "body" in res.content


@pytest.mark.asyncio
async def test_read_grants_unscoped_skill_file(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {
        "tool-motivations": ("Choose between tools.", None),
    })
    worker = rt.delegate(Task(description="W"))
    target = rt.skills_root / "tool-motivations" / "SKILL.md"
    res = await rt.tool_registry.execute("read", "tc1", agent=worker, path=str(target))
    assert "status: refused" not in res.content
    assert "body" in res.content  # raw read returns the file (frontmatter included)


@pytest.mark.asyncio
async def test_read_refuses_skill_resource_files(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {
        "mission-command": ("Brief children.", "roles:\n  - manager"),
    })
    resource = rt.skills_root / "mission-command" / "extra.md"
    resource.write_text("secret resource\n")
    worker = rt.delegate(Task(description="W", role="worker"))
    res = await rt.tool_registry.execute("read", "tc1", agent=worker, path=str(resource))
    assert "status: refused" in res.content


@pytest.mark.asyncio
async def test_glob_filters_role_scoped_skill_files(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {
        "mission-command": ("Brief children.", "roles:\n  - orchestrator"),
        "tool-motivations": ("Choose between tools.", None),
    })
    worker = rt.delegate(Task(description="W"))
    res = await rt.tool_registry.execute(
        "glob", "tc1", agent=worker, pattern=str(rt.skills_root / "**/*.md")
    )
    assert "tool-motivations" in res.content
    assert "mission-command" not in res.content


@pytest.mark.asyncio
async def test_grep_skips_role_scoped_skill_files(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {
        "mission-command": ("Brief children.", "roles:\n  - orchestrator"),
        "tool-motivations": ("Choose between tools.", None),
    })
    worker = rt.delegate(Task(description="W"))
    res = await rt.tool_registry.execute(
        "grep", "tc1", agent=worker, pattern="body", path=str(rt.skills_root)
    )
    assert "tool-motivations" in res.content
    assert "mission-command" not in res.content


@pytest.mark.asyncio
async def test_write_refused_in_skills_root(tmp_path: Path) -> None:
    rt = _runtime_with_skills(tmp_path, {
        "tool-motivations": ("Choose between tools.", None),
    })
    worker = rt.delegate(Task(description="W"))
    target = rt.skills_root / "tool-motivations" / "pwned.md"
    res = await rt.tool_registry.execute("write", "tc1", agent=worker, path=str(target), content="x")
    assert "read-only" in res.content


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
    rt = _runtime_with_skills(tmp_path, {
        "product-breakdown": ("decision records, IMP candidates", None),
    })
    agent = rt.delegate(Task(description="Update the decision log for IMP-3"))
    names = agent.reactive_policies.names()
    assert "skill_injection" in names