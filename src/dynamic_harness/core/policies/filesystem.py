"""Filesystem sandbox + containment policy as a composable policy object.

The path-traversal guard (``resolve_safe_path``), sandbox root selection, and
hidden-file filtering used to be private functions inside the filesystem
tools. This policy owns those decisions so a plugin host providing guarded
``read``/``write``/``glob``/``grep`` MCP wrappers — the advertised bridge
tools — applies the same containment without importing a tool.

The policy is pure: path + sandbox root in → resolved/denied out.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union


class SandboxPolicy:
    """Decides which paths an agent may touch and which files to filter.

    Host-agnostic: an MCP filesystem wrapper reuses the same sandbox boundary,
    so a path the harness refuses stays refused on the host.
    """

    def __init__(self, root: Path | None = None) -> None:
        #: The workspace an agent is allowed to operate in (read/glob/grep).
        self.root: Path = root if root is not None else Path.cwd()

    @classmethod
    def for_context(cls, generated_root: Path | None) -> "SandboxPolicy":
        """Bind to a runtime's generated root (falls back to cwd)."""
        return cls(root=generated_root or Path.cwd())

    def resolve_safe_path(self, path: str) -> Path:
        """Resolve ``path`` (absolute, or relative to the sandbox root) and
        refuse anything that escapes the workspace."""
        sandbox = self.root
        p = Path(path)
        if p.is_absolute():
            resolved = p.resolve()
        else:
            resolved = (sandbox / p).resolve()
        if sandbox not in resolved.parents and resolved != sandbox:
            raise ValueError(
                f"Path '{path}' is outside the workspace. You may only access "
                f"paths under the workspace root: {sandbox}. Use a relative path "
                f"or report a file and reference it by its artifact ID instead."
            )
        return resolved

    @staticmethod
    def is_hidden(path: Union[str, Path]) -> bool:
        """True for any path with a dot-prefixed component."""
        p = Path(path)
        for part in p.parts:
            if part.startswith("."):
                return True
        return False