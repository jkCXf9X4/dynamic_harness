"""Self-heal policy as a composable policy object.

The blunt-vs-rot diagnosis, the shared per-child heal budget, the deliverable
gate, and the nudge/restart message wording were entangled in
``Runtime._recover`` / ``Agent``. They live here as pure decisions and pure
string builders so a plugin host (or a re-hosted runtime) can apply the same
recovery policy without importing an agent or runtime.

The *execution* (resuming an agent, spawning a fresh worker, deleleting
children) stays in the runtime; this module only decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..task import TaskStatus


class ResumePlanner:
    """Decision half of the parent-driven ``resume`` tool's recovery ladder.

    ``Agent.resume_child`` kept the strategy validation, rot refusal, layer
    ordering, and budget-exhausted wording inline. Those decisions live here so
    a plugin host (or a second implementation of the recovery execution) can
    reuse the exact same ladder — and so the wording cannot drift from the
    heal budget checks.
    """

    VALID_STRATEGIES: tuple[str, ...] = ("automatic", "resume", "fresh")

    @classmethod
    def validate(cls, strategy: str | None) -> tuple[str | None, str | None]:
        """Normalize + validate a strategy. Returns ``(normalized, error)``;
        at most one is set (both ``None`` is impossible for a valid input)."""
        normalized = (strategy or "automatic").strip().lower()
        if normalized not in cls.VALID_STRATEGIES:
            return None, (
                f"unknown strategy '{strategy}'. One of: "
                + " | ".join(cls.VALID_STRATEGIES)
            )
        return normalized, None

    @staticmethod
    def refusal_for_rot(strategy: str, diagnosis: str) -> str | None:
        """When a parent forces ``resume`` on a rotted child, refuse instead of
        replaying the poisoned context. Returns the refusal message or None."""
        if strategy == "resume" and diagnosis == "rot":
            return (
                "the child's context is rotted (repeated calls / safety "
                "stop / many iterations); force-resuming would replay the "
                "problem. Use strategy='fresh' to restart it cleanly."
            )
        return None

    @staticmethod
    def should_attempt_resume(strategy: str, diagnosis: str) -> bool:
        """Layer 1 (resume same child): only for a blunt miss, unless forced."""
        return strategy in ("automatic", "resume") and (
            diagnosis == "blunt" or strategy == "resume"
        )

    @staticmethod
    def should_attempt_fresh(strategy: str, healed: bool) -> bool:
        """Layer 2 (fresh worker): whenever resuming didn't heal, unless the
        caller forced the SAME child (`strategy='resume'` ends the ladder)."""
        return not healed and strategy != "resume"

    @staticmethod
    def budget_exhausted(layer: str, used: int, limit: int) -> str:
        """Message when a layer's heal budget is exhausted."""
        if layer == "resume":
            return (
                "resume budget exhausted "
                f"(self_heal.max_resumes={limit})"
            )
        return (
            "fresh budget exhausted "
            f"(self_heal.max_fresh_retries={limit})"
        )


@dataclass(frozen=True)
class ResumeDecision:
    """A single planned action for ``Agent.resume_child`` to execute."""

    layer: str  # "resume" | "fresh"
    attempt: int  # 1-based attempt number for the activity event
    refuse_rot: bool = False
    refusal: str | None = None

    @staticmethod
    def rot_refusal(message: str) -> "ResumeDecision":
        return ResumeDecision(layer="none", attempt=0, refuse_rot=True, refusal=message)

    @staticmethod
    def for_layer(layer: str, attempt: int) -> "ResumeDecision":
        return ResumeDecision(layer=layer, attempt=attempt)


class HealBudget:
    """Shared per-child counter of resume/fresh heal attempts.

    Dict-like access (`counts["resume"] += 1`) and explicit ``can``/``bump``
    keep both the runtime's self-heal and a parent's ``resume`` tool reading
    and mutating the SAME budget, so retries cannot stack.
    """

    def __init__(self, *, resume: int = 0, fresh: int = 0) -> None:
        self._used: dict[str, int] = {"resume": resume, "fresh": fresh}

    def __getitem__(self, key: str) -> int:
        return self._used[key]

    def __setitem__(self, key: str, value: int) -> None:
        self._used[key] = value

    def can(self, key: str, max_n: int) -> bool:
        return self._used[key] < max_n

    def bump(self, key: str) -> int:
        self._used[key] += 1
        return self._used[key]

    def as_dict(self) -> dict[str, int]:
        return dict(self._used)


