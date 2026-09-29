---
title: Requirements — CLI Sub-Spec (Index)
summary: Requirements governing the delivered terminal surface and the persisted overview (DL-12). The runtime's product definition lives in ; this folder pins…
---

# Requirements — CLI Sub-Spec (Index)

Requirements governing the delivered terminal surface and the persisted overview
(DL-12). The runtime's product definition lives in `../README.md`; this folder
pins the CLI.

Decisions: `../../02-architecture/decisions/` (DL-12).

## Contents

<!-- pb:index:start -->
- **INFO-013** [Acceptance criteria — CLI](acceptance.md) — Observable checks that the terminal stays prompt-only and the persisted overview/tree behave as specified.
- **INFO-014** [CLI Direction & Requirements — Direction](direction.md) — Why the CLI is minimal and prompt-only: status/tree/event telemetry is persisted to files so a run can be driven headlessly and inspected by other tooling.
- **INFO-015** [FR-3 — Live interactive surface](fr-live-surface.md) — The prompt line doubles as a live progress counter; input is always available during a run (queued when busy, immediate during a child-wait); the root agent's text replies stream above the prompt.
- **INFO-016** [FR-4..FR-6 — Operator evaluation, session continuity, traceability](fr-operator-and-session.md) — A quick plain-text tree for spotting stuck/runaway agents; the REPL keeps one root agent across turns; provenance and overview files survive the process.
- **INFO-017** [FR-2 — Persisted overview](fr-persisted-overview.md) — Every run writes a continuously-refreshed overview to the run root (the parent of artifacts/, repo/, and traces/).
- **INFO-018** [FR-1 — Prompt-only terminal](fr-terminal.md) — The terminal accepts a task prompt, prints the final outcome and an aggregate, and renders no live dashboard.
- **INFO-019** [NFR-1..NFR-4 — Non-functional requirements](nfr.md) — Composability, rendering isolation, cheap live helpers, and an atomic append-only event log.
<!-- pb:index:end -->
