# Configuration & Integration

## Configuration

A conservative budget beside the existing safety knobs:

```jsonc
{
  "self_heal": {
    "mode": "on",            // on | off
    "max_resumes": 1,        // Layer 1 budget (same-agent resumes)
    "max_fresh_retries": 1   // Layer 3 budget (fresh-worker redelegates)
  }
}
```

## Integration Points

- **Choke points** — wrap the two places that `await` a run and can act on its
  non-report outcome:
  - `Runtime.run` root boundary (runtime.py:136)
  - `run_delegate_tool` / parent boundary (agent.py:601)
- **`heal(agent, diagnosis)`** — inspects `agent.outcome` + safety counters,
  picks the layer, re-enters the loop with the correct nudge/injection.
- **Escapement** — track heal attempts per task so the layer sequence is
  monotone and bounded.
- **Observability** — emit each heal as an `ActivityEvent` for the CLI/UI.
