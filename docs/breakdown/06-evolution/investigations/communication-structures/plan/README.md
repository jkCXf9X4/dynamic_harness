---
title: Plan — A Swappable Communication Layer for Topology Experiments
summary: "A thin, host-agnostic communication layer between tools and runtime so the four topology cells are a config switch. One uniform tool surface (`converse` / `message` / `post` / `channel_read` / `subscribe` / `unsubscribe` / `channels` / `channel_info`); only the routing backend differs. Leaves here hold the design, tool surface, switching seams, bed, phases, and criteria."
---


# Plan — A Swappable Communication Layer for Topology Experiments

Status: **P0 (backends) + P1 (tool surface + config switching)** implemented in
`src/dynamic_harness/core/comms/` and `core/tools/comms.py`; **P2 (push-digest)**
in `core/comms/digest.py`; **P3 (collaboration bed)** in `benchmark/comms.py` +
`resources/_collab`. Tests: `tests/backend/test_comms.py`,
`tests/backend/test_comms_benchmark.py`. **P4 (the real-LLM run)** is started —
see `INFO-063` (FINDINGS.md) and `INFO-065` (RESULTS.md).

Open investigation questions and the measurement battery are canonical in
`INFO-068` (measurement-design.md).

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-069** [Plan — CommsBackend and ChannelPolicy](backend-and-channel-policy.md) — The `CommsBackend` base class (routing decision in `route_message`) and `ChannelPolicy` (creation/join authority) that make the four topology cells a swappable backend.
- **INFO-070** [Plan — Comparison Bed](comparison-bed.md) — The controlled comparison bed reuses the existing benchmark infrastructure; the topology cell is the parameter, with the five-axis battery canonical in `INFO-068`.
- **INFO-071** [Plan — Injection Modes and Renderer](injection.md) — Two swappable injection modes (pull default, push-digest) share one `CommsMessage` to text renderer; the mode is the experiment's second variable (push cost).
- **INFO-072** [Plan — Why a Layer, the Package, and Topology Mapping](layer-shape.md) — Why a routing layer is needed (the verified baseline is one implicit router), the `core/comms/` package layout, and the topology to backend mapping.
- **INFO-073** [Plan — CommsMessage Model](message-model.md) — The `CommsMessage` typed envelope (id, topic, kind, sender, recipients, stage, content, seq) and why each field is shaped that way.
- **INFO-074** [Plan — Implementation Phases](phases.md) — Implementation phases P0 to P4 (backend, tool surface, push-digest, bed, the run), each independently testable; P0 to P3 implemented, P4 started.
- **INFO-075** [Plan — Risks and Decisions to Confirm](risks.md) — Risks and decisions to confirm for the comms layer. Blocking vs fire-and-forget, back-compat default, watermark placement, the anarchic cell 4 variant, relay visibility, and subscription as signal not gate.
- **INFO-076** [Plan — Implementation Success Criteria](success-criteria.md) — Implementation success criteria. One-config switching, no safety exemptions, back-compat proven, mock-first determinism, and a report that answers the cost question with five-axis numbers.
- **INFO-077** [Plan — Switching Seams](switching.md) — The two switching seams. The `communication` config section (Seam A, construction) and the one-time environment note (Seam B, the model's view).
- **INFO-078** [Plan — Tool Surface](tool-surface.md) — The uniform tool surface (channels, channel_info, post, channel_read, subscribe, unsubscribe, message, converse) — one vocabulary across all cells, with subscription as signal not gate.
<!-- pb:index:end -->
