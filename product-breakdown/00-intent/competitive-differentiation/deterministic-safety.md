---
title: "Deterministic Safety — Loop Detection and Spawn Limits"
category: meta
summary: >
  The runtime-enforced mechanisms that keep a disobedient model bounded:
  repeated-call / fuzzy near-identical loop detection, and per-lineage spawn caps
  keyed on target signatures.
parent: "README.md"
related:
  - ../../02-architecture/concepts/self-healing.md
---

# Deterministic Safety

Mainstream harnesses *tell* the model to behave ("verify your children", "prune
your context", "don't loop"). Measured behavior shows the model rarely complies —
it almost never calls `prune` in the manyfiles task, and token use balloons to
200–680K ([self-healing](../../02-architecture/concepts/self-healing.md)). Dynamic
Harness enforces the equivalent safety in `_run_loop()`.

## Loop detection

- **Repeated-call detection.** N identical tool-call batches in a row force a
  fail. Pure monitoring tools (`status`, `usage`, `result_read`, `result_bash`)
  are exempt — a parent polling its self-healing children is waiting, not
  looping, and a turn composed solely of them is not counted at all.
- **Near-identical call warning.** A fuzzy detector pagination-normalizes `bash`
  signatures (`sed -n 'A,Bp'` / `awk NR>=A&&NR<=B` / `head -N` collapse to a
  family), treats *same-file overlapping ranges* as the primary repeat signal,
  and warns per-command-family with a warning budget
  (`near_identical_warning_attempts`) before escalating into hard repeated-call
  detection. Strictly-disjoint forward paging and different files stay silent.
- **Per-family budget, not global.** A family that keeps re-reading the same
  material past its budget escalates instead of going silent.

Fuzzy near-duplicate tool-call detection at runtime is not present in the other
harnesses surveyed.

## Spawn limits at a single choke point

Every spawn — roots, children, self-heal fresh restarts — passes through
`Runtime.delegate()`. Beyond `max_agents` and `max_depth`, there is a per-lineage
`max_same_target_delegations` cap keyed on a **normalized file/directory
signature** extracted from the task description (`delegate_target_signature` in
`core/spawn_limits.py`). Re-spawning "explore the same repo" over and over — even
across self-heal restarts — trips the cap.

Refusals raise `DelegationLimit`; the `delegate` tool surfaces them as a
`status: refused` tool result with a `[delegation budget]` line plus a
`safety_warning` activity, and every delegate result carries that budget line so
the model can self-regulate. When a cap refuses a fresh-worker spawn, the runtime
emits `fresh_refused` and leaves the failed agent in place — bounded out rather
than spawning an agent that should never exist.
