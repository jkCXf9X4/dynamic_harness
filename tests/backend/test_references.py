"""Reference library: durable rationale that survives prompt optimization."""

from __future__ import annotations

from pathlib import Path

from dynamic_harness.config import HarnessConfig
from dynamic_harness.core.references import (
    ReferenceDoc,
    discover_references,
    render_reference_index,
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
        "product_breakdown_skill.md",
        "---\n"
        "name: product-breakdown\n"
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
    docs = discover_references(None)
    assert docs  # the bundled library is found from any cwd
    assert all(d.path.startswith(str(root)) for d in docs)


def test_explicit_references_dir_override(tmp_path: Path) -> None:
    refs = tmp_path / "my_refs"
    refs.mkdir()
    _make_doc(refs, "local.md", "# Local\n\nlocal body\n")
    root = resolve_references_root(refs)
    assert root == refs
    docs = discover_references(refs)
    assert [d.filename for d in docs] == ["local.md"]
