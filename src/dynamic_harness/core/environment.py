"""Runtime-detected environment description injected into every agent.

Environment truth must come from the running process, never hardcoded source.
The agent observes this as a single ``[Environment]`` block in its context
observation instead of trusting stale import-time strings.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class EnvironmentInfo:
    python_version: str
    working_dir: str
    packages: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    git_available: bool = True

    def render(self) -> str:
        lines = [
            "[Environment]",
            f"Python {self.python_version}",
            f"Working dir: {self.working_dir}",
            f"Git available: {'yes' if self.git_available else 'no'}",
        ]
        if self.packages:
            lines.append("Packages: " + ", ".join(sorted(self.packages)))
        if self.notes:
            lines.extend(self.notes)
        return "\n".join(lines)


_SOFTWARE_PACKAGES = (
    "pydantic", "openai", "httpx", "rich", "textual", "pathspec", "yaml", "dotenv",
)


def _installed_packages() -> tuple[str, ...]:
    import importlib.util
    return tuple(
        name for name in _SOFTWARE_PACKAGES
        if importlib.util.find_spec(name) is not None
    )


def build_environment_info(notes: Sequence[str] = ()) -> EnvironmentInfo:
    """Best-effort detection of the process environment the agent runs in.

    ``notes`` are experiment/tooling-specific instructions supplied via config
    (e.g. "pip is unavailable", "do not install packages"); they default empty
    so the agent is never told facts that may be false here.
    """
    return EnvironmentInfo(
        python_version=platform.python_version(),
        working_dir=str(Path.cwd()),
        packages=_installed_packages(),
        notes=tuple(notes),
        git_available=True,
    )
