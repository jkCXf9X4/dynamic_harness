"""Reference library: durable rationale that survives prompt optimization."""

from __future__ import annotations

from pathlib import Path

from dynamic_harness.config import HarnessConfig
from dynamic_harness.core.references import (
    ReferenceDoc,
    Skill,
    SkillRegistry,
    discover_references,
    discover_skills,
    render_reference_index,
    render_skill_triggers,
    resolve_references_root,
)
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task


def _make_doc(root: Path, name: str, body: str) -> Path:
    p = root / name
    p.write_text(body)
    return p


def test_discover_references_reads_heading_and_summary(tmp_path: Path) -> None:
    p = _make_doc(
        tmp_path,
        "guidelines.md",
        "# Delegation is the default\n\n"
        "Decompose aggressively. Each unit of work is a fresh sub-agent.\n",
    )
    docs = discover_references(tmp_path)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "Delegation is the default"
    assert doc.summary.startswith("Decompose aggressively")
    assert doc.path == str(p)


def test_discover_references_missing_dir_returns_empty() -> None:
    assert discover_references("/nonexistent/references/dir") == []


def test_discover_references_uses_frontmatter_description(tmp_path: Path) -> None:
    p = _make_doc(
        tmp_path,
        "rationale.md",
        "---\n"
        "description: Use when working in product-breakdown/ decision records.\n"
        "---\n\n"
        "# Product Breakdown Structure\n\n"
        "Seven-layer product-definition flow with per-layer decision records.\n",
    )
    docs = discover_references(tmp_path)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "Product Breakdown Structure"
    assert doc.summary == "Use when working in product-breakdown/ decision records."
    assert doc.path == str(p)


def test_skill_shaped_docs_excluded_from_plain_references(tmp_path: Path) -> None:
    """A doc with name + description frontmatter is a skill, not a reference."""
    _make_doc(
        tmp_path,
        "product_breakdown_skill.md",
        "---\n"
        "name: product-breakdown\n"
        "description: Use when working in product-breakdown/ decision records.\n"
        "---\n\n"
        "# Product Breakdown Structure\n\n"
        "Seven-layer product-definition flow with per-layer decision records.\n",
    )
    _make_doc(tmp_path, "plain.md", "# Plain\n\njust a rationale doc\n")
    assert [d.filename for d in discover_references(tmp_path)] == ["plain.md"]
    assert [s.name for s in discover_skills(tmp_path)] == ["product-breakdown"]


def test_discover_references_truncates_long_frontmatter_description(tmp_path: Path) -> None:
    long = "d" * 500
    _make_doc(
        tmp_path,
        "s.md",
        f"---\ndescription: {long}\n---\n\n# S\n\nbody\n",
    )
    (doc,) = discover_references(tmp_path)
    assert len(doc.summary) <= 200


def test_discover_references_ignores_non_doc_files(tmp_path: Path) -> None:
    (tmp_path / "notes.json").write_text("{}")
    (tmp_path / "cache.pyc").write_bytes(b"x")
    _make_doc(tmp_path, "a.md", "# A\n\nbody\n")
    docs = discover_references(tmp_path)
    assert [d.filename for d in docs] == ["a.md"]


def test_render_reference_index_empty_when_no_docs() -> None:
    assert render_reference_index([]) == ""


def test_render_reference_index_lists_each_doc() -> None:
    docs = [
        ReferenceDoc(id="a", filename="a.md", path="refs/a.md", title="A doc", summary="Short."),
        ReferenceDoc(id="b", filename="b.md", path="refs/b.md", title="B doc", summary=""),
    ]
    idx = render_reference_index(docs)
    assert "[Reference Library]" in idx
    assert "A doc [refs/a.md]" in idx
    assert "B doc [refs/b.md]" in idx
    # A body is never pulled into the index (progressive disclosure).
    assert "Short." in idx  # summary (200 chars) is fine
    assert "read()" in idx


def test_runtime_injects_reference_index_into_environment(tmp_path: Path) -> None:
    refs = tmp_path / "refs"
    refs.mkdir()
    body = "Full rationale body. " * 50  # far longer than the 200-char summary
    _make_doc(refs, "15288_rationale.md", f"# ISO 15288\n\n{body}\n")
    cfg = HarnessConfig()
    cfg.agent.references_dir = str(refs)

    rt = Runtime(
        artifact_root=tmp_path / "a",
        repo_root=tmp_path / "r",
        generated_root=tmp_path,
        config=cfg,
    )
    agent = rt.delegate(Task(description="T"))
    rendered = agent.environment_info
    assert "[Reference Library]" in rendered
    assert "15288" in rendered
    # Only the index is injected, never the full body.
    assert body not in rendered


