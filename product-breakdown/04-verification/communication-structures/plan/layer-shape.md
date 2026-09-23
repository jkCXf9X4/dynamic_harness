---
title: "Plan — Why a Layer, the Package, and Topology Mapping"
category: investigation / plan
parent: "README.md"
---

# Why a layer, the package, and topology mapping

## Why a layer at all

The verified baseline (`../INVESTIGATION.md`, "What already exists") is **one
implicit router** — `converse` reaches any agent by ID (`get_other_agent` →
`runtime.get_agent`), gated only by target status. There is no parent-mediation
gate, no sibling-scope gate, no mailbox, no topic registry, so the four
topologies cannot be toggled today; they must be *constructed*. The cheapest
construction is a **routing backend behind a fixed tool surface**:

- The **tools** never change between cells (the model learns one vocabulary).
- The **backend** decides who receives what — the only variation.
- A cell switch = one config key (or one `Runtime(comms=...)` argument).

This mirrors how the codebase already separates decision from execution
(`core/policies/` objects are host-agnostic; runtime/agent/tools delegate).

## The package

New package `src/dynamic_harness/core/comms/`:

```
comms/
├── message.py       → CommsMessage model + AgentRef + TopicInfo + renderers
├── backend.py       → CommsBackend base + SendVerdict/ReadOutcome + TopologyView
├── channel.py       → ChannelPolicy (creation/join authority, host-agnostic)
├── digest.py        → CommsDigestPolicy (ReactivePolicy, push mode) + render_digest
├── backends/
│   ├── relay.py     → cell 1: parent-mediated
│   ├── siblings.py  → cell 2: same-parent scope
│   ├── shared.py    → cell 3: one topic, universal subscription (log, not broadcast)
│   └── topics.py    → cell 4: topic registry (shared.py generalized)
└── factory.py       → build_backend(config, view): the switching seam
```

Tool defs live with the other tools in `core/tools/comms.py` — host wiring, not
part of the host-agnostic `comms/` package.

## Topology → backend mapping

| Cell | Backend | Routing decision | Subscription meaning | Registration authority |
|------|---------|------------------|----------------------|------------------------|
| 1 Parent-mediated | `relay.py` | Named peer not the parent → rewrite to common parent; parent may forward | n/a — tools refuse ("no topic channels") | n/a |
| 2 Same-parent siblings | `siblings.py` | `message` target must be a same-parent peer; parent stays authority at the boundary | n/a — tools refuse | n/a |
| 3 One shared channel | `shared.py` | Post → the one topic's subscribers; per-agent delta reads | Universal by construction; `subscribe` is a no-op success | n/a |
| 4 Topic channels | `topics.py` | Post → topic subscribers; `join`/`subscribe` gated by `ChannelPolicy` | The load-bearing routing choice — digest membership = subscription | parent-authorized (default) vs anarchic — run both |
| today (baseline) | *(none — implicit)* | Any agent by ID, blocking RPC | n/a | n/a |

Cell 3 is **cell 4 with a single topic + universal subscription + per-agent
deltas** — implemented as an append-only log, not a literal broadcast the safety
invariants would strangle. Its measured context-health/contention cost *is* the
"everyone sees everything" verdict.
