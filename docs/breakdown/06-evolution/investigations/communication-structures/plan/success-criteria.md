---
id: INFO-076
type: info
title: "Plan — Implementation Success Criteria"
category: investigation / plan
parent: "README.md"
summary: comms tools' schemas never change across cells. guards as every other cell; its measured cost is the verdict. under the default topology. shows two re…
date: 2026-09-23
status: current
---

# Success criteria

1. **One-config switching:** each cell = one `communication.topology` value; the
   comms tools' schemas never change across cells.
2. **No safety exemptions:** cell 3 runs as a log+watermark, under the same
   guards as every other cell; its measured cost is the verdict.
3. **Back-compat proven:** existing `converse`/delegation tests pass unchanged
   under the default topology.
4. **Mock-first determinism:** the stub-LLM test in `test_comms_benchmark.py`
   shows two replicate runs yield identical metrics; real-LLM spread is reported
   as variance, not asserted away.
5. **The report answers** "does richer communication change completion/quality or
   only cost/context-health?" with the five-axis numbers per cell — feeding the
   decision in `../../../06-evolution/investigations/multi-agent-coordination/`.
