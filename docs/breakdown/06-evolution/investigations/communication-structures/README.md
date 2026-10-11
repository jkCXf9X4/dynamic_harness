---
title: Communication Structures — Evidence Chain
summary: "Auditable evidence chain (INVESTIGATION, PLAN, FINDINGS, RESULTS, raw metrics-cells.json) that compared four communication topologies on a fixed collaboration task."
---


# Communication Structures — Evidence Chain

Auditable evidence chain (INVESTIGATION, PLAN, FINDINGS, RESULTS, raw
`metrics-cells.json`) that compared four communication topologies on a fixed
collaboration task. Closes `AD-001` (reject parent-mediated relaying),
`AD-002` + `AD-003` (topic channels), and retired `DL-11` (tombstone
`deprecated/decision-log.md`; read via `pb archive read deprecated/decision-log.md`);
backs `AD-001`…`AD-008` (archive records).

- **Question** — `INFO-064` (INVESTIGATION.md), `INFO-068` (measurement-design.md)
- **Design** — `plan/` (layer shape, message model, tool surface, phases)
- **Context design** — `INFO-067` (context-injection-design.md), `INFO-066` (channel-context-design.md)
- **Evidence** — `INFO-063` (FINDINGS.md)
- **Outcome** — `INFO-065` (RESULTS.md), `metrics-cells.json`

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-063** [Findings — real-LLM communication comparison (P4)](FINDINGS.md) — Real-LLM P4 comparison findings. Circular `converse` deadlock confirmed on the `off` cell; `shared` completes correctly in 40 turns, `topics_parent` with ~6x churn; n=1 per cell, ratios not absolutes.
- **INFO-064** [Investigation — Communication Structures vs Agent Success](INVESTIGATION.md) — Measurement-first comparison of four communication topologies (parent-mediated, same-parent siblings, one shared channel, topic channels) on a fixed collaboration task, to establish how structure affects agent success before any one mechanism is built out.
- **INFO-065** [Communication comparison — real-LLM run](RESULTS.md) — Real-LLM run results (2026-09-18), 3 cells, 1 replicate each; `off` timed out (converse deadlock), `shared` and `topics_parent` completed correctly; per-cell and per-run metric tables.
- **INFO-066** [Analysis — Channel Context Design (pollution, discovery, creation)](channel-context-design.md) — Containing shared-channel pollution with a per-agent watermark log (not a shared inbox), and designing topic-channel discovery (compact directory) and creation (rules + ChannelPolicy authority); cell 3 = cell 4 with one universal topic.
- **INFO-067** [Analysis — Injecting Communication into Agent Context](context-injection-design.md) — How communication enters an agent's context: inject typed envelopes, not raw content; tail-appended user messages keep the prompt prefix cache-safe; a typed envelope frames channel traffic as related work, not instructions.
- **INFO-068** [Measurement Design — Communication Topology Comparison](measurement-design.md) — How the communication-topology comparison is measured: five success axes, the controlled comparison bed, predicted outcomes, open questions, and success criteria. Companion to INVESTIGATION.md.
- [Plan — A Swappable Communication Layer for Topology Experiments](plan/README.md) — A thin, host-agnostic communication layer between tools and runtime so the four topology cells are a config switch. One uniform tool surface (`converse` / `message` / `post` / `channel_read` / `subscribe` / `unsubscribe` / `channels` / `channel_info`); only the routing backend differs. Leaves here hold the design, tool surface, switching seams, bed, phases, and criteria.
<!-- pb:index:end -->
