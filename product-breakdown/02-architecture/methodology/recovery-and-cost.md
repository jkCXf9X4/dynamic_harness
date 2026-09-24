# Failure Recovery & Cost

## Failure Recovery

See [delegation-guidelines skill](../../../3rd_party/agent_methods_and_tools/methods/delegation-guidelines/SKILL.md) →
"The Kill → Inspect → Retry loop" for the full salvage-and-retry protocol.
Short version:

| Failure | Recovery |
|---|---|
| Child returns failed | `status()` → inspect salvage → if clearable, re-delegate *with the salvage folded in*; else escalate |
| Child stuck / looping / rogue | `kill()` (recursive for a subtree) → read the `salvage` on the kill result → re-delegate carrying done/pending + key findings |
| Artifact empty/missing | converse("Did you write findings?") → read correct path or re-delegate |
| Safety limits hit | Task too broad. Re-delegate with narrower description. |
| Child escalated | Read escalation context. Resolve or pass up via your own escalate(). |
| Multiple children fail | Decomposition likely wrong. Escalate with failure summary. |

## Cost Heuristics

| Action | Approx. Tokens | Rule |
|---|---|---|
| Read known file | 500–2000 | Use when path is specific |
| Delegate | 2000–5000 overhead | When sub-task needs 2+ calls |
| compress() | 5000–15000 | When context > 50 messages |

**Rule of thumb:** Delegation ~3K overhead. If DIY takes 3+ turns at 2K+/turn,
delegating is cheaper AND better quality.
