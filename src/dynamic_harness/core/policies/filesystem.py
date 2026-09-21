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

    ``read_only_roots`` are additional roots the agent may *read* (but never
    write) — used for the durable reference library, which lives with the
    harness package rather than in the project workspace, so agents can reach
    it with the normal file tools from any working directory.
    """

    def __init__(
        self,
        root: Path | None = None,
        read_only_roots: tuple[Path, ...] = (),
    ) -> None:
        #: The workspace an agent is allowed to operate in (read/glob/grep).
        self.root: Path = root if root is not None else Path.cwd()
        #: Roots readable but not writable (e.g. the bundled reference library).
        self.read_only_roots: tuple[Path, ...] = tuple(read_only_roots)

    @classmethod
    def for_context(
        cls,
        generated_root: Path | None,
        read_only_roots: tuple[Path, ...] = (),
    ) -> "SandboxPolicy":
        """Bind to a runtime's generated root (falls back to cwd)."""
        return cls(
            root=generated_root or Path.cwd(),
            read_only_roots=read_only_roots,
        )

    def resolve_safe_path(self, path: str, *, write: bool = True) -> Path:
        """Resolve ``path`` (absolute, or relative to the sandbox root) and
        refuse anything that escapes the workspace.

        ``write=True`` (the conservative default) requires the path to be
        inside the workspace root. ``write=False`` additionally permits paths
        under the read-only roots (the reference library), so agents can read
        durable docs that live with the harness rather than in the project.
        """
        sandbox = self.root
        p = Path(path)
        if p.is_absolute():
            resolved = p.resolve()
        else:
            resolved = (sandbox / p).resolve()
        if sandbox in resolved.parents or resolved == sandbox:
            return resolved
        if not write:
            for rroot in self.read_only_roots:
                if rroot in resolved.parents or resolved == rroot:
                    return resolved
        raise ValueError(
            f"Path '{path}' is outside the workspace. You may only access "
            f"paths under the workspace root: {sandbox}. Use a relative path "
            f"or report a file and reference it by its artifact ID instead."
        )

    @staticmethod
    def is_hidden(path: Union[str, Path]) -> bool:
        """True for any path with a dot-prefixed component."""
        p = Path(path)
        for part in p.parts:
            if part.startswith("."):
                return True
        return False