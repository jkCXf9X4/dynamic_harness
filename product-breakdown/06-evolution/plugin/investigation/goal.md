---
title: "Plugin Direction — The Step Being Investigated"
category: investigation
parent: "README.md"
summary: >
  Establish and minimize the common interfaces between internal components and
  decouple/isolate them; plugin-ready structure, not plugin infrastructure.
---

# The step being investigated

The harness is a monolith of *near-seams*: tools grouped by concern, policies
extracted into host-agnostic decision objects, a metric-reactive registry that
already calls itself "the plugin seam", an event bus, an LLM provider ABC. Each
surface is individually extensible in code — but the seams are *incidental*:
their shapes differ, their breadth varies, and components still reach across
them (see [interface-inventory.md](interface-inventory.md)).

This working item investigates a **structural goal, not a mechanism**:

> Establish and **minimize** the common interfaces between internal components,
> and **de-couple and isolate** those components behind them. A plugin
> architecture with late injection of code is **not** required — plugin-ready
> *structure* is the target; a loader is out of scope.

| Aspect | Today (extensible monolith) | Target (plugin-ready structure) |
|--------|------------------------------|---------------------------------|
| Common interfaces | Many, incidental, broad (`ToolContext`, policies, event fns, ABCs) | Few, explicit, **narrow** — each exposing only what its consumers need |
| Coupling | Components import each other directly across layers | Components know neighbors only through contracts |
| Isolation | Private state reachable through wide façades | No outside reach into internals; data types pure |
| Replaceability | By-hand subclass/register-over-name | A consequence of narrow seams, not a special feature |
| Late injection | None today (good) | **Stays out of scope** — no loader, no dynamic code loading |

The folder is named `plugin/` because the *vision* is plugin-centric structure;
this document deliberately argues against building plugin *infrastructure* now.