class HealPolicy:
    """Decisions for the layered recovery policy (docs/concepts/self-healing.md).

    Holds the shared heal *limits* (``max_resumes`` / ``max_fresh``); the per-
    child *used* counters live in ``HealBudget`` instances owned separately.
    """

    def __init__(self, *, max_resumes: int = 1, max_fresh: int = 1) -> None:
        self.max_resumes: int = max(int(max_resumes), 0)
        self.max_fresh: int = max(int(max_fresh), 0)

    # -- diagnosis ------------------------------------------------------

    @staticmethod
    def diagnose(is_rot: bool) -> str:
        """Rot (poisoned context → fresh worker) vs blunt (healthy → resume)."""
        return "rot" if is_rot else "blunt"

    @staticmethod
    def diagnose_for_status(
        task_status: TaskStatus, has_deliverable: bool, is_rot: bool
    ) -> str:
        """Public blunt-vs-rot diagnosis for a terminal agent.

        Mirrors ``Runtime.heal_diagnosis``: only failed agents, or completed
        agents without a deliverable, carry a diagnosis; anything else is
        ``"none"``.
        """
        if task_status is TaskStatus.failed or (
            task_status is TaskStatus.completed and not has_deliverable
        ):
            return HealPolicy.diagnose(is_rot)
        return "none"

    # -- deliverable gate -----------------------------------------------

    @staticmethod
    def deliverable_ok(
        expected_outputs: list[str] | None,
        report_artifact_ids: list[str] | None,
        report_files_written: list[str] | None,
    ) -> bool:
        """True when the run produced its required on-disk deliverable.

        If ``expected_outputs`` were declared they must all exist on disk.
        Otherwise, fall back to the system contract: a report that declares
        written files or saved artifact IDs. A prose-only report (no files, no
        artifacts) is not a deliverable.
        """
        if expected_outputs is not None:
            return all(Path(p).exists() for p in expected_outputs)
        return bool(report_artifact_ids or report_files_written)

    # -- message builders ------------------------------------------------

    @staticmethod
    def resume_nudge(expected_outputs: list[str] | None, failure_error: str | None) -> str:
        """The corrective nudge injected when resuming the SAME agent.

        ``failure_error`` is the prior attempt's error when it failed, else
        None (meaning it completed but without a deliverable).
        """
        if failure_error is None:
            if expected_outputs:
                return (
                    f"You finished your previous turn but did not write the "
                    f"required output file(s): {', '.join(expected_outputs)}. "
                    f"Resume NOW from your current context: write exactly these "
                    f"files to disk via write(), verify they parse, then call "
                    f"report() declaring the artifact_ids / files_written."
                )
            return (
                "You finished your previous turn but did not write a deliverable "
                "to disk (no files were written and no artifact was saved). "
                "Resume NOW from your current context: write your findings to "
                "disk via write(), then call report() declaring the "
                "artifact_ids / files_written."
            )
        return (
            f"A previous attempt of this task failed with: {failure_error}. "
            f"Resume your current work and correct the failure — do not repeat "
            f"the same mistake — then write your deliverable(s) to disk and "
            f"complete the task to a final report."
        )

    @staticmethod
    def fresh_restart_note(
        failure_error: str | None, expected_outputs: list[str] | None, note: str | None = None
    ) -> str:
        """The corrective block appended to a FRESH worker's task description.

        ``failure_error`` is the prior attempt's error when it failed (blunt
        miss on the deliverable otherwise), and ``note`` is an optional parent
        instruction folded in after the reason.
        """
        if failure_error:
            block = (
                f"[Note: a prior attempt failed — {failure_error}. Begin from a "
                f"clean slate and complete the task; do not repeat the prior "
                f"failure.]"
            )
        elif expected_outputs:
            block = (
                "[Note: a prior attempt finished without writing "
                f"{', '.join(expected_outputs)}. Begin from a clean slate and "
                f"complete the task, writing those files and reporting them.]"
            )
        else:
            block = (
                "[Note: a prior attempt finished without producing an on-disk "
                "deliverable. Begin from a clean slate and complete the task, "
                "writing your findings to disk and reporting them.]"
            )
        if note:
            block += f"\n\nParent instruction: {note}"
        return block