"""Common interface for metric-reactive policy objects.

The recurring shape across the harness' prompt-guiding policies is the same:
*observe a live metric, decide a reaction, and produce a directive that
injects / alters the agent's prompt.* ``LoopGuard`` (loop metrics → notice /
nudge / fail), ``NudgePolicy`` (delegation scarcity + low iteration budget →
warning), and ``SpawnWarningPolicy`` (near-cap spawn usage → notice) all had
this skeleton with different payloads and different side-effect call-sites.

This module names that contract exactly once, so a plugin host (MCP server /
extension) can implement and register policies against it without touching the
run loop:

- ``Observation`` — the immutable snapshot of the metrics policies react to.
- ``PromptInjection`` — the resulting prompt alteration (a user message to
  append + severity + activity payload + whether the run must stop).
- ``ReactivePolicy`` — the decision interface: ``name`` + ``evaluate(obs)``.
- ``ReactivePolicyRegistry`` — a host-agnostic ordered runner; register a
  policy, and the agent loop applies whatever directive comes back through the
  shared applier.

A policy decides; the host executes. No object in this module imports an agent
or a runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class PromptInjection:
    """One directive from a reactive policy: a prompt alteration to apply.

    ``message`` is appended as a fresh user message to the agent's live
    context (tail-append-only, so the cached prompt prefix stays contiguous).
    ``level`` ranks the directive (``notice`` / ``warning`` / ``critical``);
    ``warning_type`` names it for activity events; ``data`` is the optional
    activity-event payload. ``stop=True`` means the host must terminate the
    run after applying (used by the loop-detection fail ladder).
    """

    message: str
    level: str = "warning"
    warning_type: str = "notice"
    data: dict[str, Any] | None = None
    stop: bool = False

    @classmethod
    def notice(
        cls,
        message: str,
        *,
        warning_type: str,
        data: dict[str, Any] | None = None,
    ) -> "PromptInjection":
        """Non-fatal informational injection (e.g. the near-identical notice)."""
        return cls(
            message=message,
            level="notice",
            warning_type=warning_type,
            data=data,
        )

    @classmethod
    def warning(
        cls,
        message: str,
        *,
        warning_type: str,
        data: dict[str, Any] | None = None,
    ) -> "PromptInjection":
        """Corrective but non-fatal injection (e.g. a recovery nudge)."""
        return cls(
            message=message,
            level="warning",
            warning_type=warning_type,
            data=data,
        )

    @classmethod
    def critical(
        cls,
        message: str,
        *,
        warning_type: str,
        data: dict[str, Any] | None = None,
    ) -> "PromptInjection":
        """Terminal directive: the run must stop after applying."""
        return cls(
            message=message,
            level="critical",
            warning_type=warning_type,
            data=data,
            stop=True,
        )


@dataclass(frozen=True)
class Observation:
    """Snapshot of the live metrics a reactive policy reacts to.

    Built once per turn by the host (the agent), handed to every registered
    policy unchanged. Tool calls are duck-typed (``.name`` / ``.arguments``),
    matching what ``LoopGuard.check`` already consumes.
    """

    iteration: int
    max_iterations: int
    has_delegated: bool
    tool_calls: list[Any] = field(default_factory=list)
    assistant_content: str | None = None
    tree_depth: int = 0
    spawn_usage: dict[str, Any] | None = None


@runtime_checkable
class ReactivePolicy(Protocol):
    """The plugin contract: react to an observation or produce nothing.

    A policy may keep its own state (budgets, sliding windows) but must not
    perform host side effects — injection / activity / termination are applied
    by the host from the returned ``PromptInjection``(s).
    """

    name: str

    def evaluate(
        self, observation: Observation
    ) -> PromptInjection | list[PromptInjection] | None: ...


class ReactivePolicyRegistry:
    """Ordered registry of ``ReactivePolicy`` objects.

    Registered policies are evaluated in order; each contributes zero or more
    ``PromptInjection``s. Re-registering a name replaces that policy in place,
    which is how a host overrides a default without touching the run loop.
    """

    def __init__(self, *policies: ReactivePolicy) -> None:
        self._policies: list[ReactivePolicy] = []
        for policy in policies:
            self.add(policy)

    def add(self, policy: ReactivePolicy) -> None:
        """Register a policy (replacing any policy with the same name)."""
        self._policies = [p for p in self._policies if p.name != policy.name]
        self._policies.append(policy)

    def unregister(self, name: str) -> None:
        self._policies = [p for p in self._policies if p.name != name]

    def get(self, name: str) -> ReactivePolicy | None:
        for policy in self._policies:
            if policy.name == name:
                return policy
        return None

    def names(self) -> list[str]:
        return [p.name for p in self._policies]

    def evaluate_all(self, observation: Observation) -> list[PromptInjection]:
        """Run every registered policy over ``observation``, flattening their
        directives into one list (in registration order)."""
        out: list[PromptInjection] = []
        for policy in self._policies:
            result = policy.evaluate(observation)
            if result is None:
                continue
            if isinstance(result, PromptInjection):
                out.append(result)
            else:
                out.extend(result)
        return out

    def __iter__(self):
        return iter(self._policies)

    def __len__(self) -> int:
        return len(self._policies)