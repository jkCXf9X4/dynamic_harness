"""Loop-safety as a composable policy object.

The repeated-call and near-identical detection that ``Agent`` used to run
inline in ``_run_loop`` lives here as a standalone, stateful ``LoopGuard``.
It owns the sliding-window deques, the per-family warning budgets, and the
recovery-budget decision (nudge first, fail when exhausted) — and returns
structured ``LoopAction`` verdicts instead of mutating an agent.

The module-level signature helpers (``normalize_tool_signature``,
``bash_family``, ``bash_read_regions``, ...) are pure functions so they can
be reused by any host (MCP server, opencode/pi extension) without importing
an agent.
"""

from __future__ import annotations

import json as _json
import re
from collections import deque
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from .spawn import delegate_target_signature as _delegate_target_signature

# File-like token used by the bash near-identical read-region parser.
_FILE_TOKEN = re.compile(
    r"([\w./~@-]+\.(?:cpp|hpp|c|h|md|json|txt|py|toml|csv|log|ya?ml|ini|rc|in)|"
    r"(?:\./)?[\w./~@-]+\.dynamic-harness/[\w./~@-]+)"
)


def normalize_tool_signature(name: str, arguments: dict[str, Any]) -> str:
    """Canonical, whitespace-insensitive key for a single tool call.

    Small stylistic variation (quote style, padding, casing, shell chaining)
    is folded away so a genuinely stuck loop is not hidden by the model
    nudging the wording/format of an identical command.
    """
    parts: list[str] = []
    for key in sorted(arguments):
        val = arguments[key]
        if isinstance(val, str):
            val = "_".join(val.split()).strip().lower()
        parts.append(f"{key}={_json.dumps(val, sort_keys=True)}")
    return f"{name}({' '.join(parts)})"


def paginationless_signature(
    name: str, arguments: dict[str, Any], exclude: set[str] | None = None
) -> str:
    """Signature used for *similarity* scoring: pagination knobs are dropped
    so legitimately paged reads (token_offset/token_limit changing) never
    look like a duplicated command."""
    skip = exclude or {"token_offset", "token_limit"}
    parts: list[str] = []
    for key in sorted(arguments):
        if key in skip:
            continue
        val = arguments[key]
        if isinstance(val, str):
            val = "_".join(val.split()).strip().lower()
        parts.append(f"{key}={_json.dumps(val, sort_keys=True)}")
    return f"{name}({' '.join(parts)})"


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# -- bash pagination normalization --------------------------------------
# `token_offset`/`token_limit` kwargs only cover *read-style* pagination.
# Bash re-reads churn by re-wrapping the SAME content in sed/awk/head/tail
# variants, which defeats a purely kwargs-based signature. These helpers
# collapse the line-range/pagination tokens so that re-fetching the same
# lines through a different wrapper groups under one family, while
# strictly-disjoint forward paging is still recognized as progress.


def bash_family(command: str) -> str:
    """Pagination-insensitive family key for a bash command.

    Line ranges (``sed -n '59,140p'`` / ``awk 'NR>=59 && NR<=140'``),
    head/tail counts and token knobs collapse to placeholders, whitespace
    folds and quotes drop. Two commands that differ only in *how much* of the
    same material they show share a family; commands touching different paths
    do not.
    """
    text = command
    text = re.sub(r"sed\s+-n\s*'?\d+\s*,\s*\d+p'?", "sed -n RANGE", text)
    text = re.sub(r"awk\s+'NR\s*>=\s*\d+\s*&&\s*NR\s*<=\s*\d+", "awk NR-RANGE", text)
    text = re.sub(r"\bhead\s+(?:-[a-zA-Z]+\s+)?-?\d+\b", "head -N", text)
    text = re.sub(r"\btail\s+(?:-[a-zA-Z]+\s+)?-?\d+\b", "tail -N", text)
    text = re.sub(r"\btoken_offset\s*=\s*\d+\b", "token_offset=N", text)
    text = re.sub(r"\btoken_limit\s*=\s*\d+\b", "token_limit=N", text)
    text = text.replace("'", "").replace('"', "")
    return "_".join(text.split()).strip().lower()


