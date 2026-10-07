"""P4 — the live vision probe: code-image asset + task verifier.

Verifies the probe is real and reproducible before any real-LLM run:

- the rendered PNG decodes back to the exact code (pure-Python render →
  decoder roundtrip, including a leading zero);
- the verifier recomputes ground truth from the workspace image pixels —
  a matching code.txt passes, wrong/missing digits fail, and truth cannot
  be verified without the image;
- with a deterministic (stub) LLM the probe is deterministic: the stub
  never sees the image, so it is mechanically wrong, and two replicates
  produce identical metrics — the harness adds no noise.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dynamic_harness.benchmark.comms import runtime_factory_for
from dynamic_harness.benchmark.metrics import MetricsCollector
from dynamic_harness.benchmark.runner import run_one
from dynamic_harness.benchmark.tasks import VisionCodeTask
from dynamic_harness.benchmark.vision_asset import decode_code_image, render_code_image
from dynamic_harness.llm.provider import LLMConfig, LLMProvider, LLMResponse, ToolCallResponse


class _FixedLLM(LLMProvider):
    """Deterministic stub: always answers with plain text (no tool calls)."""

    default_model = "stub"

    async def generate(self, system, user, config: LLMConfig | None = None) -> LLMResponse:
        return LLMResponse(content="Deterministic outcome.", model="stub")

    async def generate_with_tools(
        self, messages, tools, config: LLMConfig | None = None
    ) -> ToolCallResponse:
        return ToolCallResponse(content="Deterministic outcome.", model="stub")

    async def generate_structured(self, system, user, response_model, config=None):
        return None


def _workspace(code: str) -> tuple[Path, Path]:
    """Staged scan root: resources/_vision/code.png + .optimize_benchmarks.

    Returns ``(workspace, output_dir)``.
    """
    ws = Path(tempfile.mkdtemp(prefix="vision_ws_"))
    png = ws / "resources" / "_vision" / "code.png"
    png.parent.mkdir(parents=True)
    render_code_image(png, code)
    out = ws / ".optimize_benchmarks"
    out.mkdir()
    return ws, out


# -- asset roundtrip ---------------------------------------------------------


@pytest.mark.parametrize("code", ["0000", "7391", "9021", "0123"])
def test_render_decode_roundtrip(code, tmp_path):
    png = tmp_path / "code.png"
    render_code_image(png, code)
    assert png.stat().st_size < 5 * 1024 * 1024  # under the read tool's image cap
    assert decode_code_image(png) == code


def test_render_rejects_bad_code(tmp_path):
    with pytest.raises(ValueError):
        render_code_image(tmp_path / "code.png", "12")


def test_decode_rejects_non_png(tmp_path):
    f = tmp_path / "code.png"
    f.write_text("definitely not a png")
    with pytest.raises(ValueError):
        decode_code_image(f)


# -- verifier ----------------------------------------------------------------


def test_verifier_accepts_matching_digits():
    ws, out = _workspace("7391")
    (out / "code.txt").write_text("7391\n")
    ok, note = VisionCodeTask().verify(out, ws)
    assert ok, note
    assert "7391" in note


def test_verifier_rejects_wrong_digits():
    ws, out = _workspace("7391")
    (out / "code.txt").write_text("1234\n")
    ok, note = VisionCodeTask().verify(out, ws)
    assert not ok
    assert "mismatch" in note


def test_verifier_rejects_missing_report():
    ws, out = _workspace("7391")
    ok, note = VisionCodeTask().verify(out, ws)
    assert not ok and "code.txt missing" in note


def test_verifier_rejects_missing_image():
    # Truth comes from the pixels: without the image there is nothing to
    # verify against, even with a plausible report on disk.
    ws = Path(tempfile.mkdtemp(prefix="vision_ws_"))
    out = ws / ".optimize_benchmarks"
    out.mkdir()
    (out / "code.txt").write_text("7391\n")
    ok, note = VisionCodeTask().verify(out, ws)
    assert not ok and "missing from workspace" in note


# -- determinism -------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_deterministic_with_stub_llm():
    ws, out = _workspace("7391")
    collector = MetricsCollector()
    factory = runtime_factory_for("off", llm=_FixedLLM())
    outcomes = [
        await run_one(
            runtime_factory=factory,
            task=VisionCodeTask(),
            prompt_id=f"vision#rep{rep}",
            collector=collector,
            workspace=ws,
        )
        for rep in range(2)
    ]
    m1, m2 = (o.metrics for o in outcomes)
    # Every deterministic field is identical across replicates.
    for field in (
        "status", "correct", "verification_note", "total_tokens",
        "agent_count", "delegations", "total_turns", "message_count",
        "failures", "escalations",
    ):
        assert getattr(m1, field) == getattr(m2, field), field
    # The stub never reads the image: mechanically wrong, deterministically so.
    assert m1.correct is False and m1.status == "completed"
