# Working Guidelines for the Product Breakdown Structure

Operating rules for (a) how information is stored in `product-breakdown/` and
(b) how future changes are worked before they are implemented, with traceability
kept unbroken. The layer ownership and boundary rules in
[`README.md`](README.md) are authoritative; this document indexes the executable
rules.

## Guidelines

| Guideline | Covers |
|---|---|
| [storage-rules.md](guidelines/storage-rules.md) | Canonical state, ownership/boundary routing, node budget |
| [change-pipeline.md](guidelines/change-pipeline.md) | Idea → IMP → decision → task; IMP lifecycle; graduation |
| [traceability-rules.md](guidelines/traceability-rules.md) | Claim → decision → artifact chain; supersession protocol |
| [edit-checklist.md](guidelines/edit-checklist.md) | Before/after checklist for humans and agents |

## Edit Checklist Summary

Before writing: locate the canonical home, check for an existing
representation, decide create / update / merge / supersede / remove.

After editing: confirm the decision log and traceability map are consistent;
run `python3 product-breakdown/tools/check_node_size.py --strict`; run
`./build.sh` for LaTeX edits and `python3 -m pytest experiments/tests` for
scaffold edits.