def bash_read_regions(command: str) -> list[tuple[str, int, int]]:
    """Extract (file, lo, hi) reads from a bash command.

    Lets near-identical detection tell genuine forward paging (disjoint,
    advancing ranges) apart from re-reading the same lines through a
    different sedan wrapper. Only read-ish verbs with an explicit file
    produce regions; commands with no parseable file stay empty and fall
    back to the generic similarity path.
    """
    BIG = 1 << 31
    regions: list[tuple[str, int, int]] = []

    def last_path(seg: str) -> str | None:
        toks = _FILE_TOKEN.findall(seg)
        return toks[-1] if toks else None

    for seg in re.split(r"\||;", command):
        m = re.search(r"sed\s+-n\s*'?(\d+)\s*,\s*(\d+)p'?[^|]*", seg)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            p = _FILE_TOKEN.search(seg[m.end():].strip()) or last_path(seg)
            if p:
                regions.append((str(p) if not isinstance(p, tuple) else p[0], lo, hi))
            continue
        m = re.search(r"awk\s+'NR\s*>=\s*(\d+)\s*&&\s*NR\s*<=\s*(\d+)", seg)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            p = last_path(seg)
            if p:
                regions.append((str(p) if not isinstance(p, tuple) else p[0], lo, hi))
            continue
        m = re.search(r"\b(head|tail)\s+(?:-[a-zA-Z0-9]+\s+)?-?(\d+)\b[^|]*", seg)
        if m:
            n = int(m.group(2))
            p = _FILE_TOKEN.search(seg[m.end():].strip()) or last_path(seg)
            if p:
                path = str(p) if not isinstance(p, tuple) else p[0]
                if m.group(1) == "tail":
                    regions.append((path, max(0, BIG - n), BIG))
                else:
                    regions.append((path, 0, n))
            continue
        # Read-ish verbs with an explicit file: the whole file is the region.
        if re.search(r"\b(?:cat|grep|wc|git\s+show|git\s+diff|find|xxd|od|nl)\b", seg):
            p = last_path(seg)
            if p:
                regions.append((str(p) if not isinstance(p, tuple) else p[0], 0, BIG))
    # Dedupe exact (path, lo, hi) triples.
    return list(dict.fromkeys(regions))


def regions_overlap(a: list[tuple[str, int, int]], b: list[tuple[str, int, int]]) -> bool:
    """True when the same file is read at overlapping ranges in both sets.

    Open-interval overlap: strictly-disjoint adjacent ranges (e.g. 1-50 then
    51-100) are treated as forward progress, not a re-read.
    """
    for pa, loa, hia in a:
        for pb, lob, hib in b:
            if pa != pb:
                continue
            if loa < hib and lob < hia:
                return True
    return False


def delegate_target_signature(arguments: dict[str, Any]) -> str:
    """Normalized key for a delegate call, keyed on the referenced path(s).

    Catches the failure mode where an orchestrator re-reads *the same file*
    (or re-explores *the same directory*) by spinning a fresh sub-agent each
    time with superficially different wording (e.g. 'read X verbatim' →
    'read X from offset N' → ...). Shared with the runtime's same-target
    spawn cap so both in-context loop detection and the lineage-wide cap
    agree on the signature.
    """
    description = str(arguments.get("description", ""))
    return _delegate_target_signature(description)


@dataclass(frozen=True)
class LoopAction:
    """One verdict from ``LoopGuard.check`` for the caller to apply.

    ``action`` is one of ``"continue"`` (non-fatal notice injected and the
    loop keeps running), ``"nudge"`` (warning appended, one recovery attempt
    consumed), or ``"fail"`` (force-fail the run).
    """

    action: str  # "continue" | "nudge" | "fail"
    warning_type: str  # "repeated_calls" | "near_identical_calls"
    tool_name: str
    count: int
    user_message: str | None = None
    activity: dict[str, Any] | None = None

    @property
    def stop(self) -> bool:
        return self.action == "fail"


