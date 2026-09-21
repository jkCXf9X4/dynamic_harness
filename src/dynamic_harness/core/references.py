"""Durable reference library — rationale that survives prompt optimization.

The live system prompt is a compressed, optimized derivation of the project's
principles, tool motivations, and guidelines. Prompt optimization can strip some of
that rationale away. This module discovers the git-tracked, on-disk source of truth
(by default ``docs/references/``) and hands agents a compact *index* they can
`read` from on demand — so the full rationale is always recoverable even if it was
optimized out of the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_REFERENCES_DIR = "docs/references"

_REFERENCE_EXTENSIONS = (".md", ".txt", ".markdown")

#: The harness's own bundled reference library, resolved relative to this module
#: (``src/dynamic_harness/core/references.py`` → repo root ``docs/references``)
#: so it stays reachable when the harness runs from a separate project folder.
_PACKAGE_REFERENCES_DIR = Path(__file__).resolve().parents[3] / DEFAULT_REFERENCES_DIR


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


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a leading ``---``-delimited YAML frontmatter block from the body.

    Returns ``({}, text)`` unchanged when no frontmatter block is present, so
    plain markdown files are untouched. Keys are read line-wise (``key: value``)
    until the closing ``---``; the first line of the body must not be ``---``.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1:])
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
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


def discover_references(root: str | Path | None = None) -> list[ReferenceDoc]:
    """Scan ``root`` (default ``docs/references``) for reference documents.

    Returns a sorted list of docs detected on disk. A missing or empty directory
    yields ``[]`` — never an error, so the library is purely additive.
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
