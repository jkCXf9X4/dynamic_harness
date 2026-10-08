---
title: Performance Diagnostics (Index)
summary: Methodology for finding why wall-clock time grows superlinearly with conversation length and agent count — most of it runtime/CLI bookkeeping, not LLM…
---

# Performance Diagnostics (Index)

Methodology for finding why wall-clock time grows superlinearly with
conversation length and agent count — most of it runtime/CLI bookkeeping, not
LLM prompting. Start with the built-in scaler, then follow the root-cause
sections.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-116** [Live Diagnosis & Deployment Axes](live-checklist.md) — children) and watch total wall time go superlinear. Keep LLM the same. field (agent.py:702) should be constant if context is truly bounded; if it clim…
- **INFO-117** [Live-Run Profiling](live-profiling.md) — The scaler is a synthetic micro-benchmark. To capture what a real, live run actually did — real LLM latency, event handling, CLI overheads — re-run th…
- **INFO-118** [Repeatable Protocol (When You Fix Something)](protocol.md) — Any performance claim needs a before/after on the same inputs; otherwise the scaler's superlinear shape may be noise. Keep the measurements attached t…
- **INFO-119** [Two Axes, Two Root Causes](root-causes.md) — (default 50) is often read as "only the last 50 turns reach the model". It does not. It only limits which turns are listed in the Context Observation…
- **INFO-120** [Run the Built-in Scaler First](scaler.md) — Run the Built-in Scaler First
<!-- pb:index:end -->
