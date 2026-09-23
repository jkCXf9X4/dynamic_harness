# Performance Diagnostics (Index)

Methodology for finding why wall-clock time grows superlinearly with
conversation length and agent count — most of it runtime/CLI bookkeeping, not
LLM prompting. Start with the built-in scaler, then follow the root-cause
sections.

## Contents

- [scaler.md](scaler.md) — run the mock-LLM scaler and read its four axes.
- [root-causes.md](root-causes.md) — H1 unbounded prompt, H2 per-event snapshot rebuild.
- [live-checklist.md](live-checklist.md) — attribution checklist, deployment axes, honest reading.
- [protocol.md](protocol.md) — before/after protocol when fixing something.
- [live-profiling.md](live-profiling.md) — `--profile` on a real run for bug reports.
