# Outputs

After a full run, `.optimize_benchmarks/` contains:

| File | Contents |
|---|---|
| `variants.json` / `variants_round2.json` | Round-1 / Round-2 variant prompts |
| `round1.json` / `round1.md`, `round2.json` / `round2.md` | Per-run metrics + ranked reports |
| `best_prompt.txt` | **The single best system prompt (complete text)** |
| Task artifacts | `largest_files.txt`, `fibonacci.py`, `test_fibonacci.py`, `todos.txt`, `sizes.txt` |

The prune/restore A/B (`.optimize_ab/`) writes `on/bench.*` and `off/bench.*`
plus a printed comparison.
