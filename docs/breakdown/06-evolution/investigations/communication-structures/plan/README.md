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

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-069** [Plan — CommsBackend and ChannelPolicy](backend-and-channel-policy.md) — `python class CommsBackend: base class; subclasses vary only the routing decision name: str channels_enabled: bool
- **INFO-070** [Plan — Comparison Bed](comparison-bed.md) — Reuses the existing benchmark infrastructure; the cell is the parameter
- **INFO-071** [Plan — Injection Modes and Renderer](injection.md) — Both modes use the same → text renderer; only who initiates differs. This is the experiment's second variable (push cost), so it is a switch
- **INFO-072** [Plan — Why a Layer, the Package, and Topology Mapping](layer-shape.md) — The verified baseline ("What already exists") is one implicit router — reaches any agent by ID , gated only by target status. There is no parent-media…
- **INFO-073** [Plan — CommsMessage Model](message-model.md) — Plan — CommsMessage Model
- **INFO-074** [Plan — Implementation Phases](phases.md) — , + / / , , the four backends , and the config→backend factory . Watermarks are in-memory per-(agent, topic) on the backend (no separate tracker class…
- **INFO-075** [Plan — Risks and Decisions to Confirm](risks.md) — cells 3/4 are pull-first. The field + environment note must prevent a model from waiting on a notification. If cells 3/4 want blocking too, add a para…
- **INFO-076** [Plan — Implementation Success Criteria](success-criteria.md) — comms tools' schemas never change across cells. guards as every other cell; its measured cost is the verdict. under the default topology. shows two re…
- **INFO-077** [Plan — Switching Seams](switching.md) — Seam A — construction. gains a section
- **INFO-078** [Plan — Tool Surface](tool-surface.md) — Registered once in ; every tool is a thin wrapper over methods delegating to (the backend). No tool knows which backend is live
<!-- pb:index:end -->
