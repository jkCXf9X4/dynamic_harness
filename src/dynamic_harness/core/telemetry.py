from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .task import ActivityEvent, ActivityEventType

if TYPE_CHECKING:
    from ..llm.provider import ToolCallData, ToolCallResponse
    from .agent import Agent
    from .checkpoint import CheckpointStore
    from .events import EventBus
    from .trace import TraceStore
    from .usage import UsageTracker


class Telemetry:
    """Per-agent facade separating the run loop from persistence I/O.

    The agent's run loop drives *orchestration* — send messages, execute tools,
    commit turns — and hands every durable or debugging side effect to this
    object: token-usage accounting, JSONL trace recording, activity events, and
    checkpoint persistence. The stores stay deliberately dumb (append-only
    records / aggregates); all of the wiring — which event produces which
    record — lives here in one place, so the loop can be read as pure policy.

    All methods are best-effort by construction: the event bus isolates handler
    failures, and checkpoint writes are already non-fatal, so a recording hiccup
    (missing trace directory, disk full) can never fail or slow the run.
    """

    def __init__(
        self,
        *,
        agent: Agent,
        event_bus: EventBus,
        usage_tracker: UsageTracker | None = None,
        trace_store: TraceStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None:
        self._agent = agent
        self._agent_id = agent.id
        self._event_bus = event_bus
        self._usage_tracker = usage_tracker
        self._trace_store = trace_store
        self._checkpoint_store = checkpoint_store

    # -- turn-level -------------------------------------------------------

    def turn_started(self, prompt_tokens: int) -> None:
        """Per-iteration bookkeeping event (turn n, current message count)."""
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self._agent_id,
            event_type=ActivityEventType.ITERATION,
            data={
                "turn": self._agent.iteration_count,
                "messages": self._agent.message_count,
                "prompt_tokens": prompt_tokens,
            },
        ))

    def request(self, sent: list[dict[str, Any]]) -> None:
        """Record the exact request payload at send time.

        Called BEFORE awaiting the provider so trace latency reflects the real
        in-flight duration, and so ``sent`` is the exact snapshot the LLM saw.
        """
        ts = self._trace_store
        if ts is not None:
            ts.record_llm_request(self._agent_id, list(sent))

    async def llm_call(
        self, response: ToolCallResponse, sent: list[dict[str, Any]], duration_ms: float
    ) -> None:
        """Record one completed LLM call: usage, trace entry, and activity event.

        ``sent`` is the message list that produced ``response``; it feeds the
        message-count usage metric so accounting matches what left the wire.
        """
        usage = response.usage
        if usage and self._usage_tracker is not None:
            await self._usage_tracker.record_usage(
                self._agent_id,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cached_tokens=usage.get("cached_tokens", 0),
                message_count=len(sent),
            )
        names = [tc.name for tc in (response.tool_calls or [])]
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self._agent_id,
            event_type=ActivityEventType.LLM_CALL_END,
            data={
                "model": response.model,
                "prompt_tokens": usage.get("prompt_tokens", 0) if usage else 0,
                "completion_tokens": usage.get("completion_tokens", 0) if usage else 0,
                "tool_calls": names,
            },
        ))
        ts = self._trace_store
        if ts is not None:
            tc_info = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in (response.tool_calls or [])
            ]
            ts.record_llm_response(
                self._agent_id,
                response.content,
                response.model,
                usage,
                tc_info,
                duration_ms=duration_ms,
            )

    # -- tool-level -------------------------------------------------------

    def tool_started(self, tc: ToolCallData) -> None:
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self._agent_id,
            event_type=ActivityEventType.TOOL_CALL_START,
            data={"tool_name": tc.name, "arguments": tc.arguments},
        ))
        ts = self._trace_store
        if ts is not None:
            ts.record_tool_call(self._agent_id, tc.id, tc.name, tc.arguments)

    def tool_finished(self, tc: ToolCallData, content: str) -> None:
        ts = self._trace_store
        if ts is not None:
            ts.record_tool_result(self._agent_id, tc.id, tc.name, content)
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self._agent_id,
            event_type=ActivityEventType.TOOL_CALL_END,
            data={
                "tool_name": tc.name,
                "result_length": len(content),
                "result_preview": content[:200],
            },
        ))

    def tool_failed(self, tc: ToolCallData, error: Exception) -> None:
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self._agent_id,
            event_type=ActivityEventType.TOOL_CALL_END,
            data={"tool_name": tc.name, "error": str(error)},
        ))

    # -- durable state ----------------------------------------------------

    def persist_checkpoint(self) -> None:
        """Persist the agent's state to disk, best-effort (never fatal).

        Kept flow-coupled (not purely event-driven) because checkpoint timing is
        tied to crash-resume semantics: certain terminal/append paths commit
        context without a full turn commit, and the natural persist points live
        in the loop regardless of refactoring. Error handling mirrors the old
        inline behavior — trace the failure and warn, then keep going.
        """
        store = self._checkpoint_store
        if store is None:
            return
        try:
            store.save(self._agent)
        except Exception as exc:
            ts = self._trace_store
            if ts is not None:
                ts.record_event(self._agent_id, "checkpoint_error", error=str(exc))
            self._event_bus.emit_activity(ActivityEvent(
                agent_id=self._agent_id,
                event_type=ActivityEventType.SAFETY_WARNING,
                data={"warning_type": "checkpoint_error", "error": str(exc)},
            ))

    def event(self, name: str, **kwargs: Any) -> None:
        """Record an arbitrary trace event (failures, agent errors)."""
        ts = self._trace_store
        if ts is not None:
            ts.record_event(self._agent_id, name, **kwargs)