class LoopGuard:
    """Stateful repeated-call / near-identical detection.

    Each agent owns one guard. The guard records every observed turn's tool
    calls and, when a loop shape fires, returns ``LoopAction``(s) the agent
    applies (nudge → fail ladder, or a non-fatal near-identical notice).
    """

    def __init__(
        self,
        *,
        repeated_call_limit: int = 5,
        repeated_call_exempt_tools: tuple[str, ...] | list[str] | None = None,
        repeated_recovery_attempts: int = 2,
        near_identical_threshold: int = 3,
        near_identical_window: int = 6,
        near_identical_similarity: float = 0.6,
        near_identical_tools: tuple[str, ...] | list[str] | None = None,
        near_identical_warning_attempts: int = 2,
    ) -> None:
        self.repeated_call_limit: int = max(int(repeated_call_limit), 1)
        self.exempt_tools: tuple[str, ...] = tuple(
            repeated_call_exempt_tools
            if repeated_call_exempt_tools is not None
            else ("status", "usage", "result_read", "result_bash")
        )
        # Remaining chances to nudge a looping agent out of its rut before
        # repeated-call detection force-fails it (0 = fail on first detection).
        self.repeated_recovery_left: int = max(int(repeated_recovery_attempts), 0)
        self.near_identical_threshold: int = max(int(near_identical_threshold), 1)
        self.near_identical_window: int = max(int(near_identical_window), 2)
        self.near_identical_similarity: float = float(near_identical_similarity)
        self.near_identical_tools: tuple[str, ...] = tuple(
            near_identical_tools if near_identical_tools is not None else ("bash",)
        )
        self.near_identical_warning_attempts: int = max(
            int(near_identical_warning_attempts), 0
        )

        self.recent_batches: deque[list[tuple[str, str]]] = deque(
            maxlen=self.repeated_call_limit
        )
        self.recent_delegate_targets: deque[str] = deque(maxlen=self.repeated_call_limit)
        self.recent_tool_signatures: deque[str] = deque(
            maxlen=max(self.repeated_call_limit * 3, 1)
        )
        self.recent_messages: deque[str] = deque(
            maxlen=max(self.repeated_call_limit * 3, 1)
        )
        # (family, regions, core sig, full sig, tool name) tuples, sliding window.
        self.recent_near_identical: deque[tuple[str, Any, str, str, str]] = deque(
            maxlen=self.near_identical_window
        )
        # Warning budget is per distinct command *family*, not a global counter.
        self.near_identical_warned: dict[str, int] = {}
        # Rot discriminator: set once a loop shape fired. Read by diagnosis.
        self.repeated_calls_detected: bool = False

    def clear(self) -> None:
        """Drop detection state (fresh run / garbage collection)."""
        self.recent_batches.clear()
        self.recent_tool_signatures.clear()
        self.recent_messages.clear()
        self.recent_delegate_targets.clear()
        self.recent_near_identical.clear()
        self.near_identical_warned.clear()

    def check(self, tool_calls: list[Any], content: str | None = None) -> list[LoopAction]:
        """Inspect one turn's tool calls; return the actions to apply.

        ``tool_calls`` items need only expose ``.name`` and ``.arguments``
        (duck-typed; an LLM response's tool-call objects work directly).
        Returns an empty list when the turn is clean.
        """
        # -- repeated-call ladder -----------------------------------------
        exempt = self.exempt_tools
        batch_sig = tuple(
            (tc.name, _json.dumps(tc.arguments, sort_keys=True))
            for tc in tool_calls
            if tc.name not in exempt
        )
        # Pure-monitoring turn (e.g. a parent polling its children's status):
        # nothing to detect, and it must not poison the deques for the next
        # real-work turn.
        if not batch_sig:
            return []
        self.recent_batches.append(batch_sig)

        if (
            len(self.recent_batches) == self.repeated_call_limit
            and all(sig == batch_sig for sig in self.recent_batches)
        ):
            return [
                self._nudge_or_fail(
                    "Repeated identical tool calls",
                    next(t[0] for t in batch_sig),
                    self.repeated_call_limit,
                )
            ]

        # Sliding-window frequency check over individual normalized calls.
        # Any tool name+args occurring `limit` times within the last
        # (limit*2) calls is treated as a loop, even if batches interleave
        # with a sibling variant.
        limit = self.repeated_call_limit
        for tc in tool_calls:
            if tc.name in exempt:
                continue
            sig = normalize_tool_signature(tc.name, tc.arguments)
            self.recent_tool_signatures.append(sig)
        if len(self.recent_tool_signatures) >= limit:
            recent = list(self.recent_tool_signatures)
            window = recent[-limit * 2:]
            for sig in set(window):
                if window.count(sig) >= limit:
                    return [
                        self._nudge_or_fail(
                            f"Tool call '{sig}' appeared {limit} times in the "
                            f"last {limit * 2} calls",
                            tool_calls[-1].name, limit,
                        )
                    ]

        # Identical assistant text repeated many times is also a stuck signal,
        # regardless of how the tool arguments vary around it. Whitespace-only
        # content (e.g. "\n\n" emitted before a tool call) is NOT a real
        # response: recording empty strings poisons the deque and would
        # force-fail a healthy model that emits a newline placeholder.
        if content and content.strip():
            self.recent_messages.append(content.strip())
        if len(self.recent_messages) >= limit * 2:
            recent_msgs = list(self.recent_messages)
            if recent_msgs[-limit:] == [recent_msgs[-1]] * limit:
                return [
                    self._nudge_or_fail(
                        "Repeated identical assistant responses", "LLM", limit
                    )
                ]

        # Semantic guard: many consecutive delegate calls aimed at the *same*
        # target (path) signal a verification loop, even if the wording varies.
        for tc in tool_calls:
            if tc.name == "delegate":
                sig = delegate_target_signature(tc.arguments)
                self.recent_delegate_targets.append(sig)
                if (
                    len(self.recent_delegate_targets) == limit
                    and len(set(self.recent_delegate_targets)) == 1
                ):
                    return [
                        self._nudge_or_fail(
                            f"Delegated {limit} times in a row aimed at the "
                            "same target",
                            "delegate", limit,
                        )
                    ]

        # Softly warn about *near*-identical (similar-not-bytes-equal) calls
        # only when no hard loop detection fired this turn, so the agent gets
        # actionable paginate/delegate guidance without a duplicate fail-nudge.
        # Returns an action only when a family fired (warning, or an escalation
        # into the hard detection ladder).
        return self._warn_near_identical(tool_calls)

    # -- near-identical detection ----------------------------------------

    def _warn_near_identical(self, tool_calls: list[Any]) -> list[LoopAction]:
        """Warn about *near*-identical monitored-tool calls (e.g. re-reading
        the same file through different sed/awk/head wrappers).

        The warning budget (``near_identical_warning_attempts``) is held per
        distinct command *family*, not as a global counter: a family that
        stopped recurring can re-appear later and still be warned, and a
        family that keeps re-reading the same material after its budget is
        exhausted escalates into the hard detection ladder (nudge first, fail
        when the recovery budget runs out) instead of going permanently
        silent. This stops the trace failure mode where a spent budget let a
        sed/awk re-read loop run for dozens of extra turns.
        """
        if self.near_identical_warning_attempts <= 0 or not self.near_identical_tools:
            return []
        if not tool_calls:
            return []
        near = self.near_identical_tools
        entries: list[tuple[str, list[tuple[str, int, int]] | None, str, str, str]] = []
        for tc in tool_calls:
            if tc.name not in near:
                continue
            args = tc.arguments or {}
            core = paginationless_signature(tc.name, args)
            full = paginationless_signature(tc.name, args, exclude=set())
            if tc.name == "bash":
                command = str(args.get("command", ""))
                family = bash_family(command)
                regions = bash_read_regions(command) or None
            else:
                family = core
                regions = None
            self.recent_near_identical.append((family, regions, core, full, tc.name))
            entries.append((family, regions, core, full, tc.name))

        rec = list(self.recent_near_identical)
        if len(rec) < self.near_identical_threshold:
            return []

        for family, regions, core, full, name in entries:
            count = 0
            for fam_old, reg_old, core_old, full_old, _ in rec:
                if regions is not None and reg_old is not None:
                    # Both sides have file/range info: the repeat signal is a
                    # shared path read at an overlapping range — caught even
                    # when the wrapper text differs structurally. Disjoint
                    # advancing paging and different paths stay silent.
                    if regions_overlap(regions, reg_old):
                        count += 1
                elif core != core_old and (
                    similarity(full, full_old) >= self.near_identical_similarity
                ):
                    # No region info on at least one side: fall back to the
                    # generic rule. Identical core (e.g. only token pagination
                    # advancing) remains benign.
                    count += 1
            if count < self.near_identical_threshold:
                continue
            used = self.near_identical_warned.get(family, 0)
            if used < self.near_identical_warning_attempts:
                self.near_identical_warned[family] = used + 1
                return [
                    LoopAction(
                        action="continue",
                        warning_type="near_identical_calls",
                        tool_name=name,
                        count=count,
                        user_message=(
                            "[notice] You have issued "
                            f"{count} near-identical '{name}' tool calls in the "
                            f"last {len(rec)} turns (e.g. re-reading the same "
                            "file/lines through slightly different "
                            "sed/awk/head/sort variants). Each returns the same "
                            "material. Stop re-running these: for files use the "
                            "read tool with token_offset/token_limit or delegate "
                            "the distinct pieces, and for shell output re-run "
                            "the SAME command with a larger token_limit. Move on "
                            "to the next step and report / escalate / fail. This "
                            "is a warning only — it will not fail the run on "
                            "this turn."
                        ),
                        activity={
                            "warning_type": "near_identical_calls",
                            "tool_name": name,
                            "similar_count": count,
                            "window": len(rec),
                            "family": family,
                            "attempts_remaining": (
                                self.near_identical_warning_attempts - used - 1
                            ),
                        },
                    )
                ]
            # A family that persists past its budget escalates into the hard
            # detection ladder (nudge, then fail) instead of going silent.
            return [
                self._nudge_or_fail(
                    "near-identical "
                    f"'{name}' calls re-reading the same material",
                    name, count,
                )
            ]
        return []

    # -- nudge-or-fail ladder --------------------------------------------

    def _nudge_or_fail(self, message: str, tool_name: str, count: int) -> LoopAction:
        """React to a detected loop: nudge first, fail only when the recovery
        budget is exhausted.

        While at least one nudge remains we return a ``"nudge"`` action (the
        agent appends the warning and keeps running); the next detection
        consumes the remaining attempts; only then — or immediately when
        ``repeated_recovery_attempts=0`` — do we return ``"fail"``.
        """
        if self.repeated_recovery_left > 0:
            self.repeated_recovery_left -= 1
            self.repeated_calls_detected = True
            return LoopAction(
                action="nudge",
                warning_type="repeated_calls",
                tool_name=tool_name,
                count=count,
                user_message=(
                    "[safety] You are looping — you have repeated "
                    f"{message.lower()} (tool: {tool_name}) {count} times in a "
                    "row. This looks stuck. Your next turn must take a genuinely "
                    "different approach or finish via report/escalate/fail. "
                    f"You have {self.repeated_recovery_left + 1} more such "
                    "warning(s) before this run is failed."
                ),
                activity={
                    "warning_type": "repeated_calls",
                    "tool_name": tool_name,
                    "repeated_count": count,
                    "nudged": True,
                    "recovery_remaining": self.repeated_recovery_left,
                },
            )
        self.repeated_calls_detected = True
        return LoopAction(
            action="fail",
            warning_type="repeated_calls",
            tool_name=tool_name,
            count=count,
            user_message=(
                f"{message} {count} times in a row (tool: {tool_name}). "
                f"The provider may be stuck. Change strategy or stop."
            ),
            activity={
                "warning_type": "repeated_calls",
                "tool_name": tool_name,
                "repeated_count": count,
            },
        )