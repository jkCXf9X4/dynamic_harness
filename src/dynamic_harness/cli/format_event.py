from __future__ import annotations

from ..core.task import ActivityEvent, ActivityEventType

W = "\U0001f527"   # wrench (tool)
CK = "\u2705"      # check (tool result)
CH = "\U0001f4ac"  # chat bubble (LLM)
BB = "\U0001f476"  # baby (delegate)
LO = "\U0001f504"  # arrows (compression)
WARN = "\u26a0\ufe0f"  # warning


def format_event(
    event: ActivityEvent,
    *,
    emoji: bool = False,
    show_args: bool = False,
) -> str | None:
    """Render an ActivityEvent into a single line (no trailing newline).

    Used by both the Rich terminal and the Textual TUI so the event->text
    mapping lives in exactly one place.
    """
    eid = event.agent_id[:8]
    d = event.data
    et = event.event_type

    def lead(sym: str) -> str:
        return f"  [{eid}] {sym} " if emoji else f"  [{eid}] "

    if et == ActivityEventType.TOOL_CALL_START:
        name = d.get("tool_name", "?")
        args = d.get("arguments", {})
        arg_str = ""
        if show_args and args:
            arg_parts = ", ".join(f"{k}={str(v)[:30]}" for k, v in args.items())
            arg_str = f"({arg_parts})"
        return f"{lead(W if emoji else '')}{name}{arg_str}"
    elif et == ActivityEventType.TOOL_CALL_END:
        name = d.get("tool_name", "?")
        rlen = d.get("result_length", 0)
        return f"{lead(CK if emoji else '')}{name} \u2192 {rlen} bytes"
    elif et == ActivityEventType.LLM_CALL_END:
        tc = d.get("tool_calls", [])
        pt = d.get("prompt_tokens", 0)
        ct = d.get("completion_tokens", 0)
        tc_str = ", ".join(tc) if tc else ("text-only" if emoji else "text")
        return f"{lead(CH if emoji else '')}LLM \u2192 {tc_str} ({pt}+{ct} tokens)"
    elif et == ActivityEventType.DELEGATION_START:
        child = d.get("child_id", "?")[:8]
        desc = (d.get("description", "") or "")[:60]
        return f"{lead(BB if emoji else '')}delegate \u2192 {child} \"{desc}\""
    elif et == ActivityEventType.DELEGATION_END:
        child = d.get("child_id", "?")[:8]
        status = d.get("status", "?")
        return f"{lead(BB if emoji else '')}{child} \u2192 {status}"
    elif et == ActivityEventType.COMPRESSION:
        before = d.get("before", 0)
        after = d.get("after", 0)
        saved = d.get("saved", 0)
        return f"{lead(LO if emoji else '')}compressed {before}\u2192{after} msgs (-{saved})"
    elif et == ActivityEventType.SAFETY_WARNING:
        wtype = d.get("warning_type", "")
        if wtype == "max_iterations":
            return f"{lead(WARN if emoji else '')}\u26a0 max iterations ({d.get('iteration', 0)}/{d.get('limit', 0)})"
        return f"{lead(WARN if emoji else '')}\u26a0 repeated calls ({d.get('tool_name', '?')} x{d.get('repeated_count', 0)})"
    elif et == ActivityEventType.ITERATION:
        return None
    return None
