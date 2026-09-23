# Edit Checklist

For humans and agents editing `product-breakdown/`.

## Before Writing

1. Locate the canonical home (see the routing table in
   [`storage-rules.md`](storage-rules.md)).
2. Check for an existing representation; decide create / update / merge /
   supersede / remove.
3. Respect the node budget (AD-009): index target ≤40 / cap 75, leaf ≤50 / cap 75, min ~10.

## After Editing

1. Confirm `decision-log.md` and `traceability-map.md` are consistent with the
   files touched; update paths affected by renames or splits.
2. Run `python3 product-breakdown/tools/check_node_size.py --strict` and resolve
   any node over cap (trim → link → split).
3. Run `./build.sh` for LaTeX edits and
   `python3 -m pytest experiments/tests` for scaffold edits.
