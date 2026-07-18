from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runner import AgentRunner
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


@pytest.fixture
def runtime() -> Runtime:
    tmp = Path(tempfile.mkdtemp())
    return Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo")


# ---------------------------------------------------------------------------
# Agent classes simulating real sub-agent behaviour
# ---------------------------------------------------------------------------

class SecurityAuditAgent(Agent):
    """Security auditor that writes findings to disk and reports with rich views."""

    async def run(self) -> None:
        self.report(ReportPayload(
            task_id=self.task.id,
            summary="JWT validation audit complete.\nFound 2 issues: expired-token bypass, missing signature check.",
            technical_summary=(
                "Bug #1 (HIGH): Expired token bypass in auth/token.py:45. "
                "The `iat` field is compared using local timezone instead of UTC, "
                "allowing tokens up to 24h past expiry. "
                "Bug #2 (CRITICAL): Signature verification missing in auth/jwt.py:112. "
                "The `verify=False` flag is hardcoded for all development environments."
            ),
            full_report=(
                "Comprehensive JWT Security Audit Report\n"
                "=======================================\n\n"
                "Files audited:\n"
                "  - src/auth/token.py (142 lines)\n"
                "  - src/auth/jwt.py (389 lines)\n"
                "  - src/auth/middleware.py (67 lines)\n\n"
                "Issue 1: Expired Token Bypass\n"
                "  Severity: HIGH\n"
                "  Location: auth/token.py:45\n"
                "  Details: The `iat` claim comparison uses datetime.now() "
                "instead of datetime.utcnow(), creating a timezone-dependent "
                "window where expired tokens remain valid.\n\n"
                "Issue 2: Missing Signature Verification\n"
                "  Severity: CRITICAL\n"
                "  Location: auth/jwt.py:112\n"
                "  Details: jwt.decode() is called with verify=False in all "
                "environments. The flag should only be disabled in dev.\n\n"
                "Recommendations:\n"
                "  1. Replace datetime.now() with datetime.utcnow() in token.py:45\n"
                "  2. Gate verify=False behind an environment check in jwt.py:112\n"
                "  3. Add integration tests for both scenarios"
            ),
            artifact_ids=["/tmp/jwt_audit_report.txt"],
            confidence=0.95,
        ))


class PasswordAuditAgent(Agent):
    """Password hashing auditor."""

    async def run(self) -> None:
        self.report(ReportPayload(
            task_id=self.task.id,
            summary="Password hashing audit complete.\nUses bcrypt correctly but work factor is low.",
            technical_summary=(
                "Finding (MEDIUM): bcrypt work factor is set to 8 in auth/hash.py:23. "
                "OWASP recommends minimum work factor 12 as of 2023. "
                "Increasing to 12 would add ~60ms to auth latency per request."
            ),
            full_report=(
                "Password Hashing Audit\n"
                "======================\n\n"
                "Library: bcrypt 4.0.1\n"
                "Work factor: 8 (LOW)\n"
                "Recommendation: Increase to 12\n"
                "Impact: +60ms per auth request\n"
                "Migration path: Rehash on next login"
            ),
            artifact_ids=["/tmp/password_audit.txt"],
            confidence=0.9,
        ))


