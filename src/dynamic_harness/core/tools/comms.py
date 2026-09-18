"""Communication tools — one uniform surface across all topologies.

Every tool is a thin wrapper over the runtime's comms backend; no tool knows
which topology is live. The backend performs the routing decision, so a cell
switch is purely a construction change (config / ``Runtime(comms=...)``).

Read-only tools (``channels``, ``channel_info``, ``channel_read``) are pure
reads over live state and are exempt from repeated-call detection (they sit in
``safety.repeated_call_exempt_tools``); mutators (``post``, ``subscribe``,
``unsubscribe``, ``message``) are never cached and participate in loop
detection like any other side-effecting call.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..policies.permissions import ToolPermissionPolicy
from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext


def _disabled() -> str:
    return (
        "Communication is disabled (communication.topology is 'off'). "
        "Use converse() for direct by-ID messaging; no channel tools exist."
    )


def _require_backend(ctx: "ToolContext"):
    backend = ctx.comms
    if backend is None:
        return None
    return backend


TOOL_POST_DEF = ToolDef(
    name="post",
    description="Publish a message to a topic channel. Subscribers see it on "
                "their next channel_read. kind='instruction' is BINDING (use "
                "sparingly, only from a parent coordinating work); "
                "'notification' is advisory related-work; 'question' asks "
                "subscribers for input. stage marks the content draft/revised/"
                "final. In the 'shared' topology all topics collapse to the one "
                "shared channel. Posting to an unknown topic may create it "
                "subject to the topology's registration policy.",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Channel/topic name to publish to"},
            "content": {"type": "string", "description": "The message (≤200 chars is pushed; keep the headline tight)"},
            "kind": {"type": "string", "enum": ["notification", "instruction", "question"], "description": "notification (default) = advisory; instruction = binding; question = asks for input"},
            "stage": {"type": "string", "enum": ["draft", "revised", "final"], "description": "Maturity of the content (default final)"},
        },
        "required": ["topic", "content"],
    },
)

TOOL_CHANNEL_READ_DEF = ToolDef(
    name="channel_read",
    description="Read NEW messages on a topic since your last read (per-agent "
                "watermark). Pure pull: cache-friendly, safe to poll. Returns "
                "folded envelopes (kind/sender/stage/headline), not full "
                "bodies — pull the body via read_artifact if a pointer is "
                "given. In the 'shared' topology every topic reads the one "
                "shared channel.",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Topic to consume"},
        },
        "required": ["topic"],
    },
)

TOOL_CHANNELS_DEF = ToolDef(
    name="channels",
    description="List known topic channels and whether you are subscribed to "
                "each. Pure read, cache-friendly. The initial channel directory "
                "is also described in your environment; use this for live "
                "changes.",
    input_schema={"type": "object", "properties": {}, "required": []},
)

TOOL_CHANNEL_INFO_DEF = ToolDef(
    name="channel_info",
    description="Details for one topic: owner, subscriber count, last activity, "
                "and whether you subscribe. Pure read, cache-friendly.",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Topic to inspect"},
        },
        "required": ["topic"],
    },
)

TOOL_SUBSCRIBE_DEF = ToolDef(
    name="subscribe",
    description="Declare ongoing interest in a topic: it becomes part of your "
                "channel view (and, when push digests exist, your digest). "
                "Joining an existing topic is open; creating an unknown one is "
                "gated by the registration policy. Idempotent. In the 'shared' "
                "topology subscription is universal — this is a no-op success.",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Topic to subscribe to"},
        },
        "required": ["topic"],
    },
)

TOOL_UNSUBSCRIBE_DEF = ToolDef(
    name="unsubscribe",
    description="Stop tracking a topic. Your watermark/read history is kept; "
                "you simply stop listing it as subscribed.",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Topic to unsubscribe from"},
        },
        "required": ["topic"],
    },
)

TOOL_MESSAGE_DEF = ToolDef(
    name="message",
    description="Send a fire-and-forget message to a specific agent, delivered "
                "to its inbox and processed on its next turn (unlike converse, "
                "which waits for a reply). The topology routes it: parent-"
                "mediated topologies relay peer messages to the common parent; "
                "sibling topologies allow same-parent peers; channel topologies "
                "restrict peer messaging to your parent/children (use post for "
                "peers).",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "Target agent id"},
            "content": {"type": "string", "description": "The message"},
            "kind": {"type": "string", "enum": ["notification", "instruction", "question"], "description": "instruction (default for message) = binding; notification = advisory"},
        },
        "required": ["agent_id", "content"],
    },
)


def _new_message(ctx: "ToolContext", topic: str, kind: str, stage: str, content: str, recipients: list[str]):
    from ..comms import CommsMessage

    return CommsMessage(
        id=ctx.agent_id[:4], topic=topic, kind=kind, stage=stage,
        sender_id=ctx.agent_id, recipients=recipients, content=content,
    )


async def post(*, ctx: "ToolContext", topic: str, content: str, kind: str = "notification", stage: str = "final") -> str:
    backend = _require_backend(ctx)
    if backend is None:
        return _disabled()
    refusal = backend.post(ctx.sender_ref, topic, content, kind=kind, stage=stage)
    if refusal:
        return f"Error: {refusal}"
    return f"Posted to '{topic}' (kind={kind}): {content[:100]}"


async def channel_read(*, ctx: "ToolContext", topic: str) -> str:
    backend = _require_backend(ctx)
    if backend is None:
        return _disabled()
    from ..comms import render_channel_envelope

    outcome = backend.read(ctx.sender_ref, topic)
    if outcome.refusal:
        return f"Error: {outcome.refusal}"
    if not outcome.messages:
        return f"[{topic}] no new messages."
    body = "\n\n".join(render_channel_envelope(m) for m in outcome.messages)
    return f"[{topic}] {len(outcome.messages)} new message(s):\n{body}"


async def channels(*, ctx: "ToolContext") -> str:
    backend = _require_backend(ctx)
    if backend is None:
        return _disabled()
    return json.dumps(backend.channels(ctx.sender_ref), indent=2)


async def channel_info(*, ctx: "ToolContext", topic: str) -> str:
    backend = _require_backend(ctx)
    if backend is None:
        return _disabled()
    info = backend.channel_info(topic)
    if info is None:
        return f"Error: unknown topic '{topic}' (see `channels`)"
    return json.dumps(info, indent=2)


async def subscribe(*, ctx: "ToolContext", topic: str) -> str:
    backend = _require_backend(ctx)
    if backend is None:
        return _disabled()
    refusal = backend.subscribe(ctx.sender_ref, topic)
    if refusal:
        return f"Error: {refusal}"
    return f"Subscribed to '{topic}'."


async def unsubscribe(*, ctx: "ToolContext", topic: str) -> str:
    backend = _require_backend(ctx)
    if backend is None:
        return _disabled()
    refusal = backend.unsubscribe(ctx.sender_ref, topic)
    if refusal:
        return f"Error: {refusal}"
    return f"Unsubscribed from '{topic}'."


async def message(*, ctx: "ToolContext", agent_id: str, content: str, kind: str = "instruction") -> str:
    backend = _require_backend(ctx)
    if backend is None:
        return _disabled()
    target = ctx.get_other_agent(agent_id)
    if not target:
        return f"Error: no agent found with ID {agent_id}"
    if not ToolPermissionPolicy.conversable(target.task.status):
        return (
            f"Error: agent {agent_id} status is '{target.task.status.value}', "
            f"cannot message. Use resume(agent_id, note=...) to recover a "
            f"failed/under-delivered child instead."
        )
    from ..comms import render_incoming

    msg = _new_message(ctx, "", kind, "final", content, [agent_id])
    verdict = backend.route_message(ctx.sender_ref, msg)
    if not verdict.allowed:
        return f"Error: {verdict.refusal}"
    for recipient in verdict.recipients:
        ctx.queue_comms_message(recipient, render_incoming(msg))
    shown = ", ".join(f"{r[:8]}" for r in verdict.recipients)
    return f"Message routed to: {shown}."