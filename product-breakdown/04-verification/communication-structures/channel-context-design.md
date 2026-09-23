---
title: "Analysis — Channel Context Design (pollution, discovery, creation)"
category: investigation / analysis
status: open
summary: >
  Containing shared-channel pollution with a per-agent watermark log (not a
  shared inbox), and designing topic-channel discovery (compact directory) and
  creation (rules + ChannelPolicy authority); cell 3 = cell 4 with one universal
  topic.
parent: "INVESTIGATION.md"
---

# Channel context design

Companion to [context-injection-design.md](context-injection-design.md); the
implementation is the plan ([PLAN](plan/README.md)).

## One shared channel: contain the pollution

Naive broadcast to every node is the worst cell on context health, worsened by
the push-multiplier. Defensible reading of "one shared channel":

- **A shared append-only log (store), not a shared inbox.** Each agent has a
  **per-agent watermark**; each turn it is injected a *delta* — only items newer
  than its cursor, folded to headlines + pointers.
- **Subscription is the routing.** Per-subscriber digest + cap is the same
  machinery as topic channels with one topic; so cell 3 is **cell 4 with a single
  topic and universal subscription** — measure the pollution cost of universal
  subscription, not a literal broadcast the safety invariants would strangle.
- **Read-only, cache-safe:** the digest is a pure read (like `status`/`usage`) in
  the repeated-call exempt set / result cache, so polling is cheap and doesn't
  trip loop detection.

## Topic channels: discovery and creation

**Discovery:** a registry mapping `topic → {subscribers, artifact area, last
activity}` (Wegner/TMS directory), injected as a **compact index once**
(`render_reference_index` pattern), with delta re-injection on change; read-only
`channels()`/`channel_info(topic)` tools for mid-run lookups (cacheable, exempt).

**Creation — rules** (authority in `ChannelPolicy`):

- A channel = a stable, recurring topic shared by **≥2 agents** (one-off → bounded message).
- **Cohesion:** named by the shared deliverable/domain, not the team (directory stays scannable).
- Prefer an existing channel + bounded `converse` for one-off negotiation (media richness).
- A **private** persistent work area is an artifact directory, not a channel.
- Do not create what you alone consume (zero subscribers = registry tax); sprawl is a cost.

**Authority:** creation is a boundary decision → host-agnostic `ChannelPolicy`,
default **parent-authorized at its delegation boundary**. "All nodes can
register/create" is a valid *experiment cell* (anarchic registration), not the
default; run both and report the sprawl/contamination.

## Implication for the bed

Injection mechanics are **topology-independent** — same envelope/pointer ladder
every cell; only *who routes what* changes. Cell 4's variable includes
registration authority (parent-authorized vs anarchic).