class SynthesisAgent(Agent):
    """Synthesizes child findings into a final report."""

    async def run(self) -> None:
        children = [
            self.delegate("Audit JWT token validation", agent_type="SecurityAuditor"),
            self.delegate("Audit password hashing", agent_type="PasswordAuditor"),
        ]
        for child in children:
            await child.run()

        child_reports: list[str] = []
        for child in children:
            commits = self._runtime.repository.log()
            for c in commits:
                if c.agent_id == child.id:
                    child_reports.append(f"{c.agent_id[:8]}: {c.summary[:100]}")
                    break

        combined = "Security audit complete with " + str(len(child_reports)) + " findings from sub-agents."
        self.report(ReportPayload(
            task_id=self.task.id,
            summary=combined,
            technical_summary=(
                "Aggregated audit findings across 2 security domains:\n"
                + "\n".join(f"  - {r}" for r in child_reports)
            ),
            full_report=(
                "=== Security Audit Synthesis Report ===\n\n"
                "Two sub-audits completed covering JWT validation "
                "and password hashing. The JWT audit found a critical "
                "signature verification bypass and a high-severity "
                "expired-token issue. The password audit found a medium-"
                "severity weak work factor. All findings include file "
                "paths, line numbers, severity ratings, and remediation "
                "steps. Overall confidence is high.\n\n"
                + "Sub-agent findings:\n"
                + "\n".join(f"  [{r}]" for r in child_reports)
            ),
            confidence=0.92,
        ))


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_multi_agent_rich_artifact_views(runtime: Runtime) -> None:
    """Full multi-agent workflow: security audit → sub-agents → synthesis.

    Verifies every ArtifactView level is populated and recoverable from disk."""
    runtime.register_agent_class("SecurityAuditor", SecurityAuditAgent)
    runtime.register_agent_class("PasswordAuditor", PasswordAuditAgent)
    runtime.register_agent_class("SynthesisAgent", SynthesisAgent)

    root = runtime.delegate(
        Task(description="Security audit of auth module"),
        agent_type="SynthesisAgent",
    )
    await root.run()

    assert root.task.status.value == "completed"
    assert root._last_report is not None
    assert root._last_report.confidence == 0.92

    commits = runtime.repository.log()
    assert len(commits) >= 3

    all_artifacts: list = []
    for c in commits:
        for aid in c.artifact_ids:
            art = runtime.artifact_store.get(aid)
            if art:
                all_artifacts.append(art)

    assert len(all_artifacts) >= 3

    # Verify progressive disclosure levels are correctly differentiated
    for art in all_artifacts:
        if "JWT" in art.views.headline or "security" in art.views.headline.lower():
            assert art.views.headline != "", f"headline empty for {art.id}"
            assert art.views.summary_200 != "", f"summary_200 empty for {art.id}"
        if art.views.technical and art.views.summary_200:
            # technical should be distinct from summary_200 (not just truncated)
            assert art.views.technical.strip() != art.views.summary_200.strip(), \
                f"technical should differ from summary_200 for {art.id}"

    # Cross-session recovery
    rt2 = Runtime(
        artifact_root=runtime.artifact_store.root,
        repo_root=runtime.repository.root,
    )
    commits2 = rt2.repository.log()
    assert len(commits2) == len(commits)

    for c in commits2:
        for aid in c.artifact_ids:
            art = rt2.artifact_store.get(aid)
            if art:
                assert art.views.headline != ""
                if art.views.technical:
                    assert art.views.technical != ""
                if art.views.full_report:
                    assert art.views.full_report != ""


@pytest.mark.asyncio
async def test_e2e_delegate_then_read_artifact(runtime: Runtime) -> None:
    """Parent delegates to child, then reads its artifact from the store."""
    runtime.register_agent_class("SecurityAuditor", SecurityAuditAgent)

    class ReaderAgent(Agent):
        async def run(self) -> None:
            child = self.delegate("Audit JWT", agent_type="SecurityAuditor")
            await child.run()

            commits = self._runtime.repository.log()
            child_art_id = None
            for c in commits:
                if c.agent_id == child.id:
                    child_art_id = next(
                        (aid for aid in c.artifact_ids
                         if self._runtime.artifact_store.get(aid)),
                        None,
                    )
                    break

            assert child_art_id is not None, "child artifact not found"
            art = self._runtime.artifact_store.get(child_art_id)
            assert art is not None
            assert art.views.headline != ""
            assert "JWT" in art.views.headline
            assert "expired" in art.views.technical.lower()
            assert "CRITICAL" in art.views.full_report

            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Verified child artifact via store",
                confidence=1.0,
            ))

    runtime.register_agent_class("ReaderAgent", ReaderAgent)
    root = runtime.delegate(
        Task(description="Verify artifact reading"),
        agent_type="ReaderAgent",
    )
    await root.run()
    assert root.task.status.value == "completed"


@pytest.mark.asyncio
async def test_e2e_summary_200_only_when_short(runtime: Runtime) -> None:
    """When a summary is short, summary_1000 stays empty (not duplicated)."""

    class ShortReporter(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="All tests pass.",
            ))

    runtime.register_agent_class("ShortReporter", ShortReporter)
    root = runtime.delegate(Task(description="Quick check"), agent_type="ShortReporter")
    await root.run()

    commits = runtime.repository.log()
    for c in commits:
        for aid in c.artifact_ids:
            art = runtime.artifact_store.get(aid)
            if art:
                assert art.views.headline == "All tests pass."
                assert art.views.summary_200 == "All tests pass."
                assert art.views.summary_1000 == "", \
                    "summary_1000 should be empty when summary fits in summary_200"


