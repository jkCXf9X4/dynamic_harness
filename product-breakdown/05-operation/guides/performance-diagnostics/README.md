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
