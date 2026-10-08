"""Unit tests for ``AgentContext`` turn bookkeeping and the emergency
mechanical shrink (``prune_oldest_to``) the gateway-timeout retry path uses
when the provider's gateway kills a call for exceeding its total-time window.
"""

from __future__ import annotations

from dynamic_harness.core.context import AgentContext


def _context_with(turns: int, chars: int = 2000) -> AgentContext:
    ctx = AgentContext()
    ctx.reset("system prompt", "user task")
    for i in range(turns):
        ctx.commit_turn(
            {"role": "assistant", "content": f"step {i}"},
            [{"role": "tool", "tool_call_id": f"c{i}", "name": "bash", "content": "x" * chars}],
        )
    return ctx


class TestPruneOldestTo:
    def test_noop_when_already_under_budget(self) -> None:
        ctx = _context_with(6)
        assert ctx.prune_oldest_to(1_000_000) is None
        assert not ctx.pruned

    def test_noop_when_nothing_prunable(self) -> None:
        # keep_recent=3 (default) means fewer than 3 committed turns -> nothing
        # may be pruned (the working tail of the conversation is protected).
        ctx = _context_with(2)
        assert ctx.prune_oldest_to(1) is None
        assert not ctx.pruned

    def test_prunes_oldest_until_nothing_left_prunable(self) -> None:
        ctx = _context_with(6, chars=2000)
        before = ctx.estimate_prompt_tokens()
        result = ctx.prune_oldest_to(500)
        assert result is not None
        assert result["action"] is True
        # Oldest first; the newest three committed turns are protected.
        assert result["turns_pruned"] == ["t0", "t1", "t2"]
        assert ctx.estimate_prompt_tokens() < before
        # Pruned turns are replaced by markers in the live buffer.
        assert any("[PRUNED t0" in str(m.get("content", "")) for m in ctx.messages)
        assert not any("[PRUNED t3" in str(m.get("content", "")) for m in ctx.messages)

    def test_stops_early_once_under_budget(self) -> None:
        ctx = _context_with(10, chars=2000)
        result = ctx.prune_oldest_to(3500)
        assert result is not None
        # 10 turns ~ 530 tokens each (~5300 + system/user), 7 prunable
        # (keep_recent=3 protects t7..t9): pruning the four oldest lands the
        # estimate (~3180) under 3500, and the loop stops there instead of
        # chewing through the remaining prunable turns.
        assert result["turns_pruned"] == ["t0", "t1", "t2", "t3"]
        assert "t4" not in ctx.pruned

    def test_pruned_turns_stay_restorable(self) -> None:
        ctx = _context_with(6, chars=2000)
        before = ctx.estimate_prompt_tokens()
        result = ctx.prune_oldest_to(500)
        assert result is not None
        for pid in result["turns_pruned"]:
            ctx.restore(pid)
        assert not ctx.pruned
        assert ctx.estimate_prompt_tokens() >= before

    def test_zero_target_disables(self) -> None:
        ctx = _context_with(6)
        assert ctx.prune_oldest_to(0) is None
        assert ctx.prune_oldest_to(None) is None
