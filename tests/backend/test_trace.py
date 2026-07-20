from __future__ import annotations

import json
from pathlib import Path

import pytest

from dynamic_harness.core.trace import TraceStore


@pytest.fixture
def trace(tmp: Path) -> TraceStore:
    return TraceStore(tmp / "traces")


class TestTraceStore:
    def test_creates_root_dir(self, tmp: Path) -> None:
        root = tmp / "traces"
        ts = TraceStore(root)
        assert root.exists()
        assert root.is_dir()

    def test_record_llm_request_creates_file(self, trace: TraceStore) -> None:
        trace.record_llm_request("agent-1", [
            {"role": "system", "content": "You are a test agent."},
            {"role": "user", "content": "Hello"},
        ])

        trace_file = trace.root / "agent-1" / "trace.jsonl"
        assert trace_file.exists()

        lines = trace_file.read_text().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["type"] == "llm_request"
        assert len(entry["messages"]) == 2

    def test_record_llm_response(self, trace: TraceStore) -> None:
        trace.record_llm_response("agent-1", "Hello back", "test-model", {"total_tokens": 10})
        trace.record_llm_response(
            "agent-1", None, "test-model", None,
            tool_calls=[{"id": "tc1", "name": "read", "arguments": {"path": "/foo"}}],
        )

        trace_file = trace.root / "agent-1" / "trace.jsonl"
        lines = trace_file.read_text().splitlines()
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["type"] == "llm_response"
        assert first["content"] == "Hello back"
        assert first["model"] == "test-model"

        second = json.loads(lines[1])
        assert second["type"] == "llm_response"
        assert second["content"] is None
        assert len(second["tool_calls"]) == 1

    def test_record_tool_call_and_result(self, trace: TraceStore) -> None:
        trace.record_tool_call("agent-1", "tc1", "read", {"path": "/foo"})
        trace.record_tool_result("agent-1", "tc1", "read", "file contents here")

        trace_file = trace.root / "agent-1" / "trace.jsonl"
        lines = trace_file.read_text().splitlines()

        call_entry = json.loads(lines[0])
        assert call_entry["type"] == "tool_call"
        assert call_entry["tool_call_id"] == "tc1"
        assert call_entry["name"] == "read"
        assert call_entry["arguments"] == {"path": "/foo"}

        result_entry = json.loads(lines[1])
        assert result_entry["type"] == "tool_result"
        assert result_entry["tool_call_id"] == "tc1"
        assert result_entry["content_preview"] == "file contents here"
        assert result_entry["content_length"] == 18

    def test_record_event(self, trace: TraceStore) -> None:
        trace.record_event("agent-1", "iteration", turn=5)
        trace.record_event("agent-1", "safety_warning", reason="max_iterations")

        trace_file = trace.root / "agent-1" / "trace.jsonl"
        lines = trace_file.read_text().splitlines()
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["type"] == "event"
        assert first["event"] == "iteration"
        assert first["turn"] == 5

    def test_multiple_agents_separate_dirs(self, trace: TraceStore) -> None:
        trace.record_llm_request("agent-1", [{"role": "user", "content": "a"}])
        trace.record_llm_request("agent-2", [{"role": "user", "content": "b"}])

        assert (trace.root / "agent-1").is_dir()
        assert (trace.root / "agent-2").is_dir()
        assert (trace.root / "agent-1" / "trace.jsonl").exists()
        assert (trace.root / "agent-2" / "trace.jsonl").exists()

    def test_clear_removes_all_dirs(self, trace: TraceStore) -> None:
        trace.record_llm_request("agent-1", [{"role": "user", "content": "a"}])
        trace.record_llm_request("agent-2", [{"role": "user", "content": "b"}])

        assert trace.root.exists()
        trace.clear()

        assert trace.root.exists()
        assert not (trace.root / "agent-1").exists()
        assert not (trace.root / "agent-2").exists()

    def test_deduplication_truncates_repeated_prefix(self, trace: TraceStore) -> None:
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "Response"},
            {"role": "tool", "content": "tool output"},
        ]

        trace.record_llm_request("agent-1", messages)
        trace.record_llm_request("agent-1", messages)

        trace_file = trace.root / "agent-1" / "trace.jsonl"
        lines = trace_file.read_text().splitlines()
        assert len(lines) == 2

        second = json.loads(lines[1])
        assert second["type"] == "llm_request"
        assert "<same as trace-entry" in second["messages"][0]["content"]

    def test_long_content_preview_truncated(self, trace: TraceStore) -> None:
        long_content = "x" * 1000
        trace.record_tool_result("agent-1", "tc1", "read", long_content)

        trace_file = trace.root / "agent-1" / "trace.jsonl"
        entry = json.loads(trace_file.read_text().splitlines()[0])
        assert len(entry["content_preview"]) == 500
        assert entry["content_length"] == 1000