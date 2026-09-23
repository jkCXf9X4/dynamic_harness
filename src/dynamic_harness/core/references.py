"""Durable reference library + skills — rationale that survives prompt optimization.

The live system prompt is a compressed, optimized derivation of the project's
principles, tool motivations, and guidelines. Prompt optimization can strip some of
that rationale away. This module discovers the git-tracked, on-disk source of truth
and hands agents a compact *index* they can pull full bodies from on demand — so the
rationale is always recoverable even if it was optimized out of the prompt.

Two separate, canonical roots (each discovered independently):

- **References** (``docs/references/``) — plain rationale docs, listed in a compact
  index the agent ``read``s on demand. Never role-scoped.
- **Skills** (``skills/``) — task-specific instruction packages, one directory per
  skill (``skills/<name>/SKILL.md`` with ``name`` + ``description`` frontmatter,
  optional ``roles``, and sibling resource files). The ``description`` is a
  *trigger*: a short when-to-use signal that is always visible, while the full body
  is loaded on demand via the ``skill_load`` tool. A skill with a ``roles`` scope is
  only listed for — and only readable by — agents whose ``role`` tag matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_REFERENCES_DIR = "docs/references"
DEFAULT_SKILLS_DIR = "skills"

_REFERENCE_EXTENSIONS = (".md", ".txt", ".markdown")

#: The harness's own bundled library, resolved relative to this module
#: (``src/dynamic_harness/core/references.py`` → repo root ``docs/references``
#: and ``skills``) so it stays reachable when the harness runs from a separate
#: project folder.
_PACKAGE_REFERENCES_DIR = Path(__file__).resolve().parents[3] / DEFAULT_REFERENCES_DIR
_PACKAGE_SKILLS_DIR = Path(__file__).resolve().parents[3] / DEFAULT_SKILLS_DIR


def resolve_references_root(root: str | Path | None) -> Path | None:
    """Effective references root: explicit override, else the bundled library.

    An explicit ``root`` is used as given. With ``None`` the default is the
    harness package's own ``docs/references`` (independent of the process cwd);
    a cwd-relative ``docs/references`` is kept as a fallback so projects that
    carry their own library still resolve it. Returns ``None`` when no library
    exists — the library is purely additive.
    """
    if root is not None:
        return Path(root)
    if _PACKAGE_REFERENCES_DIR.is_dir():
        return _PACKAGE_REFERENCES_DIR
    cwd_refs = Path(DEFAULT_REFERENCES_DIR)
    return cwd_refs if cwd_refs.is_dir() else None


def resolve_skills_root(root: str | Path | None) -> Path | None:
    """Effective skills root: explicit override, else the bundled library.

    Mirrors ``resolve_references_root``: with ``None`` the default is the
    package's own ``skills`` (independent of the process cwd), with a cwd-relative
    ``skills`` fallback. Returns ``None`` when no skills exist — purely additive.
    """
    if root is not None:
        return Path(root)
    if _PACKAGE_SKILLS_DIR.is_dir():
        return _PACKAGE_SKILLS_DIR
    cwd_skills = Path(DEFAULT_SKILLS_DIR)
    return cwd_skills if cwd_skills.is_dir() else None


@dataclass(frozen=True)
class ReferenceDoc:
    """A single durable reference document."""

    id: str
    filename: str
    path: str
    title: str = ""
    summary: str = ""

    def render_index_line(self) -> str:
        tail = f" — {self.summary}" if self.summary else ""
        return f"- {self.title} [{self.path}] ({self.filename}){tail}"


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a leading ``---``-delimited YAML frontmatter block from the body.

    Returns ``({}, text)`` unchanged when no frontmatter block is present, so
    plain markdown files are untouched. Keys are read line-wise (``key: value``)
    until the closing ``---``; a key with an empty value collects a following
    YAML list block (``- item`` lines) into a list. The first line of the body
    must not be ``---``.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, Any] = {}
    i = 1
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped == "---":
            return meta, "\n".join(lines[i + 1:])
        key, sep, value = line.partition(":")
        if sep:
            key = key.strip()
            value = value.strip()
            if (
                not value
                and i + 1 < len(lines)
                and lines[i + 1].strip().startswith("- ")
            ):
                items: list[str] = []
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith("- "):
                    items.append(lines[j].strip()[2:].strip())
                    j += 1
                if items:
                    meta[key] = items
                    i = j
                    continue
            meta[key] = value
        i += 1
    return {}, text


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def _first_paragraph(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:200]
    return ""


def _normalize_roles(value: Any) -> tuple[str, ...]:
    """Normalize a ``roles`` frontmatter value (scalar or list) to a sorted
    tuple of lowercase role tags."""
    if value is None:
        return ()
    if isinstance(value, str):
        parts = value.replace(",", " ").split()
    else:
        parts = [str(v) for v in value]
    return tuple(sorted({p.strip().lower() for p in parts if p.strip()}))


@dataclass(frozen=True)
class Skill:
    """A skill-shaped instruction doc: name + description triggers, body on demand.

    Canonical storage is one directory per skill (``skills/<name>/SKILL.md``),
    with sibling resource files reachable via ``dir``. The ``description`` is the
    *trigger* the model matches against its task; the body is loaded via
    ``skill_load`` only when the model decides it applies. ``roles`` scopes
    visibility, loading, *and* raw file access to agents with a matching role tag
    (an unscoped skill is available to everyone).
    """

    name: str
    description: str
    roles: tuple[str, ...] = ()
    path: str = ""
    dir: str = ""
    filename: str = ""

    def applies_to_role(self, role: str | None) -> bool:
        if not self.roles:
            return True
        return (role or "").strip().lower() in self.roles

    def body(self) -> str:
        """The skill's instructions, with the frontmatter stripped."""
        if not self.path:
            return ""
        try:
            text = Path(self.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        _, body = _split_frontmatter(text)
        return body.strip()

    def render_trigger_line(self) -> str:
        return f"- {self.name}: {self.description}"


class SkillRegistry:
    """Named lookup + role filtering over the discovered skill library.

    Host-agnostic (no agent/runtime import): the runtime discovers the skills
    once and hands this registry to tools and policies, which ask for a skill by
    name or by role.
    """

    def __init__(self, skills: list[Skill]) -> None:
        self._skills: list[Skill] = list(skills)
        self._by_name: dict[str, Skill] = {s.name: s for s in self._skills}

    def __iter__(self):
        return iter(self._skills)

    def __len__(self) -> int:
        return len(self._skills)

    def all(self) -> list[Skill]:
        return list(self._skills)

    def get(self, name: str) -> Skill | None:
        return self._by_name.get(name)

    def for_role(self, role: str | None) -> list[Skill]:
        return [s for s in self._skills if s.applies_to_role(role)]

    def names(self) -> list[str]:
        return [s.name for s in self._skills]

    def skill_for_path(self, path: str | Path) -> Skill | None:
        """The skill owning ``path``, or None when the path belongs to no skill.

        Any path under a skill's directory (or equal to its file) belongs to that
        skill, so the filesystem layer can enforce the same role gate the
        ``skill_load`` tool applies — a role-scoped skill's files are not readable
        by out-of-scope agents through any tool.
        """
        p = Path(path).resolve()
        for skill in self._skills:
            if not skill.dir:
                continue
            d = Path(skill.dir).resolve()
            if d == p or d in p.parents:
                return skill
        return None


def discover_references(root: str | Path | None = None) -> list[ReferenceDoc]:
    """Scan ``root`` (default ``docs/references``) for reference documents.

    References and skills live in separate roots: anything under the references
    root is a reference, regardless of frontmatter. Returns a sorted list of docs
    detected on disk. A missing or empty directory yields ``[]`` — never an
    error, so the library is purely additive.
    """
    base = resolve_references_root(root)
    if base is None or not base.is_dir():
        return []
    docs: list[ReferenceDoc] = []
    for p in sorted(base.iterdir()):
        if not p.is_file() or p.suffix.lower() not in _REFERENCE_EXTENSIONS:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        frontmatter, body = _split_frontmatter(text)
        docs.append(ReferenceDoc(
            id=p.stem,
            filename=p.name,
            path=str(p),
            title=_first_heading(body) or frontmatter.get("name") or p.stem,
            summary=(frontmatter.get("description") or _first_paragraph(body))[:200],
        ))
    return docs


def discover_skills(root: str | Path | None = None) -> list[Skill]:
    """Scan ``root`` (default ``skills``) for skills.

    Canonical storage is one directory per skill: ``<root>/<name>/SKILL.md``
    with ``description`` (and optional ``roles``) frontmatter; the skill name is
    the directory name. A missing or empty root yields ``[]`` — never an error.
    The library is purely additive.
    """
    base = resolve_skills_root(root)
    if base is None or not base.is_dir():
        return []
    skills: list[Skill] = []
    for directory in sorted(base.iterdir()):
        if not directory.is_dir():
            continue
        sk = _discover_skill_dir(directory)
        if sk is not None:
            skills.append(sk)
    return skills


def _discover_skill_dir(directory: Path) -> Skill | None:
    """A ``SKILL.md`` in a directory is a skill named after that directory."""
    sk_file = directory / "SKILL.md"
    if not sk_file.is_file():
        return None
    try:
        text = sk_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    frontmatter, _body = _split_frontmatter(text)
    description = str(frontmatter.get("description") or "").strip()
    if not description:
        return None
    name = str(frontmatter.get("name") or directory.name).strip() or directory.name
    return Skill(
        name=name,
        description=description,
        roles=_normalize_roles(frontmatter.get("roles")),
        path=str(sk_file),
        dir=str(directory),
        filename="SKILL.md",
    )


def render_reference_index(docs: list[ReferenceDoc]) -> str:
    """Render a compact index of available references.

    Kept small on purpose: the index is injected into the agent's environment so it
    *knows the library exists and where*, while the full bodies are only pulled into
    context via ``read`` on demand (progressive disclosure).
    """
    if not docs:
        return ""
    lines = [
        "[Reference Library]",
        "Durable rationale survives prompt optimization. Read the file(s) you need "
        "via read() (this lives outside the optimized prompt).",
    ]
    lines.extend(doc.render_index_line() for doc in docs)
    return "\n".join(lines)


def render_skill_triggers(skills: list[Skill] | SkillRegistry, role: str | None = None) -> str:
    """Render the compact skill trigger list visible to an agent's role.

    Role-scoped skills are filtered: an unscoped skill is visible to everyone; a
    skill with a ``roles`` scope is listed only when the agent's role matches.
    Only the name + description trigger is rendered — never the body, which is
    loaded on demand via ``skill_load('<name>')`` (progressive disclosure).
    """
    registry = skills if isinstance(skills, SkillRegistry) else SkillRegistry(skills)
    visible = registry.for_role(role)
    if not visible:
        return ""
    lines = [
        "[Skills]",
        "Task-specific instructions are packaged as skills. Load a skill's full "
        "instructions with skill_load('<name>') when its trigger applies to your task:",
    ]
    lines.extend(s.render_trigger_line() for s in visible)
    return "\n".join(lines)