def test_runtime_without_references_dir_is_unchanged(tmp_path: Path) -> None:
    cfg = HarnessConfig()
    rt = Runtime(
        artifact_root=tmp_path / "a",
        repo_root=tmp_path / "r",
        generated_root=tmp_path,
        config=cfg,
    )
    agent = rt.delegate(Task(description="T"))
    rendered = agent.environment_info
    # Environment notes still render even when no library exists.
    assert "[Environment]" in rendered


def test_runtime_injects_role_filtered_skill_triggers(tmp_path: Path) -> None:
    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "mission_command.md").write_text(
        "---\nname: mission-command\ndescription: Brief children with intent.\n"
        "roles:\n  - orchestrator\n---\n\n# Mission Command\n\nbrief body\n"
    )
    (refs / "tool_motivations.md").write_text(
        "---\nname: tool-motivations\ndescription: Choose between tools.\n---\n\n"
        "# Tool Motivations\n\ntool body\n"
    )
    cfg = HarnessConfig()
    cfg.agent.references_dir = str(refs)

    rt = Runtime(
        artifact_root=tmp_path / "a",
        repo_root=tmp_path / "r",
        generated_root=tmp_path,
        config=cfg,
    )
    worker = rt.delegate(Task(description="W"))
    assert "mission-command" not in worker.skill_triggers
    assert "tool-motivations" in worker.skill_triggers
    # Only triggers, never bodies.
    assert "tool body" not in worker.skill_triggers

    orchestrator = rt.delegate(Task(description="O", role="orchestrator"))
    assert "mission-command" in orchestrator.skill_triggers
    assert "tool-motivations" in orchestrator.skill_triggers

    # Triggers are folded into the static system-prompt steerage.
    blocks = orchestrator._build_steerage()
    assert "[Skills]" in blocks
    assert "mission-command: Brief children with intent." in blocks


async def test_reference_docs_readable_via_normal_tools_from_any_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    """The baked-in library is reachable with the plain file tools even when the
    harness runs from a separate project folder (reference root lives with the
    package, not the cwd; sandbox grants read-only access to it)."""
    monkeypatch.chdir(tmp_path)
    cfg = HarnessConfig()
    rt = Runtime(
        artifact_root=tmp_path / "a",
        repo_root=tmp_path / "r",
        generated_root=tmp_path,
        config=cfg,
    )
    assert rt.reference_root is not None
    agent = rt.delegate(Task(description="T"))

    target = rt.reference_root / "guidelines.md"
    res = await rt.tool_registry.execute("read", "tc1", agent, path=str(target))
    assert "outside the workspace" not in res.content
    assert "Delegate" in res.content

    glob_res = await rt.tool_registry.execute(
        "glob", "tc2", agent, pattern=str(rt.reference_root / "*.md")
    )
    assert "guidelines.md" in glob_res.content

    write_res = await rt.tool_registry.execute(
        "write", "tc3", agent,
        path=str(rt.reference_root / "pwned.md"), content="x",
    )
    assert "outside the workspace" in write_res.content


def test_default_references_dir_resolves_package_relative(tmp_path: Path, monkeypatch) -> None:
    """The default library is the harness package's docs, not the cwd project's.

    Running from a separate project folder must still discover the baked-in
    library (the product-breakdown skill etc.), so it resolves relative to the
    package rather than the process working directory.
    """
    monkeypatch.chdir(tmp_path)  # a random "target project" folder
    root = resolve_references_root(None)
    assert root is not None
    assert root.name == "references" or root.name == "docs"
    # The bundled library is skill-shaped (name + description frontmatter), so
    # skills — not plain references — are the discoverable surface from any cwd.
    skills = discover_skills(None)
    assert skills
    assert all(s.path.startswith(str(root)) for s in skills)
    refs = discover_references(None)
    assert all(d.path.startswith(str(root)) for d in refs)


def test_explicit_references_dir_override(tmp_path: Path) -> None:
    refs = tmp_path / "my_refs"
    refs.mkdir()
    _make_doc(refs, "local.md", "# Local\n\nlocal body\n")
    root = resolve_references_root(refs)
    assert root == refs
    docs = discover_references(refs)
    assert [d.filename for d in docs] == ["local.md"]


# -- skills ----------------------------------------------------------------


