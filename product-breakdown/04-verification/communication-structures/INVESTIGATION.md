---
title: "Investigation — Communication Structures vs Agent Success"
category: investigation
status: open
summary: >
  Measurement-first comparison of four communication topologies — parent-mediated,
  same-parent siblings, one shared channel, topic channels — on a fixed
  collaboration task, to establish how structure affects agent success before any
  one mechanism is built out.
---

# Investigation: Communication structures vs agent success

A **measurement-first** verification item: before committing to any one
collaboration mechanism (`../../02-architecture/multi-agent-coordination/`),
establish how different communication structures influence how agents succeed —
same task, same tree shape, only the topology varying.

The four structures form a lattice **1 ⊂ 2 ⊂ 3 ⊂ 4**: a relaying parent is
sibling communication with the parent on the edge; same-parent scoping is the
shared channel restricted to one subtree; one global channel is topic channels
with one unfiltered topic. So the real question is **where the routing decision
is made** (parent, sibling-scope, global, or topic-tagged) and what that costs or
earns:

1. **Parent-mediated** — every exchange passes through the parent (relay).
2. **Same-parent siblings** — children of one parent may message each other directly.
3. **One shared channel** — all nodes read/write a single dedicated channel.
4. **Topic channels** — any node can register/create named channels by topic.

## What already exists — verified 2026-09-17

Ground-truth audit of the current seams (an earlier draft wrongly assumed a
``_links`` spine and a sibling gate existed — they do not):

| Structure | Current reality | Real moving part |
|---|---|---|
| 1 Parent-mediated | **Not the default.** `converse` is a global by-ID RPC (`runtime.get_agent`, `core/agent.py:1708` → `runtime.py:1043`), gated only by target status (`ToolPermissionPolicy.conversable`, `core/policies/permissions.py:51`); a parent relays only if the model forwards. Relay pieces exist (`stream_children` + `[child settled]` folding, `_format_delegate_result` `core/agent.py:985`) | Backend routing any non-parent-peer message to the common parent |
| 2 Same-parent siblings | **Gate does not exist.** `converse` reaches *any* agent, across unrelated subtrees; nothing enforces same-parent | Restrict `message`/`converse` targets to same-parent peers |
| 3 One shared channel | **Partial.** No runtime mailbox, but delivery primitives exist: `submit_input`/`_inject_event` mid-run injection (`core/agent.py:1428/246`), tail-append `_drain_inject_input` (`core/agent.py:1440`), broadcast-shaped `EventBus` (`core/events.py`) | One append-only log (per-subscriber watermark) + cacheable read tool + push digest |
| 4 Topic channels | **De facto but implicit.** Agents emulate channels via scoped artifacts + `converse` pushes; nothing *routes* — no registry, subscription, or per-agent delta | `topic → {subscribers, artifact area}` registry + `join`/`post`/`read` tools; routing authority via a `ChannelPolicy` |

**Corrected baseline:** today there is exactly *one* router — any-agent by-ID,
blocking request/response (cell 2/3-ish reachability, none of the containment).
The experiment cannot run by toggling existing gates (there are none); it needs a
thin, *explicit* routing layer whose only job is making "who routes what" a
swappable decision.

- Measurement design (success battery, controlled bed, open questions, success criteria): [measurement-design.md](measurement-design.md)
- Swappable-layer plan and tool-surface design: [plan/](plan/README.md)
