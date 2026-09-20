"""Communication layer: backend routing + tool surface.

Two layers of coverage:

1. **Pure backend routing** (FakeView, no agents/LLM): the four topology cells
   make the *correct routing decision* — relay re-routes peers to the parent,
   siblings allow same-parent peers only, shared/topics are hierarchy-only for
   by-ID messaging and channel-based otherwise, and creation authority obeys
   the registration policy.
2. **Tool integration** (real Runtime + ToolContext): the uniform tool surface
   works end-to-end through the runtime's comms backend, and switching via
   ``communication.topology`` actually changes routing.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from dynamic_harness.config import CommsConfig, HarnessConfig
from dynamic_harness.core.comms import (
    AgentRef,
    ChannelPolicy,
    CommsDigestPolicy,
    CommsLog,
    build_backend,
    render_digest,
)
from dynamic_harness.core.comms.backend import CommsBackend
from dynamic_harness.core.comms.backends.relay import RelayBackend
from dynamic_harness.core.comms.backends.shared import SharedBackend
from dynamic_harness.core.comms.backends.siblings import SiblingsBackend
from dynamic_harness.core.comms.backends.topics import TopicsBackend
from dynamic_harness.core.policies.interface import Observation
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.core.tool_context import ToolContext
from dynamic_harness.core.tools import comms as comms_tools
from dynamic_harness.core.tools.agents import converse


class FakeView:
    """Minimal TopologyView: r root with children a, b; b has child c."""

    PARENTS = {"r": None, "a": "r", "b": "r", "c": "b"}
    CHILDREN = {"r": ["a", "b"], "b": ["c"]}

    def agent_parent_id(self, agent_id: str) -> str | None:
        return self.PARENTS.get(agent_id)

    def agent_children_ids(self, agent_id: str) -> list[str]:
        return list(self.CHILDREN.get(agent_id, []))

    def agent_role(self, agent_id: str) -> str | None:
        return None


def _ref(agent_id: str, parent_id: str | None = None) -> AgentRef:
    return AgentRef(agent_id=agent_id, parent_id=parent_id)


def _msg(sender: str, recipient: str, content: str = "hi"):
    from dynamic_harness.core.comms import CommsMessage

    return CommsMessage(
        id="x", topic="", sender_id=sender, recipients=[recipient], content=content,
    )


# -- factory / switching ----------------------------------------------------


def test_build_backend_off_returns_none():
    assert build_backend(CommsConfig(topology="off"), FakeView()) is None
    assert build_backend(CommsConfig(topology=""), FakeView()) is None


@pytest.mark.parametrize(
    ("topology", "cls"),
    [
        ("relay", RelayBackend),
        ("siblings", SiblingsBackend),
        ("shared", SharedBackend),
        ("topics", TopicsBackend),
    ],
)
def test_build_backend_constructs_cell(topology: str, cls):
    backend = build_backend(CommsConfig(topology=topology), FakeView())
    assert isinstance(backend, cls)
    assert isinstance(backend, CommsBackend)


def test_build_backend_unknown_topology_raises():
    with pytest.raises(ValueError):
        build_backend(CommsConfig(topology="bogus"), FakeView())


# -- cell 1: relay ----------------------------------------------------------


def test_relay_routes_sibling_message_to_common_parent():
    b = RelayBackend(FakeView(), None)
    verdict = b.route_message(_ref("a", "r"), _msg("a", "b"))
    assert verdict.allowed
    assert verdict.recipients == ["r"]  # parent in the middle of the edge


def test_relay_hierarchy_edges_stay_direct():
    b = RelayBackend(FakeView(), None)
    assert b.route_message(_ref("a", "r"), _msg("a", "r")).recipients == ["r"]
    assert b.route_message(_ref("r"), _msg("r", "a")).recipients == ["a"]


def test_relay_refuses_unrelated_agents():
    b = RelayBackend(FakeView(), None)
    verdict = b.route_message(_ref("c", "b"), _msg("c", "a"))
    assert not verdict.allowed


def test_relay_has_no_channels():
    b = RelayBackend(FakeView(), None)
    assert b.post(_ref("a", "r"), "x", "hi") is not None  # refusal


# -- cell 2: siblings -------------------------------------------------------


def test_siblings_allows_same_parent_peers():
    b = SiblingsBackend(FakeView(), None)
    verdict = b.route_message(_ref("a", "r"), _msg("a", "b"))
    assert verdict.allowed
    assert verdict.recipients == ["b"]


def test_siblings_refuses_unrelated_peers():
    b = SiblingsBackend(FakeView(), None)
    assert not b.route_message(_ref("c", "b"), _msg("c", "a")).allowed  # diff parents
    assert not b.route_message(_ref("a", "r"), _msg("a", "c")).allowed  # diff parents


def test_siblings_keeps_hierarchy_direct():
    b = SiblingsBackend(FakeView(), None)
    assert b.route_message(_ref("a", "r"), _msg("a", "r")).allowed
    assert b.route_message(_ref("r"), _msg("r", "c")).allowed  # grandparent still allowed


def test_siblings_has_no_channels():
    b = SiblingsBackend(FakeView(), None)
    assert b.post(_ref("a", "r"), "x", "hi") is not None
    assert b.channel_info("x") is None


# -- cell 3: shared ---------------------------------------------------------


def test_shared_posts_and_reads_delta_with_watermark():
    b = SharedBackend(FakeView(), None)
    a, c = _ref("a", "r"), _ref("c", "b")
    assert b.post(a, "whatever-name", "hello everyone") is None
    first = b.read(c, "anything")  # topic names collapse to the shared channel
    assert [m.content for m in first.messages] == ["hello everyone"]
    assert b.read(c, "anything").messages == []  # watermark advanced


def test_shared_subscription_is_universal_noop():
    b = SharedBackend(FakeView(), None)
    assert b.subscribe(_ref("c", "b"), "anything") is None
    assert b.unsubscribe(_ref("c", "b"), "anything") is None


def test_shared_refuses_peer_by_id():
    b = SharedBackend(FakeView(), None)
    assert not b.route_message(_ref("a", "r"), _msg("a", "b")).allowed
    assert b.route_message(_ref("r"), _msg("r", "a")).allowed  # hierarchy ok


# -- cell 4: topics ---------------------------------------------------------


def test_topics_creation_parent_authorized():
    b = TopicsBackend(FakeView(), ChannelPolicy(registration="parent", allowed_topics=["findings"]))
    assert b.post(_ref("a", "r"), "unapproved", "x") is not None  # child, not pre-declared
    assert b.post(_ref("a", "r"), "findings", "x") is None  # pre-declared by parent
    assert b.post(_ref("r"), "new-one", "x") is None  # root may create


def test_topics_anarchic_creation():
    b = TopicsBackend(FakeView(), ChannelPolicy(registration="anarchic"))
    assert b.post(_ref("c", "b"), "anything", "x") is None


def test_topics_join_and_watermarked_read():
    b = TopicsBackend(FakeView(), ChannelPolicy(registration="anarchic"))
    owner, reader = _ref("a", "r"), _ref("c", "b")
    b.post(owner, "x", "one")
    b.post(owner, "x", "two")
    # Pull is open: read works on an existing topic whether or not subscribed.
    out = b.read(reader, "x")
    assert out.refusal is None
    assert [m.content for m in out.messages] == ["one", "two"]
    assert b.read(reader, "x").messages == []  # watermark advanced
    b.post(owner, "x", "three")
    assert [m.content for m in b.read(reader, "x").messages] == ["three"]


def test_topics_channels_listing_and_info():
    b = TopicsBackend(FakeView(), ChannelPolicy(registration="anarchic"))
    b.post(_ref("a", "r"), "x", "hi")
    listing = b.channels(_ref("c", "b"))
    assert any(entry["topic"] == "x" for entry in listing)
    info = b.channel_info("x")
    assert info["owner"] == "a"
    assert b.subscriptions("a") == ["x"]


def test_topics_peer_by_id_refused():
    b = TopicsBackend(FakeView(), ChannelPolicy(registration="anarchic"))
    assert not b.route_message(_ref("a", "r"), _msg("a", "b")).allowed


# -- tool integration (real Runtime + ToolContext) --------------------------

TOPICS_CFG = HarnessConfig(
    communication=CommsConfig(topology="topics", registration="parent", channels=["findings"])
)
SIBLINGS_CFG = HarnessConfig(communication=CommsConfig(topology="siblings"))


def _runtime(tmp: Path, cfg: HarnessConfig) -> Runtime:
    rt = Runtime(
        artifact_root=tmp / "artifacts",
        repo_root=tmp / "repo",
        generated_root=tmp / "gen",
        config=cfg,
    )
    return rt


def _tree(rt: Runtime):
    root = rt.delegate(Task(description="root"))
    a = rt.delegate(Task(description="a"), parent=root)
    b = rt.delegate(Task(description="b"), parent=root)
    c = rt.delegate(Task(description="c"), parent=root)
    return root, a, b, c


def test_tools_disabled_by_default(tmp: Path):
    rt = _runtime(tmp, HarnessConfig())
    assert rt.comms is None
    root, *_ = _tree(rt)
    ctx = ToolContext(root)
    assert asyncio.run(comms_tools.post(ctx=ctx, topic="x", content="y")) == (
        "Communication is disabled (communication.topology is 'off'). "
        "Use converse() for direct by-ID messaging; no channel tools exist."
    )


@pytest.mark.asyncio
async def test_topic_tools_end_to_end(tmp: Path):
    rt = _runtime(tmp, TOPICS_CFG)
    root, a, b, c = _tree(rt)
    ctx_a, ctx_b = ToolContext(a), ToolContext(b)

    # Child posts to a pre-declared channel; subscriber reads the delta.
    out = await comms_tools.post(ctx=ctx_a, topic="findings", content="parser bug in line 12", kind="notification")
    assert "Posted" in out and "parser bug" in out

    await comms_tools.subscribe(ctx=ctx_b, topic="findings")
    read = await comms_tools.channel_read(ctx=ctx_b, topic="findings")
    assert "parser bug in line 12" in read
    # Watermark: second read sees nothing new.
    read2 = await comms_tools.channel_read(ctx=ctx_b, topic="findings")
    assert "no new messages" in read2

    # Owner sees its own post; listing shows subscription state.
    channels = await comms_tools.channels(ctx=ctx_a)
    assert "findings" in channels
    info = await comms_tools.channel_info(ctx=ctx_b, topic="findings")
    assert '"owner": "a"' in info or f'"owner": "{a.id}"' in info


@pytest.mark.asyncio
async def test_child_cannot_create_unapproved_topic(tmp: Path):
    rt = _runtime(tmp, TOPICS_CFG)
    root, a, b, c = _tree(rt)
    out = await comms_tools.post(ctx=ToolContext(a), topic="unapproved", content="nope")
    assert "Refused" in out or "cannot create" in out


@pytest.mark.asyncio
async def test_message_routing_follows_topology(tmp: Path):
    rt = _runtime(tmp, SIBLINGS_CFG)
    root, a, b, c = _tree(rt)
    ctx_c = ToolContext(c)
    # c is NOT a sibling of a (different parents: c has no parent here since all
    # children of root) — wait, all four are root's children in _tree.
    # a and b are same-parent siblings: message routes directly.
    out = await comms_tools.message(ctx=ToolContext(a), agent_id=b.id, content="hi b")
    assert b.id[:8] in out and "routed" in out


@pytest.mark.asyncio
async def test_message_refused_across_unrelated_subtrees(tmp: Path):
    rt = _runtime(tmp, SIBLINGS_CFG)
    root = rt.delegate(Task(description="root"))
    a = rt.delegate(Task(description="a"), parent=root)
    inner = rt.delegate(Task(description="inner"), parent=a)  # unrelated to root's other children
    other = rt.delegate(Task(description="other"), parent=root)
    out = await comms_tools.message(ctx=ToolContext(inner), agent_id=other.id, content="hi")
    assert "Error" in out and "sibling" in out


@pytest.mark.asyncio
async def test_converse_refusal_surface_when_comms_on(tmp: Path):
    rt = _runtime(tmp, TOPICS_CFG)
    root, a, b, c = _tree(rt)
    # Peer converse in a topics topology is refused without touching the target.
    out = await converse(ctx=ToolContext(a), agent_id=b.id, message="hi")
    assert out.startswith("Error:") and "peer" in out


# -- audit trail (comms.jsonl) ----------------------------------------------


def _log_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def test_comms_log_records_channel_lifecycle(tmp: Path):
    path = tmp / "comms.jsonl"
    b = TopicsBackend(FakeView(), ChannelPolicy(registration="anarchic"), log=CommsLog(path))
    a, c = _ref("a", "r"), _ref("c", "b")
    b.post(a, "findings", "parser bug in line 12", kind="notification")
    b.subscribe(c, "findings")
    out = b.read(c, "findings")
    assert out.refusal is None and len(out.messages) == 1

    lines = _log_lines(path)
    assert [l["type"] for l in lines] == ["post", "subscribe", "read"]
    post = lines[0]
    assert post["topic"] == "findings" and post["sender"] == "a"
    assert post["seq"] == 1 and post["kind"] == "notification"
    assert post["created"] is True and "parser bug" in post["headline"]
    assert lines[1]["agent"] == "c" and lines[1]["created"] is False
    read = lines[2]
    assert read["agent"] == "c" and read["count"] == 1
    assert read["from_seq"] == 0 and read["to_seq"] == 1
    # Second read records an empty delta with the advanced watermark.
    b.read(c, "findings")
    assert _log_lines(path)[-1]["count"] == 0 and _log_lines(path)[-1]["from_seq"] == 1


def test_comms_log_records_route_verdicts_and_deliveries(tmp: Path):
    path = tmp / "comms.jsonl"
    b = SiblingsBackend(FakeView(), None, log=CommsLog(path))
    verdict = b.route_message(_ref("a", "r"), _msg("a", "b"))
    assert verdict.allowed
    b.log_delivery(_msg("a", "b", "hi b"), verdict.recipients, mode="queued")

    refused = b.route_message(_ref("c", "b"), _msg("c", "a"))
    assert not refused.allowed

    allowed_line, deliver, refused_line = _log_lines(path)
    assert allowed_line["type"] == "route" and allowed_line["allowed"] is True
    assert allowed_line["requested"] == ["b"] and allowed_line["effective"] == ["b"]
    assert refused_line["allowed"] is False and refused_line["refusal"]
    assert deliver["type"] == "deliver" and deliver["mode"] == "queued"
    assert deliver["to"] == ["b"]


def test_comms_log_relay_records_rewritten_recipients(tmp: Path):
    path = tmp / "comms.jsonl"
    b = RelayBackend(FakeView(), None, log=CommsLog(path))
    verdict = b.route_message(_ref("a", "r"), _msg("a", "b"))
    assert verdict.allowed and verdict.recipients == ["r"]
    line = _log_lines(path)[0]
    assert line["requested"] == ["b"] and line["effective"] == ["r"]


def test_comms_log_refusals_when_channels_disabled(tmp: Path):
    path = tmp / "comms.jsonl"
    b = SiblingsBackend(FakeView(), None, log=CommsLog(path))
    b.post(_ref("a", "r"), "x", "hi")
    b.read(_ref("a", "r"), "x")
    lines = _log_lines(path)
    assert lines[0]["type"] == "post" and lines[0]["refusal"]
    assert lines[1]["type"] == "read" and lines[1]["refusal"]


def test_runtime_wires_comms_log(tmp: Path):
    rt = Runtime(
        artifact_root=tmp / "artifacts",
        repo_root=tmp / "repo",
        trace_root=tmp / "traces",
        config=TOPICS_CFG,
    )
    log_path = tmp / "traces" / "comms.jsonl"
    assert rt.comms is not None
    root, a, b, c = _tree(rt)
    asyncio.run(comms_tools.post(ctx=ToolContext(a), topic="findings", content="hi"))
    assert any(
        l["type"] == "post" and l["topic"] == "findings" for l in _log_lines(log_path)
    )
    # reset() wipes the channel store + trace root (fresh-run semantics); the
    # same CommsLog object keeps writing to the path going forward.
    rt.reset()
    assert rt.comms is not None
    assert not log_path.exists()  # wiped with the trace root
    root, a, b, c = _tree(rt)
    asyncio.run(comms_tools.post(ctx=ToolContext(a), topic="findings", content="hi again"))
    assert any(
        l["type"] == "post" and l["topic"] == "findings" for l in _log_lines(log_path)
    )


def test_runtime_comms_log_disabled_by_config(tmp: Path):
    cfg = HarnessConfig(
        communication=CommsConfig(
            topology="topics", registration="parent", channels=["findings"], trace=False
        )
    )
    rt = Runtime(
        artifact_root=tmp / "artifacts",
        repo_root=tmp / "repo",
        trace_root=tmp / "traces",
        config=cfg,
    )
    log_path = tmp / "traces" / "comms.jsonl"
    assert not log_path.exists()
    root, a, b, c = _tree(rt)
    asyncio.run(comms_tools.post(ctx=ToolContext(a), topic="findings", content="hi"))
    assert not log_path.exists()


# -- P2: push-digest policy -------------------------------------------------


def _obs(agent_id: str, iteration: int = 1) -> Observation:
    return Observation(
        iteration=iteration, max_iterations=400, has_delegated=False, agent_id=agent_id
    )


def _msg_created(id_: str, content: str, seq: int):
    from datetime import datetime, timedelta, timezone

    from dynamic_harness.core.comms import CommsMessage

    return CommsMessage(
        id=id_, topic="t", sender_id="s", content=content, seq=seq,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        + timedelta(seconds=seq),
    )


def test_render_digest_caps_items_newest_first():
    msgs = [_msg_created(f"m{i}", f"msg{i}", i) for i in range(1, 7)]
    body = render_digest(msgs, max_items=2, max_tokens=100000)
    assert "msg6" in body and "msg5" in body
    assert "msg4" not in body


def test_render_digest_token_cap():
    # Tiny budget (5 tokens ≈ 20 chars): only the newest envelope fits.
    msgs = [_msg_created("a", "message one", 1), _msg_created("b", "message two", 2)]
    body = render_digest(msgs, max_items=5, max_tokens=5)
    assert "message two" in body  # newest kept
    assert "message one" not in body  # oldest dropped by budget


def test_digest_policy_injects_subscribed_delta_once():
    backend = TopicsBackend(FakeView(), ChannelPolicy(registration="anarchic"))
    pol = CommsDigestPolicy(backend)
    backend.subscribe(_ref("b", "r"), "t")
    backend.post(_ref("a", "r"), "t", "hello world")
    inj = pol.evaluate(_obs("b"))
    assert inj is not None and "comms digest" in inj.message and "hello world" in inj.message
    # Watermark advanced by the read: second evaluate is a no-op.
    assert pol.evaluate(_obs("b")) is None


def test_digest_policy_only_subscribed_topics():
    backend = TopicsBackend(FakeView(), ChannelPolicy(registration="anarchic"))
    pol = CommsDigestPolicy(backend)
    backend.post(_ref("a", "r"), "notmine", "secret")  # b never subscribed
    assert pol.evaluate(_obs("b")) is None


def test_digest_policy_caps_items():
    backend = TopicsBackend(FakeView(), ChannelPolicy(registration="anarchic"))
    pol = CommsDigestPolicy(backend, max_items=2, max_tokens=100000)
    backend.subscribe(_ref("b", "r"), "t")
    for i in range(1, 5):
        backend.post(_ref("a", "r"), "t", f"msg{i}")
    inj = pol.evaluate(_obs("b"))
    assert inj is not None
    assert "msg4" in inj.message and "msg3" in inj.message
    assert "msg2" not in inj.message


def test_digest_policy_noop_when_no_channels():
    assert CommsDigestPolicy(None).evaluate(_obs("a")) is None
    assert (
        CommsDigestPolicy(SiblingsBackend(FakeView(), None)).evaluate(_obs("a"))
        is None
    )


def test_push_digest_wired_per_agent(tmp: Path):
    cfg = HarnessConfig(
        communication=CommsConfig(
            topology="topics", registration="anarchic", digest_mode="push",
            digest_max_items=3, digest_max_tokens=200,
        )
    )
    rt = _runtime(tmp, cfg)
    root = rt.delegate(Task(description="root"))
    assert "comms_digest" in root.reactive_policies.names()
    pol = root.reactive_policies.get("comms_digest")
    assert pol.max_items == 3 and pol.max_tokens == 200


def test_pull_default_has_no_digest_policy(tmp: Path):
    rt = _runtime(tmp, TOPICS_CFG)
    root = rt.delegate(Task(description="root"))
    assert "comms_digest" not in root.reactive_policies.names()