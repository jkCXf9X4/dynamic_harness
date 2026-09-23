# Prompt Optimization (Index)

Portable reference for the two-stage A/B-test workflow that optimizes the
Dynamic Harness agent system prompt: how to run it, its inputs and outputs, and
how to feed the winning prompt back into the application. See
[benchmark-alternatives](../benchmark-alternatives/README.md) for the external
benchmark landscape.

## Contents

- [workflow.md](workflow.md) — what the two-round orchestrator does and why ranking is deterministic.
- [files-and-prerequisites.md](files-and-prerequisites.md) — files involved, prerequisites, provider config.
- [running.md](running.md) — full run and the `--seed-only` smoke test.
- [outputs.md](outputs.md) — files written by a full run.
- [task-suite.md](task-suite.md) — the canonical `ALL_TASKS` suite and its probes.
- [feeding-back.md](feeding-back.md) — applying the winning prompt (three options, caveat).
- [provider-quirks.md](provider-quirks.md) — rate limits and tool-calling provider quirks.
- [customizing.md](customizing.md) — extending tasks and tuning the objective.