@pytest.mark.asyncio
async def test_e2e_summary_1000_populated_when_long(runtime: Runtime) -> None:
    """When a summary exceeds 200 chars, summary_1000 gets populated."""

    long_summary = (
        "This is a very long summary that exceeds the two hundred character "
        "threshold. It contains detailed information about multiple findings "
        "across the codebase, including specific file paths, line numbers, "
        "and remediation steps for each issue discovered during the audit."
    )

    class LongReporter(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary=long_summary,
            ))

    runtime.register_agent_class("LongReporter", LongReporter)
    root = runtime.delegate(Task(description="Detailed"), agent_type="LongReporter")
    await root.run()

    commits = runtime.repository.log()
    for c in commits:
        for aid in c.artifact_ids:
            art = runtime.artifact_store.get(aid)
            if art:
                assert art.views.summary_1000 != "", \
                    "summary_1000 should be populated for long summaries"
                assert art.views.summary_1000 == long_summary[:1000]


@pytest.mark.asyncio
async def test_e2e_headless_runner_with_rich_report(runtime: Runtime) -> None:
    """AgentRunner with rich reporting: all view levels captured."""

    class RichReporter(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Code review complete. Found 5 type errors and 3 null safety issues.",
                technical_summary=(
                    "Type errors:\n"
                    "  1. src/handler.py:23 - str assigned to int param\n"
                    "  2. src/parser.py:67 - Optional[str] not unwrapped\n"
                    "  3. src/cache.py:12 - dict key type mismatch\n"
                    "  4. src/worker.py:89 - Callback type erased\n"
                    "  5. src/api.py:34 - Any used as return type\n\n"
                    "Null safety:\n"
                    "  1. src/handler.py:45 - nullable field accessed without guard\n"
                    "  2. src/parser.py:120 - Optional[str] concatenated\n"
                    "  3. src/cache.py:78 - dict.get() result used without None check"
                ),
                full_report=(
                    "=== Full Code Review Report ===\n\n"
                    "Scope: src/ directory (847 lines across 12 files)\n\n"
                    "TYPE ERRORS (5 found):\n\n"
                    "1. src/handler.py:23 - str assigned to int param `port`\n"
                    "   The port parameter is typed as int but receives a string from env.\n"
                    "   Fix: wrap in int() with validation.\n\n"
                    "2. src/parser.py:67 - Optional[str] not unwrapped\n"
                    "   config.get('key') returns Optional[str]; it's passed directly to\n"
                    "   a function expecting str. Fix: add None guard.\n\n"
                    "3. src/cache.py:12 - dict key type mismatch\n"
                    "   Cache dict typed as Dict[str, int] but keys are Path objects.\n"
                    "   Fix: use str(path) as key.\n\n"
                    "4. src/worker.py:89 - Callback type erased\n"
                    "   Callable typed as Callable[..., Any] loses parameter info.\n"
                    "   Fix: use ParamSpec or specific signature.\n\n"
                    "5. src/api.py:34 - Any used as return type\n"
                    "   get_response() returns Any; should be a TypedDict or model.\n"
                    "   Fix: define response model class.\n\n"
                    "NULL SAFETY (3 found):\n\n"
                    "1. src/handler.py:45 - nullable field accessed without guard\n"
                    "2. src/parser.py:120 - Optional[str] concatenated\n"
                    "3. src/cache.py:78 - dict.get() result used without None check\n\n"
                    "RECOMMENDATIONS:\n"
                    "- Enable mypy strict mode\n"
                    "- Add pre-commit hook for type checking\n"
                    "- Add pyright in CI pipeline"
                ),
                artifact_ids=["/tmp/code_review_report.md"],
                confidence=0.88,
            ))

    runtime.register_agent_class("RichReporter", RichReporter)

    runner = AgentRunner(runtime)
    runner.runtime.register_agent_class("RichReporter", RichReporter)

    task = Task(description="Review codebase for type safety and null safety")
    root = runtime.delegate(task, agent_type="RichReporter")
    await root.run()

    assert root.task.status.value == "completed"
    assert root._last_report is not None
    assert root._last_report.confidence == 0.88

    commits = runtime.repository.log()
    assert len(commits) >= 1

    for c in commits:
        for aid in c.artifact_ids:
            art = runtime.artifact_store.get(aid)
            if art:
                views = art.views
                assert views.headline != ""
                assert views.summary_200 != ""
                # summary_1000 is empty only because the summary is <200 chars
                if len(views.summary_200) > 200:
                    assert views.summary_1000 != ""
                assert "str assigned to int" in views.technical
                assert "Full Code Review Report" in views.full_report

                # Verify progressive sizing
                assert len(views.summary_200) <= 200
                assert len(views.full_report) > len(views.technical)


