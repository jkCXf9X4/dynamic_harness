"""The ``codeact`` agent type — the measurement cell for the code-as-action
investigation (proposal §5).

Mirrors OpenHands' minimalist agent: a single ``invoke(code)`` action surface,
plus the terminal (``report``) and lean-context observation tools (``usage``,
``status``, ``result_read``/``result_bash``). The rich capability — read/write/
grep/delegate/ask/converse/comms/plan — is deliberately NOT in the direct tool
surface; the model reaches it by writing code that calls the injected
``harness_tools`` RPC stub, which routes every call back through
``ToolRegistry.execute()`` so the same policies (sandbox roots, spawn caps,
comms routing, budget lines) apply to code-driven actions.

This keeps the measurement honest: the *model contract* is collapsed to one
tool (the paradigm), while the runtime retains its rich, policy-enforcing
surface behind the stub (the harness's identity — see the build-vs-extend
leaf). Register on a runtime with ``register_codeact(runtime)``, then delegate
with ``agent_type="codeact"``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .agent import Agent

if TYPE_CHECKING:
    from .runtime import Runtime


#: The minimalist tool surface exposed directly to a codeact agent.
#: ``invoke`` is the single action tool; ``report`` is the terminal contract;
#: ``usage``/``status`` are the self-observation knobs (a codeact agent has no
#: message list of its own, so it monitors itself through the runtime);
#: ``result_read``/``result_bash`` page the cached outputs produced inside
#: ``invoke`` (and by harness_tools calls) without re-running anything.
CODECT_TOOLS: frozenset[str] = frozenset({
    "invoke", "report",
    "result_read", "result_bash", "usage", "status",
})


class CodeActAgent(Agent):
    """An agent whose action surface is a single ``invoke(code)`` tool.

    Construction knobs are identical to the base ``Agent`` (the runtime builds
    it through the same ``AgentPolicy``); only the exposed tool surface and the
    loop-guard family (source-normalized ``invoke`` snippets) differ.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.allowed_tools = CODECT_TOOLS
        # Re-issuing near-identical code is the codeact churn loop; detect it
        # with the source-normalized family key instead of the bash one.
        self._near_identical_tools = ("invoke",)


def register_codeact(runtime: "Runtime") -> None:
    """Register the ``codeact`` agent type on a runtime (idempotent)."""
    runtime.register_agent_class("codeact", CodeActAgent)