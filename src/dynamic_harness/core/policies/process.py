"""Shell-safety policy as a composable policy object.

The ``bash`` tool's concurrency decision — which commands mutate state and
therefore need the global repo lock serialized — used to live as module
constants inside the tool. This policy owns that classification, plus the
shell-metacharacter detection and the leading-``cd`` prefix handling, so a
plugin host providing a guarded ``bash`` wrapper (one of the advertised MCP
bridge tools) applies the same safety decisions without importing the tool.

The policy is pure: it never acquires locks or spawns processes. The caller
decides what to do with the verdict (acquire the repo lock / use a shell / set
the workdir).
"""

from __future__ import annotations

import re


class BashSafetyPolicy:
    """Decides read-only-ness, shell-ness, and workdir for a bash command.

    Host-agnostic: an MCP ``bash`` wrapper reuses the exact same classification
    so a command the harness treats as read-only stays read-only on the host.
    """

    #: Commands that only read, so no repo lock is needed.
    READ_ONLY_COMMANDS: frozenset[str] = frozenset({
        "ls", "cat", "head", "tail", "grep", "find", "pwd", "which",
        "python3", "python", "echo", "env", "printenv", "wc", "sort", "uniq",
    })

    READ_ONLY_GIT_SUBCOMMANDS: frozenset[str] = frozenset({
        "status", "log", "show", "diff", "branch", "config", "stash", "blame",
        "rev-parse",
    })

    #: Shell metacharacters that require a shell to interpret (&&, ||, |, ;, <,
    #: >, backtick). A leading `cd <dir> &&` is handled separately and stripped
    #: before this check so a bare `cd X && ls` chain still funnels into the
    #: shell path.
    SHELL_META: re.Pattern[str] = re.compile(r"[|&;<>`]")

    #: Leading `cd <dir> && ` (or a bare `cd <dir>`). Captured as the working
    #: directory; the remainder is the command to run.
    LEADING_CD: re.Pattern[str] = re.compile(r"^\s*cd\s+(\S+)\s*(?:&&\s*)?")

    @classmethod
    def is_read_only(cls, args: list[str]) -> bool:
        """Heuristic: does this command only read, so no repo lock is needed?"""
        if not args:
            return True
        from pathlib import Path

        base = Path(args[0]).name
        if base in cls.READ_ONLY_COMMANDS:
            return True
        if base == "git" and len(args) > 1 and args[1] in cls.READ_ONLY_GIT_SUBCOMMANDS:
            return True
        return False

    @classmethod
    def needs_shell(cls, command: str) -> bool:
        """Shell operators present -> interpret via a shell so ``cd X && ...``,
        pipes, and chained commands run instead of a hard exec error."""
        return bool(cls.SHELL_META.search(command))

    @classmethod
    def resolve_workdir(cls, command: str, workdir: str | None) -> tuple[str, str | None]:
        """Pull a leading ``cd <dir> &&`` prefix into the working directory.

        Stripping it here means a common agent habit — ``cd /path && ls ...`` —
        stops failing as an ``exec`` ``[Errno 2] No such file or directory:
        'cd'`` error, which was churning the conversation prefix with identical
        repeated failures. Returns ``(command_without_cd, resolved_workdir)``.
        """
        m = cls.LEADING_CD.match(command or "")
        if not m:
            return command, (workdir or None)
        resolved = workdir or m.group(1)
        rest = (command[m.end():]).strip()
        if not rest:
            return "", resolved
        return rest, resolved