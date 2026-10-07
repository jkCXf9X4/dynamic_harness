---
title: "Plan — A Swappable Communication Layer for Topology Experiments"
category: investigation / plan
status: implemented (P0–P3) / started (P4)
summary: >
  A thin, host-agnostic communication layer between tools and runtime so the four
  topology cells are a config switch. One uniform tool surface (`converse` /
  `message` / `post` / `channel_read` / `subscribe` / `unsubscribe` / `channels` /
  `channel_info`); only the routing backend differs. Leaves here hold the design,
  tool surface, switching seams, bed, phases, and criteria.
parent: "INVESTIGATION.md"
---

# Plan: swappable communication layer

Status: **P0 (backends) + P1 (tool surface + config switching)** implemented in
`src/dynamic_harness/core/comms/` and `core/tools/comms.py`; **P2 (push-digest)**
in `core/comms/digest.py`; **P3 (collaboration bed)** in `benchmark/comms.py` +
`resources/_collab`. Tests: `tests/backend/test_comms.py`,
`tests/backend/test_comms_benchmark.py`. **P4 (the real-LLM run)** is started —
see [FINDINGS.md](../FINDINGS.md) and [RESULTS.md](../RESULTS.md).

Open investigation questions and the measurement battery are canonical in

[../measurement-design.md](../measurement-design.md).

## Contents
