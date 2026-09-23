# Run the Built-in Scaler First

```
python -m dynamic_harness.benchmark.profile_scaling            # full grid
python -m dynamic_harness.benchmark.profile_scaling --quick   # fast sanity pass
```

It uses a **mock LLM (no network)** and measures, in isolation, the scaling of
each suspected hot path. Read the *shading* column: a ratio that roughly doubles
when size doubles = **superlinear = suspect**. The tool prints four axes:

| Section | Question it answers | Dominant axis |
|---------|--------------------|---------------|
| A  | Does `persist_checkpoint()` cost grow with conversation length? | turns |
| A2 | How many **bytes/tokens are actually SENT to the LLM** per turn? | turns |
| B  | Does `Repository.commit()` (full journal rewrite) grow with agent count? | agents |
| C  | Does the CLI snapshot (`StateWriter.snapshot`) grow with agent count? | agents agg. |
| D  | End-to-end `Agent.run()` wall time at growing turn counts | end-to-end |

If the box this app runs in is CLI/REPL, C is usually the biggest "why did it get
so much slower than I expected". If it is the programmatic `Runtime` API, A2 and
A dominate over long conversations.
