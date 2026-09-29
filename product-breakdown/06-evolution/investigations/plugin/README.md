---
title: Plugin Investigation
summary: "Interface-economy investigation feeding DL-8/DL-9 and AD-007: the runtime's plugin direction is a small set of host-agnostic seams with no loader / no…"
---

# Plugin Investigation

Interface-economy investigation feeding [DL-8/DL-9](../../decision-log.md) and
[AD-007](../../02-architecture/decisions/AD-007.md): the runtime's plugin direction is a small set
of host-agnostic seams with **no loader / no late injection**.

| Part | Leaves |
|---|---|
| Goal, motive, target | [goal](investigation/goal.md), [motivation](investigation/motivation.md), [target](investigation/target.md) |
| Options & rulings | [options](investigation/options.md), [decisions](investigation/decisions.md), [rulings](investigation/rulings.md) |
| Interface economy | [interface-inventory](investigation/interface-inventory.md), [interface-set](investigation/interface-set.md), [design-comparison](investigation/design-comparison.md), [context-architecture](investigation/context-architecture.md) |
| Seam audits | [tool-context](investigation/audit-tool-context.md), [policies](investigation/audit-policies.md), [other seams](investigation/audit-other-seams.md) |
| Next steps & success | [next-steps](investigation/next-steps.md), [success-criteria](investigation/success-criteria.md) |

## Contents

<!-- pb:index:start -->
- [Investigation — Interface Economy: Decoupling Toward a Plugin-Ready Structure](investigation/README.md) — Direction work for making Dynamic Harness' internals decoupled and isolated: a minimal set of narrow, stable common interfaces between components, so the structure is plugin-ready (seams first) without a plugin architecture or late code injection.
<!-- pb:index:end -->
