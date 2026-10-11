---
title: Performance Diagnostics (Index)
summary: Methodology for finding why wall-clock time grows superlinearly with conversation length and agent count — most of it runtime/CLI bookkeeping, not LLM prompting
---

# Performance Diagnostics (Index)

Methodology for finding why wall-clock time grows superlinearly with
conversation length and agent count — most of it runtime/CLI bookkeeping, not
LLM prompting. Start with the built-in scaler, then follow the root-cause
sections.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-116** [Live Diagnosis & Deployment Axes](live-checklist.md) — Checklist for diagnosing a live run — reproduce, confirm H1/H2, profile hotspots, pick the deployment axis
- **INFO-117** [Live-Run Profiling](live-profiling.md) — Re-run the exact failing scenario under the live profiler to capture real LLM latency, event handling, and CLI overheads
- **INFO-118** [Repeatable Protocol (When You Fix Something)](protocol.md) — Before/after protocol for performance claims — same inputs, measurements attached to the change
- **INFO-119** [Two Axes, Two Root Causes](root-causes.md) — Two root causes — unbounded prompt growth with conversation length (H1) and per-event tree rebuilds with agent count (H2, fixed)
- **INFO-120** [Run the Built-in Scaler First](scaler.md) — Mock-LLM scaling benchmark — run it first to see which hot path grows superlinearly with turns or agents
<!-- pb:index:end -->
