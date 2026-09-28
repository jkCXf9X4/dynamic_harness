# Open Questions (before implementation)

The questions the investigation must resolve before the multi-agent coordination
design is implemented. Record: [INVESTIGATION.md](INVESTIGATION.md).

1. **Scope of "solve together."** True peer/sibling communication does NOT exist.
   The actor model isolates agents (know only parent + children + task). Is the
   target *parent-mediated* coordination (safe within the model) or *peer
   collaboration* (requires relaxing the isolation invariant)?
2. **Cost/context floor.** Streaming burns more parent turns and grows parent
   context as it accumulates settlements + converse exchanges. At what point does
   the orchestrating parent degrade into a monolithic agent (the thing the whole
   architecture avoids)? Need a measurable budget / handoff rule.
3. **Verification is prompt-discipline, not a mechanism.** G1 (acceptance
   criteria never mechanically checked) and G7 (converse-based heal reuses the
   shared `_recover`, not a distinct mechanism) — see
   `../../04-verification/gap-analysis.md`. Should "converse → demand better"
   become a first-class mechanism?
4. **Failure steering.** How does a parent reliably detect a bad child result and
   decide converse vs resume vs kill vs re-delegate — and does the current
   `resume`/self-heal budget cover the multi-round coordination case?
5. **Termination.** When a parent reports/escalates/fails with children still
   running, stragglers are cancelled. Is that the right contract for the complex
   mode, or should settling work be allowed to complete and merge?