@pytest.mark.asyncio
async def test_e2e_cross_session_recovery_all_levels(runtime: Runtime) -> None:
    """Save artifacts with all levels, destroy runtime, recover everything."""

    class FullReporter(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Full audit complete.\nThree vulnerabilities found and documented.",
                technical_summary="Vuln #1: SQL injection in query builder. Vuln #2: XSS in template renderer. Vuln #3: Path traversal in file handler.",
                full_report="Complete security audit with detailed reproduction steps, CVSS scores, and remediation guidance for all three vulnerabilities.",
                confidence=0.93,
            ))

    runtime.register_agent_class("FullReporter", FullReporter)
    await runtime.delegate(
        Task(description="Full security audit"),
        agent_type="FullReporter",
    ).run()

    commits = runtime.repository.log()
    saved_artifacts: dict[str, Path] = {}
    for c in commits:
        for aid in c.artifact_ids:
            art = runtime.artifact_store.get(aid)
            if art and art.path:
                saved_artifacts[aid] = art.path

    assert len(saved_artifacts) >= 1

    for aid, path in saved_artifacts.items():
        assert (path / "artifact.json").exists()

    rt2 = Runtime(
        artifact_root=runtime.artifact_store.root,
        repo_root=runtime.repository.root,
    )

    for aid in saved_artifacts:
        art = rt2.artifact_store.get(aid)
        assert art is not None, f"artifact {aid} not recovered"
        v = art.views
        assert v.headline != ""
        assert v.summary_200 != ""
        assert v.technical != ""
        assert v.full_report != ""
        assert "SQL injection" in v.technical
        assert "CVSS" in v.full_report


# ---------------------------------------------------------------------------
# -m flag integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_m_flag_integration(runtime: Runtime) -> None:
    """Simulate the -m flag path: read a prompt file, run AgentRunner with it."""
    prompt_file = Path(__file__).parent.parent / "prompts" / "security_audit.txt"
    assert prompt_file.exists(), "prompt file missing"

    prompt_text = prompt_file.read_text()
    assert len(prompt_text) > 10

    class PromptRunner(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Audit executed",
                technical_summary="Ran security_audit.txt prompt via -m simulation",
                full_report=f"Prompt processed: {self.task.description[:200]}",
                confidence=0.85,
            ))

    runtime.register_agent_class("PromptRunner", PromptRunner)
    runner = AgentRunner(runtime)
    runner.runtime.register_agent_class("PromptRunner", PromptRunner)

    task = Task(description=prompt_text)
    root = runtime.delegate(task, agent_type="PromptRunner")
    await root.run()

    assert root.task.status.value == "completed"
    assert root._last_report is not None
    assert "Audit executed" in root._last_report.summary


@pytest.mark.asyncio
async def test_e2e_m_flag_parses_prompt_file(runtime: Runtime) -> None:
    """Verify _parse_args correctly handles -m flag."""
    from dynamic_harness.cli.tui import _parse_args

    args = _parse_args(["-m", "prompts/file_inventory.txt"])
    assert args.m == "prompts/file_inventory.txt"


@pytest.mark.asyncio
async def test_e2e_m_flag_file_missing(runtime: Runtime) -> None:
    """Verify _parse_args handles -m with missing file gracefully."""
    from dynamic_harness.cli.tui import _parse_args

    args = _parse_args(["-m", "prompts/nonexistent.txt"])
    assert args.m == "prompts/nonexistent.txt"
    # The file path is captured by argparse; Path.read_text() fails later
    assert not Path(args.m).exists()


@pytest.mark.asyncio
async def test_e2e_m_flag_no_llm(runtime: Runtime) -> None:
    """Verify --no-llm flag is parsed correctly."""
    from dynamic_harness.cli.tui import _parse_args

    args = _parse_args(["-m", "prompts/file_inventory.txt", "--no-llm"])
    assert args.m == "prompts/file_inventory.txt"
    assert args.no_llm is True


@pytest.mark.asyncio
async def test_e2e_all_prompt_files_exist() -> None:
    """All preset prompt files are present and readable."""
    prompt_dir = Path(__file__).parent.parent / "prompts"
    assert prompt_dir.is_dir()

    for prompt_file in sorted(prompt_dir.glob("*.txt")):
        content = prompt_file.read_text()
        assert len(content) > 0, f"{prompt_file.name} is empty"
        assert len(content) > 20, f"{prompt_file.name} too short ({len(content)} chars)"
