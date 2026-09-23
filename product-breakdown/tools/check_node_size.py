#!/usr/bin/env python3
"""Node-size checker for the product-breakdown structure (AD-009).

Every markdown file under ``product-breakdown/`` is a node:

- **Index node** — one per folder, ``README.md``. Navigational only.
  Target <=40 lines, hard cap 75.
- **Leaf node** — one concern. Target <=50 lines, hard cap 75, minimum ~10.

Nodes that exceed the cap (or fall under the leaf minimum) are violations.
There are no exemptions: ``--strict`` exits non-zero on any violation.

Usage::

    python3 product-breakdown/tools/check_node_size.py            # report
    python3 product-breakdown/tools/check_node_size.py --strict   # non-zero on violation
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BREAKDOWN = REPO_ROOT / "product-breakdown"

INDEX_TARGET = 40
INDEX_CAP = 75
LEAF_TARGET = 50
LEAF_CAP = 75
LEAF_MIN = 10


def classify(path: Path) -> str:
    return "index" if path.name == "README.md" else "leaf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check product-breakdown node sizes.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when any node violates its budget",
    )
    args = parser.parse_args(argv)

    violations: list[tuple[str, str, int]] = []

    for path in sorted(BREAKDOWN.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        kind = classify(path)
        lines = len(path.read_text(encoding="utf-8").splitlines())
        cap = INDEX_CAP if kind == "index" else LEAF_CAP
        if lines > cap or (kind == "leaf" and lines < LEAF_MIN):
            violations.append((rel, kind, lines))

    for rel, kind, lines in sorted(violations):
        cap = INDEX_CAP if kind == "index" else LEAF_CAP
        if kind == "leaf" and lines < LEAF_MIN:
            reason = f"{lines} lines < leaf minimum {LEAF_MIN}"
        else:
            reason = f"{lines} lines > cap {cap}"
        print(f"[VIOLATION] {rel} ({kind}, {reason})")

    print(f"\n{len(violations)} violation(s).")

    if args.strict and violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
