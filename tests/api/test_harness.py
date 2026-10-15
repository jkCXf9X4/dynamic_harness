"""Regression tests for the ``Harness`` programmatic API wrapper."""

from __future__ import annotations

import pytest

from dynamic_harness import Harness
from dynamic_harness.core.task import Task
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse
from dynamic_harness.llm.registry import ProviderCredentialError

LLM_CONFIG: dict = {
    "model": "prov/model",
    "providers": {
        "prov": {
            "name": "P",
            "env": ["UNSET_KEY"],
            "base_url": "https://example.invalid/v1",
            "models": {"model": {"name": "M"}},
        }
    },
}


def test_harness_llm_config_no_nameerror(tmp_path) -> None:
    """BUG #1 regression: ``Harness(llm_config=...)`` raised ``NameError``
    (missing ``HarnessConfig`` import) before config validation even ran.
    Keyless construction now fails with the credential gate instead —
    see test_harness_llm_config_constructs_with_credential."""
    with pytest.raises(ProviderCredentialError) as excinfo:
        Harness(
            artifact_root=str(tmp_path / "artifacts"),
            repo_root=str(tmp_path / "repo"),
            llm_config=LLM_CONFIG,
        )
    assert "UNSET_KEY" in str(excinfo.value)


def test_harness_llm_config_constructs_with_credential(tmp_path, monkeypatch) -> None:
    """With a credential in the environment, the documented convenience
    path validates the v2 config shape and constructs fully."""
    monkeypatch.setenv("UNSET_KEY", "test-key")
    harness = Harness(
        artifact_root=str(tmp_path / "artifacts"),
        repo_root=str(tmp_path / "repo"),
        llm_config=LLM_CONFIG,
    )
    assert harness.runtime.provider_registry is not None


class _PushLLM(LLMProvider):
    """One request_input tool-call, then a report carrying the answer.

    Records the messages it sees so a test can assert what the agent was
    actually told (the channel round-trip, not this mock's own echo).
    """

    def __init__(self) -> None:
        self.turn = 0
        self.seen: list[list[dict]] = []

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.seen.append(list(messages))
        self.turn += 1
        if self.turn == 1:
            return ToolCallResponse(
                tool_calls=[ToolCallData(
                    id="c1", name="request_input",
                    arguments={"question": "what color?"},
                )],
                content=None, model="mock",
            )
        return ToolCallResponse(
            tool_calls=None, content="done: the pushed answer", model="mock",
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


# -- IMP-006 push-answer regressions (trial findings BUG #3) ------------------


def test_on_input_request_sync_push_answer_round_trip(tmp_path) -> None:
    """BUG #3a+#3b regression: the documented ``Harness.on_input_request``
    pattern — a synchronous handler answering via ``answer_input`` inside the
    event — must reach the agent: the tool call resolves to THAT answer, not
    the policy default.

    Pre-fix this failed twice over: the runtime registered the request only
    after the event fired (``answer_input`` -> False, answer dropped), and the
    Harness seam listened on the activity stream instead of the dedicated
    ``input_request`` channel, so the request settled instantly per policy.
    """
    harness = Harness(
        artifact_root=str(tmp_path / "artifacts"),
        repo_root=str(tmp_path / "repo"),
        llm=_PushLLM(),
    )
    harness.on_input_request(lambda aid, req: harness.answer_input(req["id"], "the pushed answer"))

    harness.run("ask")

    assert harness.last_reports, "root agent never reported"
    assert "done: the pushed answer" in harness.last_reports[0][1]
    # The agent must have been told the pushed answer, not the policy's
    # empty settle answer (no default on the request). The mock never writes
    # a deliverable, so the run ends in the heal loop — check every turn's
    # messages, not just the last worker's first turn.
    all_msgs = [m for turn in harness.runtime._llm.seen for m in turn]
    tool_msgs = [m for m in all_msgs if m.get("role") == "tool"]
    assert any("the pushed answer" in str(m.get("content", "")) for m in tool_msgs)


def test_on_input_answer_receives_answer_payload(tmp_path) -> None:
    """``on_input_answer`` fires on the dedicated channel with the answer
    payload as a dict (the documented ``(agent_id, answer_dict)`` shape)."""
    harness = Harness(
        artifact_root=str(tmp_path / "artifacts"),
        repo_root=str(tmp_path / "repo"),
        llm=_PushLLM(),
    )
    seen: list[tuple[str, dict]] = []
    harness.on_input_request(lambda aid, req: harness.answer_input(req["id"], "the pushed answer"))
    harness.on_input_answer(lambda aid, ans: seen.append((aid, ans)))

    harness.run("ask")

    assert len(seen) == 1
    assert seen[0][1].get("value") == "the pushed answer"
    assert seen[0][1].get("assumed") is False
