# Repeatable Protocol (When You Fix Something)

Any performance claim needs a before/after on the same inputs; otherwise the
scaler's superlinear shape may be noise. Keep the measurements attached to the
change.

1. Before/after each change, run the same scaler command and the same live task.
2. Record: total wall time, the two smoked-out axes' ratios, and `prompt_tokens`
   at the final turn.
3. A fix is only a win if the relevant ratio stops climbing *and* the live run
   gets faster; keep the scaler run committed to the PR for a before/after.
