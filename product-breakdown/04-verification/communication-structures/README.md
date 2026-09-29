---
title: Communication Structures — Evidence Chain
summary: The auditable INVESTIGATION → PLAN → FINDINGS → RESULTS flow (with raw ) that empirically compared four communication topologies on a fixed collaborat…
---

# Communication Structures — Evidence Chain

The auditable INVESTIGATION → PLAN → FINDINGS → RESULTS flow (with raw
`metrics-cells.json`) that empirically compared four communication topologies on
a fixed collaboration task. Closes [DL-6/DL-7/DL-11](../../decision-log.md) and
backs [AD-001…AD-008](../../decisions/README.md).

| Stage | Node |
|---|---|
| Question | [INVESTIGATION.md](INVESTIGATION.md), [measurement-design](measurement-design.md) |
| Design | [plan/](plan/README.md) (layer shape, message model, tool surface, phases) |
| Context design | [context-injection-design](context-injection-design.md), [channel-context-design](channel-context-design.md) |
| Evidence | [FINDINGS.md](FINDINGS.md) |
| Outcome | [RESULTS.md](RESULTS.md), `metrics-cells.json` |

## Contents

<!-- pb:index:start -->
- **INFO-063** [Findings — real-LLM communication comparison (P4)](FINDINGS.md) — Probe status is appended LIVE under ; full metric tables are produced by into /
- **INFO-064** [Investigation — Communication Structures vs Agent Success](INVESTIGATION.md) — Measurement-first comparison of four communication topologies — parent-mediated, same-parent siblings, one shared channel, topic channels — on a fixed collaboration task, to establish how structure affects agent success before any one mechanism is built out.
- **INFO-065** [Communication comparison — real-LLM run](RESULTS.md) — When
- **INFO-066** [Analysis — Channel Context Design (pollution, discovery, creation)](channel-context-design.md) — Containing shared-channel pollution with a per-agent watermark log (not a shared inbox), and designing topic-channel discovery (compact directory) and creation (rules + ChannelPolicy authority); cell 3 = cell 4 with one universal topic.
- **INFO-067** [Analysis — Injecting Communication into Agent Context](context-injection-design.md) — How communication enters an agent's context: inject typed envelopes, not raw content; tail-appended user messages keep the prompt prefix cache-safe; a typed envelope frames channel traffic as related work, not instructions.
- **INFO-068** [Measurement Design — Communication Topology Comparison](measurement-design.md) — How the communication-topology comparison is measured: five success axes, the controlled comparison bed, predicted outcomes, open questions, and success criteria. Companion to INVESTIGATION.md.
- [Plan — A Swappable Communication Layer for Topology Experiments](plan/README.md) — A thin, host-agnostic communication layer between tools and runtime so the four topology cells are a config switch. One uniform tool surface (`converse` / `message` / `post` / `channel_read` / `subscribe` / `unsubscribe` / `channels` / `channel_info`); only the routing backend differs. Leaves here hold the design, tool surface, switching seams, bed, phases, and criteria.
<!-- pb:index:end -->

## Decisions

- AD-008 — Comms Layer = Swappable Routing Backend Behind One Uniform Tool Surface
