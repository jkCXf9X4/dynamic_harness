---
title: "Measurement Design — Communication Topology Comparison"
category: investigation
status: open
summary: >
  How the communication-topology comparison is measured: five success axes, the
  controlled comparison bed, predicted outcomes, open questions, and success
  criteria. Companion to INVESTIGATION.md.
parent: "INVESTIGATION.md"
---

# Measurement design

## What "agents succeed at their work" means — measurable

Agree a success battery up front so the comparison is fair (all measurable from
existing telemetry/usage/artifacts):

1. **Completion** — final task status (completed/escalated/failed) on the same task set.
2. **Quality** — VERIFY outcome / acceptance-criteria pass (gap G1); needs a mechanical checker on the deliverable, not prompt-discipline.
3. **Cost** — total tokens (`Runtime.total_usage()`), LLM calls, wall-clock.
4. **Context health** — peak and final message-count / estimated-token footprint per agent (from the `usage` tool); proxy for "did the topology rot contexts".
5. **Contention / accident rate** — cycle detections (repeated-call), conflicting writes, kills, self-heal activations; social topologies (3, 4) are expected to pay here; measure it.

## Controlled comparison bed

Everything constant except the topology: fixed tree (one parent, 4 children),
fixed task (one deliverable requiring shared intermediate findings — the
*interdependent* case, not independent fan-out), same LLM provider and model,
same budgets, N replicates per cell.

| Structure | Predicted strength | Predicted weakness |
|---|---|---|
| 1 Parent-mediated | Simplest, deterministic, no unvetted edges; parent guarantees the deliverable | Parent context rot; serializes parallel work; relay bottleneck |
| 2 Same-parent siblings | Direct handoff, low parent context pressure; bounded edge set; parent stays authority | Isolation softened for the group; needs per-pair cycle caps |
| 3 One shared channel | Maximal information flow; no routing search cost | Inbox flood; unbounded contamination; commons-tragedy needs a broker anyway |
| 4 Topic channels | Information routed where needed; artifacts give provenance; the current de facto shape | Channel naming/granularity decisions; stale-topic drift; routing is still a model decision |

## Key open questions

1. **Natural comparison unit?** One run yields an outcome, but success is noisy; set replicate count / variance budget before calling a loser on noise.
2. **Is "richer channel = better" the right hypothesis?** Media-richness predicts *matching* medium to task (lean → shared store; equivocal → rich messages), not "more channel always wins"; score per-task equivocality, not an overall average.
3. **Does structure change who succeeds or only what it costs?** On easy tasks all may complete; need a task gradient (easy → hard collaboration).
4. **What role does the parent play per structure?** Router in 1; boundary authority in 2/4; nobody in 3. Is "no authority" survivable (Ostrom: long-lived commons have institutions)?
5. **Can cell 3 run as designed** without instantly tripping the repeated-call/context guards? If safety makes it untestable, that is itself a result.

## Next steps

1. Write the success-battery definition (5 axes, operationalized).
2. Define the task gradient (independent → interdependent → adversarial), reusing `benchmark/tasks.py`.
3. Implement the 4 topologies as thin switches on the existing links/mailbox/artifact seams.
4. Run the controlled comparison (deterministic mock-LLM first, then real-LLM probes with N replicates per cell).
5. Report completion/quality/cost/context-health/contention per cell.
6. Decide which structure(s) feed the collaboration spine, or confirm the current hybrid (4 de facto).

## Success criteria

1. The bed is reproducible — mock-LLM runs give the same cell ranking; real-LLM spread is reported as variance, not asserted away.
2. All four topologies run on the same task/tree/budget, with no safety exemptions granted to cell 3.
3. The report answers "does richer communication change completion/quality or only cost?" with numbers.
4. A topology (or the hybrid) is adopted on evidence, not on the dev investigation's design reasoning alone.