def _make_skill(root: Path, name: str, description: str, roles: str | None = None) -> Path:
    meta = [f"name: {name}", f"description: {description}"]
    if roles is not None:
        meta.append(roles)
    body = f"---\n{chr(10).join(meta)}\n---\n\n# {name}\n\nfull instructions body\n"
    return _make_doc(root, f"{name}.md", body)


def test_discover_skills_reads_name_description_and_roles(tmp_path: Path) -> None:
    _make_skill(tmp_path, "product-breakdown", "Use in decision records.", "roles: orchestrator, worker")
    _make_skill(tmp_path, "unscoped", "Available to everyone.")
    skills = discover_skills(tmp_path)
    assert [s.name for s in skills] == ["product-breakdown", "unscoped"]
    (scoped,) = [s for s in skills if s.name == "product-breakdown"]
    assert scoped.description == "Use in decision records."
    assert scoped.roles == ("orchestrator", "worker")
    (unscoped,) = [s for s in skills if s.name == "unscoped"]
    assert unscoped.roles == ()


def test_discover_skills_parses_yaml_list_roles(tmp_path: Path) -> None:
    _make_doc(
        tmp_path,
        "listy.md",
        "---\nname: listy\ndescription: d\nroles:\n  - orchestrator\n  - worker\n---\n\n"
        "# Listy\n\nbody\n",
    )
    (skill,) = discover_skills(tmp_path)
    assert skill.roles == ("orchestrator", "worker")


def test_discover_skills_missing_dir_returns_empty() -> None:
    assert discover_skills("/nonexistent/skills/dir") == []


def test_skill_body_strips_frontmatter(tmp_path: Path) -> None:
    p = _make_doc(
        tmp_path,
        "s.md",
        "---\nname: s\ndescription: d\nroles:\n  - worker\n---\n\n# The body\n\n"
        "full instructions live here\n",
    )
    (skill,) = discover_skills(tmp_path)
    assert "name: s" not in skill.body()
    assert "The body" in skill.body()
    assert "full instructions live here" in skill.body()


def test_skill_applies_to_role(tmp_path: Path) -> None:
    scoped = Skill(name="x", description="d", roles=("orchestrator",))
    assert scoped.applies_to_role("orchestrator")
    assert scoped.applies_to_role("Orchestrator")  # case-insensitive
    assert not scoped.applies_to_role("worker")
    assert not scoped.applies_to_role(None)
    unscoped = Skill(name="y", description="d")
    assert unscoped.applies_to_role("worker")
    assert unscoped.applies_to_role(None)


def test_skill_registry_lookup_and_role_filter(tmp_path: Path) -> None:
    skills = [
        Skill(name="a", description="da", roles=("orchestrator",)),
        Skill(name="b", description="db"),
    ]
    reg = SkillRegistry(skills)
    assert reg.get("a") is skills[0]
    assert reg.get("missing") is None
    assert reg.names() == ["a", "b"]
    assert [s.name for s in reg.for_role("orchestrator")] == ["a", "b"]
    assert [s.name for s in reg.for_role("worker")] == ["b"]
    assert [s.name for s in reg.for_role(None)] == ["b"]


def test_render_skill_triggers_empty_when_no_skills() -> None:
    assert render_skill_triggers([], role=None) == ""


def test_render_skill_triggers_filters_by_role() -> None:
    skills = [
        Skill(name="mission-command", description="Brief children.", roles=("orchestrator",)),
        Skill(name="tool-motivations", description="Choose tools."),
    ]
    # An agent without a role only sees unscoped skills.
    none_triggers = render_skill_triggers(skills, role=None)
    assert "mission-command" not in none_triggers
    assert "tool-motivations" in none_triggers
    worker_triggers = render_skill_triggers(skills, role="worker")
    assert "mission-command" not in worker_triggers
    assert "tool-motivations" in worker_triggers
    orchestrator_triggers = render_skill_triggers(skills, role="orchestrator")
    assert "mission-command" in orchestrator_triggers
    assert "tool-motivations" in orchestrator_triggers
    # The trigger is the description, not a body (bodies load via skill_load).
    assert "Brief children." in orchestrator_triggers


def test_render_skill_triggers_accepts_registry(tmp_path: Path) -> None:
    reg = SkillRegistry([Skill(name="a", description="da")])
    assert "a: da" in render_skill_triggers(reg, role=None)


def test_default_references_dir_discovers_bundled_skills(tmp_path: Path, monkeypatch) -> None:
    """The bundled library is all skill-shaped; skills stay discoverable from any cwd."""
    monkeypatch.chdir(tmp_path)
    skills = discover_skills(None)
    assert skills
    assert any(s.name == "product-breakdown" for s in skills)
